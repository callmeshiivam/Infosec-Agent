"""
Questionnaire Router - Chat queries and Excel questionnaire processing.
"""
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from services import rag_engine, document_loader, excel_processor

router = APIRouter()
EXPORTS_DIR = Path(__file__).parent.parent / "data" / "exports"


class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Dict[str, str]]] = None
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict]
    confidence: str


class ExcelColumnsResponse(BaseModel):
    columns: List[Dict[str, str]]
    preview: List[Dict[str, str]]
    filename: str


@router.post("/chat", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        result = rag_engine.query_knowledge_base(request.question, history=request.history, top_k=request.top_k)
        return ChatResponse(answer=result["answer"], sources=result["sources"], confidence=result["confidence"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying knowledge base: {str(e)}")


@router.post("/excel/upload", response_model=ExcelColumnsResponse)
async def upload_excel(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Only .xlsx/.xls files supported.")

    temp_path = EXPORTS_DIR / f"temp_{file.filename}"
    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        columns = document_loader.get_excel_columns(str(temp_path))
        preview = document_loader.get_excel_preview(str(temp_path), max_rows=5)
        return ExcelColumnsResponse(columns=columns, preview=preview, filename=f"temp_{file.filename}")
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error reading Excel file: {str(e)}")


@router.post("/excel/process")
async def process_excel(
    filename: str = Form(...),
    question_column: str = Form(...),
    answer_column: str = Form(...),
    start_row: int = Form(2),
    confidence_column: Optional[str] = Form(None),
    source_column: Optional[str] = Form(None),
):
    file_path = EXPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Excel file not found. Please upload again.")
    try:
        result = excel_processor.process_excel_questionnaire(
            file_path=str(file_path),
            question_column=question_column,
            answer_column=answer_column,
            start_row=start_row,
            confidence_column=confidence_column or None,
            source_column=source_column or None,
        )
        return {"output_filename": result["output_filename"], "total_questions": result["total_questions"], "answered": result["answered"], "results": result["results"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Excel: {str(e)}")


@router.get("/excel/download/{filename}")
async def download_excel(filename: str):
    file_path = EXPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path=str(file_path), filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
