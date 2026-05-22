from __future__ import annotations

import json
from pathlib import Path

from agents.parser_agent import ProjectParser


DOCX_DIR = Path("data/project_documents")
PER_FILE_OUTPUT_DIR = Path("data/per_file_json")


def get_docx_files(folder: Path) -> list[Path]:
    files = sorted(
        file_path
        for file_path in folder.glob("*.docx")
        if not file_path.name.startswith("~$")
    )
    if not files:
        raise FileNotFoundError(f"В папке нет DOCX-файлов: {folder}")
    return files


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = ProjectParser()
    files = get_docx_files(DOCX_DIR)
    results = []

    for index, file_path in enumerate(files, start=1):
        if index == 5:
            break
        print(f"[{index}/{len(files)}] Читаю {file_path.name}")

        try:
            project_data = parser.parse(file_path).model_dump(mode="json")
            save_json(PER_FILE_OUTPUT_DIR / f"{file_path.stem}.json", project_data)
            results.append(
                {
                    "file": file_path.name,
                    "data": project_data,
                    "error": None,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "file": file_path.name,
                    "data": None,
                    "error": str(exc),
                }
            )

    failed = sum(1 for item in results if item["error"])
    payload = {
        "source": str(DOCX_DIR),
        "total": len(results),
        "processed": len(results) - failed,
        "failed": failed,
        "items": results,
    }

    print(f"Готово: {payload['processed']}/{payload['total']} файлов обработано")
    print(f"JSON по файлам: {PER_FILE_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
