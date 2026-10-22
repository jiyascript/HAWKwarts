import json
import time
from collections import Counter
from pathlib import Path

import requests
from bs4 import BeautifulSoup


DATA_DIR = Path(__file__).parent / "data"
PROGRAMS_PATH = DATA_DIR / "programs.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; iit-catalog-rag/1.0)"
}


def clean_text(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def row_values(row):
    return [
        clean_text(cell.get_text(" ", strip=True))
        for cell in row.find_all(["th", "td"])
        if clean_text(cell.get_text(" ", strip=True))
    ]


def classify_table(table):
    rows = table.find_all("tr")

    if not rows:
        return "empty"

    header = " ".join(row_values(rows[0])).lower()

    all_rows = [
        row_values(row)
        for row in rows
    ]

    all_rows = [r for r in all_rows if r]

    has_code_title_credits = (
        "code" in header
        and "title" in header
        and "credit hours" in header
    )

    has_requirement_credits = (
        "requirement" in header
        and "credits" in header
    )

    has_total = any(
        r[0].lower().startswith("total credit hours")
        for r in all_rows
    )

    has_select = any(
        r[0].lower().startswith(("select", "please select", "choose"))
        for r in all_rows
    )

    if has_code_title_credits and has_total:
        return "curriculum_with_total"

    if has_requirement_credits:
        return "credit_summary"

    if has_code_title_credits and has_select:
        return "course_table_with_selection"

    if has_code_title_credits:
        return "course_list"

    return "other"


def classify_page(table_types):
    if not table_types:
        return "no_tables"

    counts = Counter(table_types)

    if counts["curriculum_with_total"]:
        return "single_authoritative_curriculum"

    if (
        counts["credit_summary"] >= 2
        and counts["course_table_with_selection"] >= 2
    ):
        return "multiple_pathways"

    if (
        counts["credit_summary"]
        and counts["course_table_with_selection"]
    ):
        return "summary_plus_curriculum"

    if counts["course_table_with_selection"]:
        return "curriculum_without_total"

    if counts["course_list"]:
        return "course_list_only"

    if counts["credit_summary"]:
        return "summary_only"

    return "other"


def main():
    programs = json.loads(
        PROGRAMS_PATH.read_text(encoding="utf-8")
    )

    results = []
    page_counts = Counter()

    for index, program in enumerate(programs, start=1):
        print(
            f"[{index}/{len(programs)}] "
            f"{program['name']} ({program['credential']})"
        )

        try:
            response = requests.get(
                program["url"],
                headers=HEADERS,
                timeout=30,
            )
            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            tables = soup.find_all("table")

            table_types = [
                classify_table(table)
                for table in tables
            ]

            page_type = classify_page(table_types)

            page_counts[page_type] += 1

            results.append(
                {
                    "program_id": program["id"],
                    "name": program["name"],
                    "credential": program["credential"],
                    "page_type": page_type,
                    "table_count": len(tables),
                    "table_types": table_types,
                    "url": program["url"],
                }
            )

            print(
                f"  {page_type}: "
                f"{Counter(table_types)}"
            )

        except Exception as exc:
            page_counts["fetch_error"] += 1

            results.append(
                {
                    "program_id": program["id"],
                    "name": program["name"],
                    "credential": program["credential"],
                    "page_type": "fetch_error",
                    "error": str(exc),
                    "url": program["url"],
                }
            )

            print(f"  ERROR: {exc}")

        time.sleep(0.5)

    output = DATA_DIR / "program_structure_audit.json"

    output.write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("PROGRAM STRUCTURE SUMMARY")
    print("=" * 60)

    for page_type, count in page_counts.most_common():
        print(f"{page_type:35} {count}")

    print(f"\nWrote {output}")


if __name__ == "__main__":
    main()