# src/core/sync_raw_and_metadata.py

from pathlib import Path
import pandas as pd


# Resolve project root dynamically (repo-root/src/core/ -> repo-root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIR = PROJECT_ROOT / "projects"

DRY_RUN = False

ALLOWED_EXTS = {".pdf", ".txt", ".md"}


def get_prefix(project_name: str) -> str:
    return project_name.upper()[:6]


def sync_project(project_path: Path):
    raw_dir = project_path / "data" / "raw"
    metadata_path = project_path / "data" / "metadata.xlsx"

    print(f"\n▶ Syncing project: {project_path.name}")

    if not raw_dir.exists():
        print("  ↪ Skipped: no raw directory")
        return

    files = [
        f for f in raw_dir.iterdir()
        if f.is_file()
        and not f.name.startswith(".")
        and f.suffix.lower() in ALLOWED_EXTS
    ]

    print(f"  • Raw files detected ({len(files)}): {[f.name for f in files]}")

    if not files:
        print("  ↪ Skipped: no raw files")
        return

    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing metadata.xlsx in {project_path}")

    prefix = get_prefix(project_path.name)

    # Load metadata
    df = pd.read_excel(metadata_path)

    # Validate metadata schema: first column must be 'doc_id'
    if df.columns[0].lower() != "doc_id":
        raise ValueError(
            f"First column must be 'doc_id' in {metadata_path}"
        )

    # Ensure 'found' column exists
    if "found" not in df.columns:
        df["found"] = 0

    # Ensure 'local_path' column exists
    if "local_path" not in df.columns:
        df["local_path"] = ""

    doc_id_col = df.columns[0]

    if df.empty:
        existing_ids = set()
    else:
        existing_ids = set(df[doc_id_col].dropna().astype(str))

    existing_numbers = []
    for f in raw_dir.iterdir():
        if (
            not f.is_file()
            or f.name.startswith(".")
            or f.suffix.lower() not in ALLOWED_EXTS
        ):
            continue
        stem = f.stem
        if stem.startswith(prefix + "_"):
            parts = stem.split("_")
            if len(parts) == 2 and parts[1].isdigit():
                existing_numbers.append(int(parts[1]))
    counter = max(existing_numbers, default=0) + 1
    for file in sorted(files):
        ext = file.suffix.lower()

        # Skip already-renamed files
        if file.stem.startswith(prefix):
            continue

        doc_id = f"{prefix}_{counter:03d}"
        new_path = raw_dir / f"{doc_id}{ext}"

        # Avoid collisions
        while new_path.exists():
            counter += 1
            doc_id = f"{prefix}_{counter:03d}"
            new_path = raw_dir / f"{doc_id}{ext}"

        if DRY_RUN:
            print(f"  [DRY RUN] Would rename {file.name} → {new_path.name}")
        else:
            file.rename(new_path)
        counter += 1

    # Add missing doc_ids to metadata based on actual raw files
    raw_files = [
        f for f in raw_dir.iterdir()
        if f.is_file()
        and not f.name.startswith(".")
        and f.suffix.lower() in ALLOWED_EXTS
    ]
    new_rows = []

    for f in raw_files:
        doc_id = f.stem
        if doc_id not in existing_ids:
            new_rows.append({
                doc_id_col: doc_id,
                "found": 1,
                "local_path": str(f.resolve())
            })

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    # Recompute found flags based on actual raw files
    raw_doc_ids = {
        f.stem for f in raw_dir.iterdir()
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTS
    }
    df["found"] = (
        df[doc_id_col]
        .astype(str)
        .isin(raw_doc_ids)
        .fillna(False)
        .astype(int)
    )

    # Update local_path for all found docs
    for f in raw_dir.iterdir():
        if f.is_file():
            df.loc[
                df[doc_id_col].astype(str) == f.stem,
                "local_path"
            ] = str(f.resolve())

    if len(df) != len(raw_files):
        print(
            f"  ⚠ Warning: metadata rows ({len(df)}) "
            f"!= raw files ({len(raw_files)})"
        )

    df.to_excel(metadata_path, index=False)

    print(f"  ✔ Synced {project_path.name}: {df['found'].sum()} files found")


def main():
    for project in PROJECTS_DIR.iterdir():
        if project.is_dir():
            sync_project(project)


if __name__ == "__main__":
    main()