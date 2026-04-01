"""
RAG Engine Service
Handles document embedding, vector storage (ChromaDB), and LLM-powered question answering.
Supports automatic fallback across multiple free-tier LLM providers.
"""
import os
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.schema import Document, HumanMessage, SystemMessage

_vectorstore = None
_embeddings = None
_usage = {"requests": 0, "tokens": 0, "cost": 0.0, "last_provider": None}
_usage_lock = threading.Lock()

CHROMA_DIR = str(Path(__file__).parent.parent / "data" / "chroma_db")

# Cost per 1M tokens (input+output blended average) — USD
COST_PER_1M_TOKENS = {
    "bedrock": 0.105,   # Nova Lite: $0.06 input + $0.24 output, blended ~$0.105
    "groq": 0.0,        # Free tier
    "google": 0.0,      # Free tier
    "cerebras": 0.0,    # Free tier
    "openai": 7.50,     # GPT-4o: $2.50 input + $10 output, blended ~$7.50
}
COLLECTION_NAME = "infosec_knowledge"

# Provider configs: name -> {env_key, model_env, default_model, free_rpd, free_tpm}
PROVIDERS = {
    "bedrock":  {"key_env": "AWS_ACCESS_KEY_ID",  "model_env": "BEDROCK_MODEL",  "default": "apac.amazon.nova-lite-v1:0", "rpd": 10000, "tpm": 100000},
    "groq":     {"key_env": "GROQ_API_KEY",     "model_env": "GROQ_MODEL",     "default": "meta-llama/llama-3.3-70b-versatile", "rpd": 1000,  "tpm": 30000},
    "google":   {"key_env": "GOOGLE_API_KEY",    "model_env": "GOOGLE_MODEL",   "default": "gemini-2.0-flash",                          "rpd": 250,   "tpm": 250000},
    "cerebras": {"key_env": "CEREBRAS_API_KEY",  "model_env": "CEREBRAS_MODEL", "default": "llama3.1-8b",                              "rpd": 5000,  "tpm": 60000},
    "openai":   {"key_env": "OPENAI_API_KEY",    "model_env": "OPENAI_MODEL",   "default": "gpt-4o",                                    "rpd": 500,   "tpm": 30000},
}

SYSTEM_PROMPT = """You are an expert Information Security compliance assistant for Locobuzz. Answer InfoSec questionnaire questions accurately using ONLY the provided context.

STRICT RULES:
1. ALWAYS refer to the provider/vendor/entity as 'Locobuzz'. NEVER use generic terms like 'the provider', 'the vendor', or 'the organization'.
2. Answer InfoSec questionnaire questions accurately using ONLY the provided context.
3. If the context doesn't contain enough information, say so clearly.
4. Be professional, concise, and direct — answers go into client-facing questionnaires.
5. Use specific details, policy names, and references from the context when available.
6. If the question asks for a Yes/No, start with "Yes," or "No," followed by the explanation on the SAME line — do NOT put a line break after Yes or No.
7. Write answers suitable for copy-pasting directly into a questionnaire response.
8. If the user asks you to shorten, rephrase, or adjust a previous answer, DO IT — re-answer the original question with the requested changes. Do NOT ask the user to repeat their question.
9. NEVER respond with meta-commentary like "I'll make sure to..." or "Please go ahead and ask..." — always provide a direct answer.
"""


def get_usage_stats():
    with _usage_lock:
        return dict(_usage)


def get_fallback_chain():
    """Return ordered list of providers to try. Primary first, then fallbacks with valid API keys."""
    primary = os.getenv("LLM_PROVIDER", "bedrock")
    fallback_str = os.getenv("FALLBACK_PROVIDERS", "bedrock,groq,google,cerebras")
    chain = [p.strip() for p in fallback_str.split(",") if p.strip()]
    if primary in chain:
        chain.remove(primary)
    chain.insert(0, primary)
    # Filter: bedrock uses AWS credential chain (always available if configured), others need explicit keys
    def has_credentials(p):
        if p == "bedrock":
            return bool(os.getenv("AWS_ACCESS_KEY_ID", "").strip() or os.getenv("AWS_PROFILE", "").strip() or True)  # boto3 auto-discovers
        return bool(os.getenv(PROVIDERS.get(p, {}).get("key_env", ""), "").strip())
    return [p for p in chain if has_credentials(p)]


def get_provider_info():
    """Return info about all configured providers for the health endpoint."""
    chain = get_fallback_chain()
    primary = os.getenv("LLM_PROVIDER", "groq")
    result = []
    for name in chain:
        cfg = PROVIDERS.get(name, {})
        model = os.getenv(cfg.get("model_env", ""), cfg.get("default", "unknown"))
        result.append({
            "name": name,
            "model": model,
            "is_primary": name == primary,
            "free_rpd": cfg.get("rpd", 0),
            "free_tpm": cfg.get("tpm", 0),
        })
    return result


def _create_llm(provider: str):
    """Create an LLM instance for a specific provider."""
    cfg = PROVIDERS.get(provider, {})
    model = os.getenv(cfg.get("model_env", ""), cfg.get("default", ""))
    api_key = os.getenv(cfg.get("key_env", ""), "")

    if provider == "bedrock":
        import boto3
        from langchain_aws import ChatBedrock
        session = boto3.Session(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
            region_name=os.getenv("AWS_REGION", "ap-south-1"),
        )
        return ChatBedrock(
            model_id=model,
            client=session.client("bedrock-runtime"),
            model_kwargs={"temperature": 0.1},
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model_name=model, groq_api_key=api_key, temperature=0.1)
    elif provider == "cerebras":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, openai_api_key=api_key, base_url="https://api.cerebras.ai/v1", temperature=0.1)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, openai_api_key=api_key, temperature=0.1)
    else:  # google
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0.1, max_retries=2)


def _get_embeddings():
    global _embeddings
    if _embeddings is not None:
        return _embeddings
    provider = os.getenv("EMBEDDING_PROVIDER", "local")
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        _embeddings = OpenAIEmbeddings(model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"), openai_api_key=os.getenv("OPENAI_API_KEY"))
    elif provider == "local":
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(model_name=os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    else:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        _embeddings = GoogleGenerativeAIEmbeddings(model=os.getenv("GOOGLE_EMBEDDING_MODEL", "models/gemini-embedding-001"), google_api_key=os.getenv("GOOGLE_API_KEY"))
    return _embeddings


def _get_vectorstore():
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore
    _vectorstore = Chroma(collection_name=COLLECTION_NAME, embedding_function=_get_embeddings(), persist_directory=CHROMA_DIR)
    return _vectorstore


def reset_instances():
    global _vectorstore, _embeddings
    _vectorstore = None
    _embeddings = None


def ingest_document(text: str, metadata: Dict) -> int:
    """Chunk text and store embeddings in ChromaDB."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", ". ", " ", ""])
    chunks = splitter.split_text(text)
    documents = [Document(page_content=chunk, metadata={**metadata, "chunk_index": i}) for i, chunk in enumerate(chunks)]
    vectorstore = _get_vectorstore()

    if os.getenv("EMBEDDING_PROVIDER", "local") == "local":
        vectorstore.add_documents(documents)
        return len(documents)

    for i in range(0, len(documents), 20):
        batch = documents[i:i + 20]
        for attempt in range(3):
            try:
                vectorstore.add_documents(batch)
                break
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    time.sleep(10)
                    continue
                raise
        if i + 20 < len(documents):
            time.sleep(3)
    return len(documents)


def delete_document(filename: str) -> int:
    collection = _get_vectorstore()._collection
    results = collection.get(where={"filename": filename})
    if results and results["ids"]:
        collection.delete(ids=results["ids"])
        return len(results["ids"])
    return 0


def has_document_chunks(filename: str) -> bool:
    """Check if any chunks for this filename exist in ChromaDB."""
    collection = _get_vectorstore()._collection
    # Using get with limit=1 is very fast
    results = collection.get(where={"filename": filename}, limit=1)
    return bool(results and results["ids"])


def _call_llm_with_fallback(messages) -> tuple:
    """Try each provider in the fallback chain. Returns (response, provider_name)."""
    chain = get_fallback_chain()
    if not chain:
        raise Exception("No LLM providers configured. Add at least one API key to .env")

    last_error = None
    for provider in chain:
        try:
            print(f"[RAG] Trying provider: {provider}")
            llm = _create_llm(provider)
            response = llm.invoke(messages)
            print(f"[RAG] Success with: {provider}")
            return response, provider
        except Exception as e:
            last_error = str(e)
            print(f"[RAG] {provider} failed: {last_error[:100]}")
            if "401" in last_error or "invalid" in last_error.lower():
                continue  # Bad key, skip immediately
            time.sleep(1)
            continue

    raise Exception(f"All providers failed. Last error: {last_error}")


def _is_style_instruction(question: str) -> bool:
    """Detect if the user is asking to restyle/shorten/rephrase the last answer, not asking a new question."""
    import re
    patterns = [
        r'\b(\d+[-–]\d+|few|shorter|brief|concise|summarize|condense|shorten)\b.*\b(line|sentence|word|paragraph|point)',
        r'\b(line|sentence|word)\b.*\b(\d+)',
        r'\bmake (it|this|that)\b.*(short|brief|concise|smaller|compact)',
        r'\b(rephrase|rewrite|reformat|redo|simplify)\b',
        r'\bgive\b.*\b(short|brief|concise|\d+)',
        r'\bin\s+\d+\s*(line|sentence|word)',
        r'\bonly\s+\d+\s*(line|sentence|word)',
    ]
    q = question.lower().strip()
    return any(re.search(p, q) for p in patterns)


def _get_last_ai_answer(history: List[Dict[str, str]]) -> str:
    """Get the last assistant answer from history."""
    if not history:
        return ""
    for msg in reversed(history):
        if msg.get("role") in ("assistant", "ai"):
            return msg.get("content", "")
    return ""


def query_knowledge_base(question: str, history: List[Dict[str, str]] = None, top_k: int = 5) -> Dict:
    """Query the knowledge base with conversation history support."""
    
    # Check if this is a style/format instruction on the last answer
    if history and _is_style_instruction(question):
        last_answer = _get_last_ai_answer(history)
        if last_answer:
            print(f"[RAG] Detected style instruction: '{question}' — reformatting last answer")
            reformat_prompt = f"Here is a previous answer:\n\n{last_answer}\n\n---\n\nUser instruction: {question}\n\nRewrite the answer following the user's instruction. Keep all factual content. Use 'Locobuzz' as the company name. Output ONLY the rewritten answer."
            response, provider_used = _call_llm_with_fallback([
                SystemMessage(content="You reformat answers exactly as the user requests. Keep facts intact. Use 'Locobuzz' as the company name. Output only the rewritten answer, nothing else."),
                HumanMessage(content=reformat_prompt)
            ])
            import re
            answer = response.content
            answer = re.sub(r'\b[Tt]he [Pp]rovider\b', 'Locobuzz', answer)
            answer = re.sub(r'\b[Tt]he [Vv]endor\b', 'Locobuzz', answer)
            with _usage_lock:
                _usage["requests"] += 1
                _usage["last_provider"] = provider_used
                est_tokens = (len(reformat_prompt) + len(answer)) // 4
                _usage["tokens"] += est_tokens
                _usage["cost"] += (est_tokens / 1_000_000) * COST_PER_1M_TOKENS.get(provider_used, 0)
            return {"answer": answer, "sources": [], "confidence": "high", "provider": provider_used}

    # Normal flow: rephrase question if history exists
    standalone_question = question
    if history and len(history) > 0:
        h_text = ""
        for msg in history[-5:]: # Use last 5 turns
            role = msg.get("role", "user")
            content = msg.get("content", "")
            h_text += f"{role.capitalize()}: {content}\n"
        
        rephrase_prompt = (
            "Given the following conversation history and a NEW user message, determine if the new message "
            "is a follow-up question or a completely new, unrelated topic.\n\n"
            "1. If it is a FOLLOW-UP: Rephrase it into a standalone search query that includes the necessary context from history.\n"
            "2. If it is a NEW TOPIC: Simply return the new message as the query (ignore unrelated history).\n\n"
            "Only output the final query text. No explanations.\n\n"
            f"Conversation History:\n{h_text}\n"
            f"NEW Message: {question}"
        )
        
        try:
            print("[RAG] Rephrasing question for context...")
            rephrase_resp, _ = _call_llm_with_fallback([
                SystemMessage(content="You are a query optimizer that identifies if a user is asking a follow-up or starting a new topic."), 
                HumanMessage(content=rephrase_prompt)
            ])
            standalone_question = rephrase_resp.content.strip()
            print(f"[RAG] Rephrased query: {standalone_question}")
        except Exception as e:
            print(f"[RAG] Rephrasing failed: {str(e)}. Using original question.")

    # 2. Expand query for better retrieval — short questions miss relevant chunks
    expanded_query = standalone_question
    expansions = {
        "DR": "disaster recovery",
        "BCP": "business continuity plan",
        "VAPT": "vulnerability assessment penetration testing",
        "ISMS": "information security management system",
        "DLP": "data loss prevention",
        "MFA": "multi-factor authentication",
        "SSO": "single sign-on",
        "RBAC": "role-based access control",
    }
    for abbr, full in expansions.items():
        if abbr.lower() in standalone_question.lower() and full.lower() not in standalone_question.lower():
            expanded_query = f"{standalone_question} {full}"
            break

    # Retrieve more chunks than needed, then deduplicate by filename for diversity
    retrieval_k = max(top_k * 2, 10)
    all_docs = _get_vectorstore().as_retriever(search_kwargs={"k": retrieval_k}).invoke(expanded_query)

    # Deduplicate: keep best chunk per file, then fill remaining slots
    seen_files = {}
    for doc in all_docs:
        fname = doc.metadata.get("filename", "Unknown")
        if fname not in seen_files:
            seen_files[fname] = doc
    # Prioritize unique files, then add remaining by rank
    relevant_docs = list(seen_files.values())[:top_k]
    if len(relevant_docs) < top_k:
        for doc in all_docs:
            if doc not in relevant_docs:
                relevant_docs.append(doc)
            if len(relevant_docs) >= top_k:
                break

    if not relevant_docs:
        return {"answer": "I couldn't find relevant information in the knowledge base. Please upload relevant documents first.", "sources": [], "confidence": "low", "provider": None}

    context_parts, sources, seen = [], [], set()
    for doc in relevant_docs:
        context_parts.append(doc.page_content)
        name = doc.metadata.get("filename", "Unknown")
        if name not in seen:
            seen.add(name)
            sources.append({"filename": name, "chunk": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content})

    context = "\n\n---\n\n".join(context_parts)
    # Replace generic provider references in context so LLM doesn't echo them
    context = context.replace("the provider", "Locobuzz").replace("The provider", "Locobuzz").replace("the Provider", "Locobuzz").replace("The Provider", "Locobuzz")
    
    # 3. Pre-sanitize context to enforce naming (Locobuzz)
    # This ensures the LLM primarily sees 'Locobuzz' even if doc says 'the provider'
    context = context.replace("the provider", "Locobuzz").replace("The provider", "Locobuzz").replace("the Provider", "Locobuzz").replace("the vendor", "Locobuzz")
    
    # 4. Construct the full multi-turn prompt
    history_ctx = ""
    if history:
        for msg in history[-5:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_ctx += f"{role.capitalize()}: {content}\n"
    
    # Pre-sanitize everything else for strict enforcement
    history_ctx = history_ctx.replace("the provider", "Locobuzz").replace("The provider", "Locobuzz")
    safe_question = question.replace("the provider", "Locobuzz").replace("The provider", "Locobuzz").replace("provider", "Locobuzz")

    user_prompt = f"Previous Conversation:\n{history_ctx}\n\nContext from knowledge base:\n{context}\n\n---\n\nLatest Question: {safe_question}\n\nProvide a professional, accurate answer based on the context above and the conversation history. IMPORTANT: Always use 'Locobuzz' as the company name — never say 'the provider', 'the vendor', or 'the entity'."

    response, provider_used = _call_llm_with_fallback([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)])

    # Post-process: force replace any remaining "the provider" in the LLM output
    answer = response.content
    import re
    answer = re.sub(r'\b[Tt]he [Pp]rovider\b', 'Locobuzz', answer)
    answer = re.sub(r'\b[Tt]he [Vv]endor\b', 'Locobuzz', answer)
    answer = re.sub(r'\b[Tt]he [Ee]ntity\b', 'Locobuzz', answer)
    answer = re.sub(r'\b[Tt]he [Oo]rganization\b', 'Locobuzz', answer)
    answer = re.sub(r'\b[Tt]he [Oo]rganisation\b', 'Locobuzz', answer)
    # Fix "Yes.\n" or "No.\n" — merge into same line with comma
    answer = re.sub(r'^(Yes|No)[.,]?\s*\n+', r'\1, ', answer)
    # Strip meta-commentary that doesn't answer anything
    meta_patterns = [
        r"^(I'll make sure|Please go ahead|Go ahead and ask|What's your question|I'll ensure|Please ask|What would you like).*$",
    ]
    for pat in meta_patterns:
        if re.match(pat, answer.strip(), re.IGNORECASE):
            answer = "I need a specific InfoSec question to answer. Please ask about a security policy, compliance requirement, or control."

    # Track usage
    tokens = 0
    if hasattr(response, "response_metadata"):
        tokens = response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
    if tokens == 0:
        tokens = (len(SYSTEM_PROMPT) + len(user_prompt) + len(answer)) // 4

    with _usage_lock:
        _usage["requests"] += 1
        _usage["last_provider"] = provider_used
        _usage["tokens"] += tokens
        _usage["cost"] += (tokens / 1_000_000) * COST_PER_1M_TOKENS.get(provider_used, 0)

    confidence = "high" if len(relevant_docs) >= 3 else ("medium" if len(relevant_docs) >= 1 else "low")
    return {"answer": answer, "sources": sources, "confidence": confidence, "provider": provider_used}


def get_collection_stats() -> Dict:
    try:
        return {"total_chunks": _get_vectorstore()._collection.count(), "status": "ready"}
    except Exception as e:
        return {"total_chunks": 0, "status": f"error: {str(e)}"}
