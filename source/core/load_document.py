from pathlib import Path
import re
import fitz  # PyMuPDF


SUPPORTED_EXTS = {".pdf", ".txt", ".md"}


def load_document(project_root: Path, doc_id: str) -> dict:
    """
    Load a document by doc_id from a project vault.

    Prefer processed files over raw.
    Always return page-level provenance.
    """
    processed_dir = project_root / "data" / "processed"
    raw_dir = project_root / "data" / "raw"

    source_quality = "auto"

    # 1. Prefer processed files
    processed_matches = []
    if processed_dir.exists():
        processed_matches = (
            list(processed_dir.glob(f"{doc_id}.md")) +
            list(processed_dir.glob(f"{doc_id}.txt"))
        )

    if processed_matches:
        file_path = processed_matches[0]
        source_quality = "manual"
    else:
        raw_matches = list(raw_dir.glob(f"{doc_id}.*"))
        if not raw_matches:
            raise FileNotFoundError(f"No file found for doc_id: {doc_id}")
        if len(raw_matches) > 1:
            raise ValueError(f"Multiple raw files found for doc_id: {doc_id}")
        file_path = raw_matches[0]

    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise ValueError(f"Unsupported file type: {ext}")

    # 2. Load content
    if ext == ".pdf":
        pages = _load_pdf(file_path)
    else:
        pages = _load_text(file_path)

    full_text = "\n\n".join(p["text"] for p in pages)

    return {
        "doc_id": doc_id,
        "source_path": str(file_path.resolve()),
        "file_type": ext.lstrip("."),
        "source_quality": source_quality,
        "pages": pages,
        "full_text": full_text,
    }


def _load_pdf(path: Path) -> list[dict]:
    """
    Load PDF with page-level text extraction.
    Page numbers correspond to PDF pages.
    """
    doc = fitz.open(path)
    pages = []

    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if not text:
            continue

        pages.append({
            "page": i,
            "text": text
        })

    doc.close()
    return pages


def _load_text(path: Path, block_size: int = 1000) -> list[dict]:
    """
    Load TXT/MD files.

    If [[PAGE X]] markers exist:
      - split strictly on them
      - use X as page number (journal page)

    Otherwise:
      - fall back to block-size paging
    """
    content = path.read_text(encoding="utf-8", errors="ignore")

    page_pattern = re.compile(r"\[\[\s*PAGE\s+(\d+)\s*\]\]", re.IGNORECASE)
    matches = list(page_pattern.finditer(content))

    pages = []

    # Case 1: Explicit page markers → authoritative
    if matches:
        for idx, match in enumerate(matches):
            page_num = int(match.group(1))
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            page_text = content[start:end].strip()

            if page_text:
                pages.append({
                    "page": page_num,
                    "text": page_text
                })

        return pages

    # Case 2: No markers → fallback block paging
    blocks = []
    current = ""
    page = 1

    for line in content.splitlines():
        current += line + "\n"
        if len(current) >= block_size:
            blocks.append({
                "page": page,
                "text": current.strip()
            })
            current = ""
            page += 1

    if current.strip():
        blocks.append({
            "page": page,
            "text": current.strip()
        })

    return blocks