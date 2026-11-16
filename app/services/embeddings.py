import math
import os

from google import genai
from google.genai import types

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768

_client = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = []
    for i in range(0, len(texts), 100):  # API limit: 100 texts per request
        batch = texts[i : i + 100]
        result = get_client().models.embed_content(
            model=EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM),
        )
        for e in result.embeddings:
            norm = math.sqrt(sum(x * x for x in e.values)) or 1.0
            vectors.append([x / norm for x in e.values])
    return vectors