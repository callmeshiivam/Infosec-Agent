"""Smoke test — hit every endpoint to verify the system is healthy."""
import requests

BASE = "http://localhost:8000/api"
results = []

def test(name, fn):
    try:
        status, detail = fn()
        results.append((name, status, detail))
    except Exception as e:
        results.append((name, "FAIL", str(e)[:80]))

# 1. Health
def t_health():
    r = requests.get(f"{BASE}/health", timeout=5).json()
    ok = r["status"] == "healthy"
    return "PASS" if ok else "FAIL", f"Provider: {r['provider']}, Model: {r['model']}"

# 2. Doc list
def t_docs():
    docs = requests.get(f"{BASE}/documents/list", timeout=5).json()
    return "PASS", f"{len(docs)} documents"

# 3. Stats
def t_stats():
    s = requests.get(f"{BASE}/documents/stats", timeout=5).json()
    return "PASS", f"{s['total_documents']} docs, {s['total_chunks']} chunks"

# 4. Chat
def t_chat():
    r = requests.post(f"{BASE}/questionnaire/chat", json={"question": "What security policies exist?", "top_k": 3}, timeout=30).json()
    ok = len(r.get("answer", "")) > 10
    return "PASS" if ok else "FAIL", f"{len(r['answer'])} chars, {len(r['sources'])} sources, {r['confidence']}"

# 5. Frontend
def t_frontend():
    r = requests.get("http://localhost:5173", timeout=5)
    return "PASS" if r.status_code == 200 else "FAIL", f"HTTP {r.status_code}"

test("Health", t_health)
test("Doc List", t_docs)
test("Stats", t_stats)
test("Chat Query", t_chat)
test("Frontend", t_frontend)

print("\n" + "=" * 55)
print("  SMOKE TEST RESULTS")
print("=" * 55)
for name, status, detail in results:
    icon = "OK" if status == "PASS" else "XX"
    print(f"  [{icon}] {name:15s} {detail}")
print("=" * 55)
passed = sum(1 for _, s, _ in results if s == "PASS")
print(f"  {passed}/{len(results)} passed")
print("=" * 55)
