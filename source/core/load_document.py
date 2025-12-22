from pathlib import Path
import fitz  # PyMuPDF


SUPPORTED_EXTS = {".pdf", ".txt", ".md"}


def load_document(project_root: Path, doc_id: str) -> dict:
    """
    Load a document by doc_id from a project vault.

    Returns a normalized document object with page-level provenance.
    """
    raw_dir = project_root / "data" / "raw"

    # Locate file
    matches = list(raw_dir.glob(f"{doc_id}.*"))
    if not matches:
        raise FileNotFoundError(f"No raw file found for doc_id: {doc_id}")
    if len(matches) > 1:
        raise ValueError(f"Multiple files found for doc_id: {doc_id}")

    file_path = matches[0]
    ext = file_path.suffix.lower()

    if ext not in SUPPORTED_EXTS:
        raise ValueError(f"Unsupported file type: {ext}")

    if ext == ".pdf":
        pages = _load_pdf(file_path)
    elif ext in {".txt", ".md"}:
        pages = _load_text(file_path)
    else:
        raise ValueError(f"Unhandled extension: {ext}")

    full_text = "\n\n".join(p["text"] for p in pages)

    return {
        "doc_id": doc_id,
        "source_path": str(file_path.resolve()),
        "file_type": ext.lstrip("."),
        "pages": pages,
        "full_text": full_text,
    }


def _load_pdf(path: Path) -> list[dict]:
    """
    Load PDF with page-level text extraction.
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
    Load TXT/MD files and split into logical blocks.
    """
    content = path.read_text(encoding="utf-8", errors="ignore")
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