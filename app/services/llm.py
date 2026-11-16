import os
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
_client = None


def get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")
        _client = genai.Client(api_key=key)
    return _client


def answer_question(question: str, chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(chunks)
    prompt = f"""You are a helpful assistant answering questions about a document.
Use ONLY the context below. If the answer is not in the context, say
"I couldn't find that in the document." Keep the answer clear and short.

Context:
{context}

Question: {question}

Answer:"""
    response = get_client().models.generate_content(model=MODEL, contents=prompt)
    return response.text