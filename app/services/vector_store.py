import numpy as np
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Document, Chunk


def add_document(doc_id: str, user_id: int, filename: str, chunks: list[str], vectors: list[list[float]]):
    arr = np.array(vectors, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)  # normalize for cosine similarity

    with SessionLocal() as db:
        db.add(Document(id=doc_id, user_id=user_id, filename=filename))
        for i, (text, vec) in enumerate(zip(chunks, arr)):
            db.add(Chunk(document_id=doc_id, chunk_index=i, text=text, embedding=vec.tobytes()))
        db.commit()


def search(user_id: int, doc_id: str | None, query_vector: list[float], top_k: int = 3):
    with SessionLocal() as db:
        if doc_id is None:  # default to this user's most recent upload
            doc_id = db.scalars(
                select(Document.id)
                .where(Document.user_id == user_id)
                .order_by(Document.created_at.desc())
                .limit(1)
            ).first()
            if doc_id is None:
                return None
        else:  # the document must belong to this user
            owned = db.scalars(
                select(Document.id).where(Document.id == doc_id, Document.user_id == user_id)
            ).first()
            if owned is None:
                return None

        rows = db.execute(
            select(Chunk.chunk_index, Chunk.text, Chunk.embedding)
            .where(Chunk.document_id == doc_id)
            .order_by(Chunk.chunk_index)
        ).all()

    if not rows:
        return None

    matrix = np.vstack([np.frombuffer(r.embedding, dtype=np.float32) for r in rows])
    q = np.array(query_vector, dtype=np.float32)
    q /= np.linalg.norm(q)

    scores = matrix @ q
    best = np.argsort(scores)[::-1][:top_k]

    return [
        {
            "chunk_index": rows[i].chunk_index,
            "score": round(float(scores[i]), 4),
            "text": rows[i].text,
        }
        for i in best
    ]
