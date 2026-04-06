"""
Documents Router - Upload, list, and delete knowledge base documents.
Uses Supabase Storage for persistent file storage (survives redeploys).
"""
import os
import tempfile
from pathlib import Path
from typing import List
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from supabase import create_client
from services import document_loader, rag_engine

router = APIRouter()
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".mp4", ".mov"}
BUCKET = "documents"

def _get_supabase():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))


class DocumentInfo(BaseModel):
    filename: str
    size_bytes: int
    uploaded_at: str
    file_type: str


class UploadResponse(BaseModel):
    filename: str
    chunks_created: int
    message: str


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported: {suffix}")

    content = await file.read()
    sb = _get_supabase()

    # Save to temp file for text extraction
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = document_loader.extract_text(tmp_path)
        if not text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from this file.")

        # Upload to Supabase Storage
        sb.storage.from_(BUCKET).upload(file.filename, content, {"content-type": "application/octet-stream", "upsert": "true"})

        # Ingest into Pinecone
        metadata = {"filename": file.filename, "file_type": suffix, "uploaded_at": datetime.now().isoformat()}
        chunks = rag_engine.ingest_document(text, metadata)
        return UploadResponse(filename=file.filename, chunks_created=chunks, message=f"Processed '{file.filename}' into {chunks} chunks.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        os.unlink(tmp_path)


@router.get("/list", response_model=List[DocumentInfo])
async def list_documents():
    sb = _get_supabase()
    try:
        files = sb.storage.from_(BUCKET).list()
        return [
            DocumentInfo(
                filename=f["name"],
                size_bytes=f.get("metadata", {}).get("size", 0),
                uploaded_at=f.get("created_at", datetime.now().isoformat()),
                file_type="." + f["name"].rsplit(".", 1)[-1].lower() if "." in f["name"] else "",
            )
            for f in files if f.get("name")
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


@router.delete("/delete/{filename}")
async def delete_document(filename: str):
    sb = _get_supabase()
    chunks_deleted = rag_engine.delete_document(filename)
    try:
        sb.storage.from_(BUCKET).remove([filename])
    except:
        pass
    return {"message": f"Deleted '{filename}' and {chunks_deleted} chunks.", "chunks_deleted": chunks_deleted}


@router.delete("/delete_all")
async def delete_all_documents():
    sb = _get_supabase()
    try:
        files = sb.storage.from_(BUCKET).list()
        names = [f["name"] for f in files if f.get("name")]
        if names:
            sb.storage.from_(BUCKET).remove(names)
        # Note: Pinecone delete-all requires deleting the index — skip for now
        return {"message": f"Deleted {len(names)} documents.", "files_deleted": len(names)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/stats")
async def get_stats():
    sb = _get_supabase()
    try:
        files = sb.storage.from_(BUCKET).list()
        file_count = len([f for f in files if f.get("name")])
    except:
        file_count = 0
    vector_stats = rag_engine.get_collection_stats()
    return {"total_documents": file_count, "total_chunks": vector_stats["total_chunks"], "status": vector_stats["status"]}


@router.get("/download/{filename}")
async def download_document(filename: str):
    sb = _get_supabase()
    try:
        data = sb.storage.from_(BUCKET).download(filename)
        return Response(content=data, media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")
