"""
Documents Router - Upload, list, and delete knowledge base documents.
"""
from pathlib import Path
from typing import List
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from services import document_loader, rag_engine

router = APIRouter()
UPLOADS_DIR = Path(__file__).parent.parent / "data" / "uploads"
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md", ".csv",
    ".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif",
    ".mp4", ".mov"
}


class DocumentInfo(BaseModel):
    filename: str
    size_bytes: int
    uploaded_at: str
    file_type: str


class UploadResponse(BaseModel):
    filename: str
    chunks_created: int
    message: str
    status: str = "processed"  # "processed", "skipped", "error"


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    file_path = UPLOADS_DIR / file.filename
    # Smart Skip: If file exists and is already indexed, skip it.
    if file_path.exists() and rag_engine.has_document_chunks(file.filename):
        return UploadResponse(filename=file.filename, chunks_created=0, message=f"'{file.filename}' is already indexed. Skipping.", status="skipped")

    # If it was a previously failed file, just overwrite it
    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())

        text = document_loader.extract_text(str(file_path))
        if not text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from this file.")

        metadata = {"filename": file_path.name, "original_filename": file.filename, "file_type": suffix, "uploaded_at": datetime.now().isoformat()}
        chunks = rag_engine.ingest_document(text, metadata)
        return UploadResponse(filename=file_path.name, chunks_created=chunks, message=f"Processed '{file_path.name}' into {chunks} chunks.")
    except HTTPException:
        raise
    except Exception as e:
        try:
            if file_path.exists():
                file_path.unlink()
        except PermissionError:
            pass  # Windows file lock — file will be cleaned up later
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.get("/list", response_model=List[DocumentInfo])
async def list_documents():
    return [
        DocumentInfo(
            filename=f.name,
            size_bytes=f.stat().st_size,
            uploaded_at=datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            file_type=f.suffix.lower(),
        )
        for f in sorted(UPLOADS_DIR.iterdir())
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    ]


@router.delete("/delete_all")
async def delete_all_documents():
    chunks_deleted = 0
    files_deleted = 0
    for f in UPLOADS_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
            chunks_deleted += rag_engine.delete_document(f.name)
            f.unlink()
            files_deleted += 1
    return {"message": f"Successfully deleted {files_deleted} documents and {chunks_deleted} vector chunks.", "files_deleted": files_deleted, "chunks_deleted": chunks_deleted}

@router.delete("/delete/{filename}")
async def delete_document(filename: str):
    file_path = UPLOADS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")
    chunks_deleted = rag_engine.delete_document(filename)
    file_path.unlink()
    return {"message": f"Deleted '{filename}' and {chunks_deleted} chunks.", "chunks_deleted": chunks_deleted}


@router.get("/stats")
async def get_stats():
    stats = rag_engine.get_collection_stats()
    file_count = len([f for f in UPLOADS_DIR.iterdir() if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS])
    return {"total_documents": file_count, "total_chunks": stats["total_chunks"], "status": stats["status"]}


@router.get("/download/{filename}")
async def download_document(filename: str):
    """Download a document from the knowledge base."""
    file_path = UPLOADS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")
    return FileResponse(path=str(file_path), filename=filename, media_type="application/octet-stream")
