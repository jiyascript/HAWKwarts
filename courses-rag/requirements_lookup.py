
"""Exact lookup of academic requirements from scraped catalog data."""

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

DATASETS = {
    "program": "program_requirements.json",
    "minor": "minor_requirements.json",
    "specialization": "specializations.json",
}


@lru_cache(maxsize=None)
def load_dataset(kind: str) -> list[dict]:
    """Load and cache a requirements dataset."""
    if kind not in DATASETS:
        raise ValueError(f"Unknown requirement type: {kind}")

    path = DATA_DIR / DATASETS[kind]
    return json.loads(path.read_text())


def get_requirements(kind: str, record_id: str) -> dict | None:
    """Retrieve a complete requirement record by its exact ID."""
    records = load_dataset(kind)
    id_fields = {
        "program": "program_id",
        "minor": "id",
        "specialization": "id",
    }
    if kind not in id_fields:
        raise ValueError(f"Unknown requirement type: {kind}")
    if kind == "program":
        if record_id. startswith("program:"):
            record_id = record_id.removeprefix("program:")
        record_id = record_id.split(":section:")[0]

    elif kind == "minor":
        if record_id.startswith("minor:"):
            record_id = record_id.removeprefix("minor:")

    elif kind == "specialization":
        if record_id.startswith("specialization:"):
            record_id = record_id.removeprefix("specialization:")

    id_field = id_fields[kind]

    for record in records:
        if record.get(id_field) == record_id:
            return record

    return None

