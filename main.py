from __future__ import annotations

import json
from pathlib import Path

from agents.parser_agent import ProjectParser
from backend.database.models import Base
from backend.database.project_import import update_project_from_schema
from backend.database.session import create_engine_from_env, create_session_factory


DOCX_DIR = Path("data/project_documents")
OUTPUT_FILE = Path("data/batch_output.json")
PER_FILE_OUTPUT_DIR = Path("data/per_file_json")
MAX_DOCX_FILES = 4


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
    files = get_docx_files(DOCX_DIR)[:MAX_DOCX_FILES]
    results = []
    engine = create_engine_from_env()
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    for index, file_path in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] Читаю {file_path.name}")

        try:
            project_data_model = parser.parse(file_path)
            project_data = project_data_model.model_dump(mode="json")
            save_json(PER_FILE_OUTPUT_DIR / f"{file_path.stem}.json", project_data)

            with session_factory() as session:
                project = update_project_from_schema(session, project_data_model, file_path)
                project_id = project.id
                session.commit()

            results.append(
                {
                    "file": file_path.name,
                    "project_id": project_id,
                    "data": project_data,
                    "error": None,
                }
            )
        except Exception as exc:
            print(exc)
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

    save_json(OUTPUT_FILE, payload)

    print(f"Готово: {payload['processed']}/{payload['total']} файлов обработано")
    print(f"Общий JSON: {OUTPUT_FILE}")
    print(f"JSON по файлам: {PER_FILE_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
