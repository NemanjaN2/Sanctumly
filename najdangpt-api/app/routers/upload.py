"""Authenticated document upload and RAG ingestion."""
import csv
import io
import json
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

import PyPDF2
import docx
import openpyxl
import xlrd
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from app.database import get_db
from app.models.account import Account
from app.models.document import UserDocument
from app.security import require_user, sanitize_session_id
from app.security.conversations import authorize_conversation_session
from app.security.usage import is_creator_account, consume_quota
from app.services.rag import generate_embeddings, chunk_text
from app.config import MAX_FILE_SIZE, FREE_MAX_FILE_SIZE, MAX_EXTRACTED_DOCUMENT_CHARS, SUPPORTED_FILE_TYPES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["Upload"])


def _extract_document(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    text_content = ""
    if ext == "pdf":
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        text_content = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif ext == "txt":
        text_content = content.decode("utf-8", errors="replace")
    elif ext == "docx":
        document = docx.Document(io.BytesIO(content))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        text_content = "\n".join(parts)
    elif ext == "xlsx":
        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        parts = []
        for sheet in workbook.worksheets:
            parts.append(f"Sheet: {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                parts.append(" | ".join(str(cell) if cell is not None else "" for cell in row))
        text_content = "\n".join(parts)
        workbook.close()
    elif ext == "xls":
        workbook = xlrd.open_workbook(file_contents=content, on_demand=True)
        parts = []
        for sheet in workbook.sheets():
            parts.append(f"Sheet: {sheet.name}")
            for row_idx in range(sheet.nrows):
                parts.append(" | ".join(str(cell.value) for cell in sheet.row(row_idx)))
        text_content = "\n".join(parts)
        workbook.release_resources()
    elif ext == "csv":
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig", errors="replace")))
        text_content = "\n".join(" | ".join(row) for row in reader)
    elif ext == "epub":
        book = epub.read_epub(io.BytesIO(content))
        parts = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                parts.append(BeautifulSoup(item.get_content(), "html.parser").get_text("\n"))
        text_content = "\n".join(parts)
    else:
        raise HTTPException(status_code=415, detail="Unsupported document type")
    return text_content.strip()


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = "",
    account: Account = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Upload a document to the authenticated account's server-issued session."""
    clean_session_id = authorize_conversation_session(session_id, account, db)

    filename = (file.filename or "document").replace("\\", "/").split("/")[-1]
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_FILE_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported document type")

    creator = is_creator_account(account)
    max_size = MAX_FILE_SIZE if creator else FREE_MAX_FILE_SIZE
    content = await file.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {max_size // (1024 * 1024)}MB")
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")

    try:
        text_content = _extract_document(filename, content)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Document extraction failed for %s (%s)", filename, type(exc).__name__)
        raise HTTPException(status_code=400, detail="Could not read this document. Check that the file is valid.")

    if not text_content:
        raise HTTPException(status_code=400, detail="No readable text was found in this document")
    if not creator and len(text_content) > MAX_EXTRACTED_DOCUMENT_CHARS:
        raise HTTPException(status_code=413, detail="Document contains too much extracted text for the free plan")

    if not creator:
        consume_quota(account, db, "document_uploads", 1)

    chunks = chunk_text(text_content)
    logger.info("Processing document %s for %s: %s chunks / %s chars", filename, account.username, len(chunks), len(text_content))

    try:
        embeddings = generate_embeddings(chunks, batch_size=32)
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            db.add(UserDocument(
                session_id=clean_session_id,
                filename=filename[:500],
                chunk_index=index,
                content=chunk,
                embedding=json.dumps(embedding) if embedding else None,
            ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Document persistence failed for %s", filename)
        raise HTTPException(status_code=500, detail="Document processing failed")

    return {"success": True, "filename": filename, "chunks": len(chunks), "size": len(text_content)}
