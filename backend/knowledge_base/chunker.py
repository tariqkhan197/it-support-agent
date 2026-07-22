"""
Text chunker for RAG ingestion.

Splits page text into overlapping chunks sized for embedding, preferring
to break on sentence/paragraph boundaries so chunks read coherently rather
than being cut mid-sentence.
"""

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """
    Split `text` into chunks of roughly `chunk_size` characters, with
    `chunk_overlap` characters of overlap between consecutive chunks so
    context isn't lost at chunk boundaries.

    Sentences are kept whole where possible: chunks are built by
    accumulating whole sentences until adding the next one would exceed
    chunk_size, then a new chunk starts, carrying back `chunk_overlap`
    characters worth of trailing sentences for continuity.
    """
    text = text.strip()
    if not text:
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    sentences = _SENTENCE_BOUNDARY.split(text)
    # Guard against pathological single "sentence" longer than chunk_size
    sentences = _split_oversized_sentences(sentences, chunk_size)

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence) + 1  # +1 for the joining space
        if current_length + sentence_length > chunk_size and current_sentences:
            chunk = " ".join(current_sentences).strip()
            chunks.append(chunk)
            current_sentences = _carry_over_overlap(current_sentences, chunk_overlap)
            current_length = sum(len(s) + 1 for s in current_sentences)

        current_sentences.append(sentence)
        current_length += sentence_length

    if current_sentences:
        chunks.append(" ".join(current_sentences).strip())

    return [c for c in chunks if c]


def _split_oversized_sentences(sentences: list[str], max_length: int) -> list[str]:
    """Hard-split any single 'sentence' that alone exceeds chunk_size (e.g. no punctuation in source)."""
    result: list[str] = []
    for sentence in sentences:
        if len(sentence) <= max_length:
            result.append(sentence)
            continue
        for i in range(0, len(sentence), max_length):
            result.append(sentence[i: i + max_length])
    return result


def _carry_over_overlap(sentences: list[str], overlap_chars: int) -> list[str]:
    """Return the trailing sentences (from the end) whose combined length is closest to overlap_chars."""
    carried: list[str] = []
    total = 0
    for sentence in reversed(sentences):
        if total >= overlap_chars:
            break
        carried.insert(0, sentence)
        total += len(sentence) + 1
    return carried
