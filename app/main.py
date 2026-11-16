import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select

from app.database import engine, Base, SessionLocal
from app import models
from app.auth import router as auth_router, get_current_user
from app.models import User
from app.services.pdf_parser import extract_text
from app.services.chunker import chunk_text
from app.services.embeddings import embed_texts
from app.services import vector_store
from app.services.llm import answer_question

app = FastAPI(title="Doc QA App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)  # creates the tables on first run
app.include_router(auth_router)

MIN_SCORE = 0.2  # below this, the document probably doesn't contain the answer


class SearchRequest(BaseModel):
    doc_id: str | None = None
    question: str
    top_k: int = 3


class AskRequest(BaseModel):
    doc_id: str | None = None
    question: str
    top_k: int = 4


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    data = await file.read()
    text = extract_text(data)

    if not text:
        raise HTTPException(status_code=422, detail="No text found. Is this a scanned PDF?")

    chunks = chunk_text(text)
    vectors = embed_texts(chunks)

    doc_id = str(uuid.uuid4())
    vector_store.add_document(doc_id, user.id, file.filename, chunks, vectors)

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "characters": len(text),
        "num_chunks": len(chunks),
        "vector_size": len(vectors[0]),
    }


@app.get("/documents")
def list_documents(user: User = Depends(get_current_user)):
    with SessionLocal() as db:
        docs = db.scalars(
            select(models.Document)
            .where(models.Document.user_id == user.id)
            .order_by(models.Document.created_at.desc())
        ).all()
        return [{"doc_id": d.id, "filename": d.filename, "uploaded": d.created_at} for d in docs]


@app.post("/search")
def search(req: SearchRequest, user: User = Depends(get_current_user)):
    query_vector = embed_texts([req.question])[0]
    results = vector_store.search(user.id, req.doc_id, query_vector, req.top_k)

    if results is None:
        raise HTTPException(status_code=404, detail="Document not found. Upload it again.")

    return {"question": req.question, "results": results}


@app.post("/ask")
def ask(req: AskRequest, user: User = Depends(get_current_user)):
    query_vector = embed_texts([req.question])[0]
    results = vector_store.search(user.id, req.doc_id, query_vector, req.top_k)

    if results is None:
        raise HTTPException(status_code=404, detail="Document not found. Upload it again.")

    if results[0]["score"] < MIN_SCORE:
        return {"answer": "I couldn't find that in the document.", "sources": []}

    try:
        answer = answer_question(req.question, [r["text"] for r in results])
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")

    return {"answer": answer, "sources": results}
