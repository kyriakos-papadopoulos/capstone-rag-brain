# src/core/normalize_document.py

from collections import Counter
import re
from copy import deepcopy


# -----------------------------
# Public API
# -----------------------------

def normalize_document(
    document: dict,
    header_footer_threshold: float = 0.6,
    top_n: int = 2,
    bottom_n: int = 2,
    drop_table_like_pages: bool = False,
) -> dict:
    """
    Normalize a loaded document for retrieval.

    - Fix whitespace & hyphenation
    - Detect and remove repeated headers/footers
    - Flag table-like pages
    - Preserve page provenance

    Returns a NEW document dict (does not mutate input).
    """

    doc = deepcopy(document)
    pages = doc["pages"]

    # 1. Character-level normalization
    for p in pages:
        p["text"] = normalize_whitespace(p["text"])
        p["text"] = fix_hyphenation(p["text"])

    # 2. Detect headers / footers (repeated lines)
    repeated_lines = detect_repeated_lines(
        pages,
        top_n=top_n,
        bottom_n=bottom_n,
        threshold=header_footer_threshold,
    )

    # 3. Remove headers / footers
    for p in pages:
        p["text"] = remove_lines(p["text"], repeated_lines)

    # 4. Flag table-like pages BEFORE reflow (layout-sensitive)
    for p in pages:
        p["is_table_like"] = is_table_like(p["text"])

    # 5. Reflow text for ALL pages (coherence-first)
    for p in pages:
        p["text"] = reflow_lines(p["text"])

    # 5. Optionally drop table-heavy pages from retrieval
    if drop_table_like_pages:
        doc["pages"] = [p for p in pages if not p["is_table_like"]]

    # 6. Recompute full text
    doc["full_text"] = "\n\n".join(p["text"] for p in doc["pages"] if p["text"].strip())

    return doc


# -----------------------------
# Normalization helpers
# -----------------------------

def normalize_whitespace(text: str) -> str:
    """
    Normalize PDF whitespace artifacts conservatively.
    """
    return (
        text
        .replace("\xa0", " ")   # non-breaking space
        .replace("\u2009", " ") # thin space
        .replace("\u2002", " ") # en space
        .replace("\u00ad", "")  # soft hyphen
    )


def fix_hyphenation(text: str) -> str:
    """
    Fix word breaks caused by hyphenation across line breaks.

    Example:
        coopeti-\n tion -> coopetition
    """
    return re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)


def reflow_lines(text: str) -> str:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    reflowed = []
    for p in paragraphs:
        single_line = " ".join(p.splitlines())
        single_line = re.sub(r"\s+", " ", single_line)
        reflowed.append(single_line.strip())
    return "\n\n".join(reflowed)


# -----------------------------
# Header / footer detection
# -----------------------------

def detect_repeated_lines(
    pages: list,
    top_n: int,
    bottom_n: int,
    threshold: float,
) -> set:
    """
    Detect lines that appear repeatedly at the top or bottom of pages.
    """
    candidate_lines = []

    for p in pages:
        lines = [l.strip() for l in p["text"].splitlines() if l.strip()]
        candidate_lines.extend(lines[:top_n])
        candidate_lines.extend(lines[-bottom_n:])

    counts = Counter(candidate_lines)
    total_pages = max(len(pages), 1)

    return {
        line
        for line, count in counts.items()
        if count / total_pages >= threshold
    }


def remove_lines(text: str, lines_to_remove: set) -> str:
    """
    Remove exact matching lines from text.
    """
    cleaned_lines = []
    for line in text.splitlines():
        if line.strip() not in lines_to_remove:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


# -----------------------------
# Table detection (heuristic)
# -----------------------------

def is_table_like(text: str) -> bool:
    """
    Heuristic to detect table-heavy pages.

    Flags pages with:
    - many short lines
    - low sentence density
    """
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return False

    short_lines = [l for l in lines if len(l.strip()) < 40]
    ratio = len(short_lines) / len(lines)

    return ratio > 0.6