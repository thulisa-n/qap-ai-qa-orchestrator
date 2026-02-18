from pathlib import Path

from app.src.schemas import FileItem


def write_playwright_files(files: list[FileItem]) -> list[str]:
    base_dir = (Path(__file__).resolve().parent.parent.parent / "playwright-tests").resolve()
    created_files: list[str] = []

    for file_item in files:
        path = (base_dir / file_item.path).resolve()
        # Defense-in-depth against path traversal even after schema validation.
        if not str(path).startswith(str(base_dir)):
            raise ValueError("Resolved path escapes playwright-tests directory")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file_item.content, encoding="utf-8")
        created_files.append(str(path))

    return created_files
