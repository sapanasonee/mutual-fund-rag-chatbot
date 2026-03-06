"""Text cleaning and chunking utilities per architecture (HTML stripping, boilerplate removal, 300-500 token chunks with overlap)."""
from __future__ import annotations

import re
from typing import List


def clean_html(raw: str) -> str:
    """Strip HTML tags and common boilerplate. Idempotent for plain text."""
    if not raw:
        return ""
    text = raw
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^\s*(cookie|privacy|terms|disclaimer)\s*[\:\-]\s*", " ", text, flags=re.IGNORECASE)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size_tokens: int = 400,
    overlap_tokens: int = 50,
) -> List[str]:
    """
    Split text into chunks of ~chunk_size_tokens with overlap_tokens overlap.
    Uses word count as a token approximation (~1 word ≈ 1 token for English).
    """
    if not text or not text.strip():
        return []
    words = text.split()
    if len(words) <= chunk_size_tokens:
        return [text] if text.strip() else []
    step = max(1, chunk_size_tokens - overlap_tokens)
    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size_tokens, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(words):
            break
        start += step
    return chunks
