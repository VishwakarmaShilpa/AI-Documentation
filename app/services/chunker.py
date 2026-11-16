def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    start = 0
    while start < len(text):
        piece = text[start:start + chunk_size].strip()
        if piece:
            chunks.append(piece)
        start += chunk_size - overlap
    return chunks
