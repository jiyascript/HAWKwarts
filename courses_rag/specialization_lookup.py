"""exact lookup """
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "specializations.json"


def list_specializations(parent_program_id: str) -> list[dict]:
    """List all specializations belonging to a degree program.

    Args:
        parent_program_id: Exact catalog program ID,
            e.g. computer-science:bs-bac-ba.
    """
    print(
        f"\n[TOOL] list_specializations("
        f"parent_program_id={parent_program_id})"
    )

    with DATA_PATH.open(encoding="utf-8") as file:
        records = json.load(file)

    matches = [
        {
            "id": record["id"],
            "name": record["name"],
            "parent_program_id": record["parent_program_id"],
            "credential": record["credential"],
            "url": record.get("url"),
        }
        for record in records
        if record.get("parent_program_id") == parent_program_id
    ]
    return sorted(matches, key=lambda record: record["name"])
