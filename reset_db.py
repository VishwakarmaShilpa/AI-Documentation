from sqlalchemy import text
from app.database import engine

with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS chunks, documents, users CASCADE"))
print("tables dropped")
