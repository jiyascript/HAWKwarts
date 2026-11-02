import sys
from pathlib import Path
from typing import Any

TRANSCRIPT_DIR = Path(__file__).resolve().parents[1] / "backend" / "transcript"

if str(TRANSCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(TRANSCRIPT_DIR))

from transcript_parser import parse_transcript
def load_student_transcript(pdf_path: str) -> dict[str, Any]:
    path = Path(pdf_path).expanduser().resolve()

    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ValueError("A valid transcript PDF is required.")

    return parse_transcript(str(path))


def summarize_transcript(history: dict) -> dict:
    """Return structured course history without unnecessary personal details."""
    return {
        "completed_courses": history.get("completed_courses", []),
        "transfer_courses": history.get("transfer_courses", []),
        "in_progress_courses": history.get("in_progress_courses", []),
        "all_institution_records": history.get("all_institution_records", []),
        "scheduler_course_codes": history.get("scheduler_course_codes", []),
        "warnings": history.get("warnings", []),
    }
