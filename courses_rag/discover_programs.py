"""Discover all academic programs listed in the Illinois Tech catalog.
Scrapes https://catalog.iit.edu/programs/ and stores each program/credential
combination as a separate record.

Usage:
    python discover_programs.py
    python discover_programs.py --out data/programs.json
"""
import argparse
import json
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE_URL = "https://catalog.iit.edu"
PROGRAMS_URL = f"{BASE_URL}/programs/"
DATA_DIR = Path(__file__).parent / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; iit-catalog-rag/1.0)"
}

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def fetch(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def slugify(text: str) -> str:
    """Turn text into a stable lowercase identifier."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def clean_program_name(name: str) -> str:
    """Remove catalog footnote markers such as * and **."""
    return clean_text(name).rstrip("*").strip()


def clean_credential(credential: str) -> str:
    """Normalize whitespace while preserving catalog credential names."""
    return clean_text(credential)


def infer_level(url: str, credential: str) -> str:
    """Infer broad academic level from the catalog URL/credential."""
    if "/undergraduate/" in url:
        return "undergraduate"

    if "/graduate/" in url:
        return "graduate"

    if credential == "BS/BAC/BA":
        return "undergraduate"

    if credential in {
        "MAS",
        "M.ENG.",
        "M.S.",
        "JD",
        "JSD",
        "PHD",
        "CER",
        "DUAL DEGREE",
    }:
        return "graduate"

    return "unknown"


def discover_programs() -> list[dict]:
    html = fetch(PROGRAMS_URL)
    soup = BeautifulSoup(html, "html.parser")

    # Find the table whose first header is "Major".
    program_table = None

    for table in soup.find_all("table"):
        first_row = table.find("tr")
        if not first_row:
            continue

        headers = [
            clean_text(cell.get_text(" ", strip=True))
            for cell in first_row.find_all(["th", "td"])
        ]

        if headers and headers[0].lower() == "major":
            program_table = table
            break

    if program_table is None:
        raise RuntimeError("Could not find the programs table.")

    header_row = program_table.find("tr")

    headers = [
        clean_text(cell.get_text(" ", strip=True))
        for cell in header_row.find_all(["th", "td"])
    ]

    print("Detected columns:")
    for index, header in enumerate(headers):
        print(f"  {index}: {header}")

    programs = []

    for row in program_table.find_all("tr")[1:]:
        cells = row.find_all(["th", "td"])

        if not cells:
            continue

        raw_name = clean_text(cells[0].get_text(" ", strip=True))

        if not raw_name:
            continue

        name = clean_program_name(raw_name)

        # Every remaining column represents a credential type.
        for index, cell in enumerate(cells[1:], start=1):
            if index >= len(headers):
                continue

            credential = clean_credential(headers[index])

            links = cell.find_all("a", href=True)

            if not links:
                continue

            for link in links:
                url = urljoin(BASE_URL, link["href"])

                # Only keep actual catalog links.
                if "catalog.iit.edu" not in url:
                    continue

                level = infer_level(url, credential)

                program_id = (
                    f"{slugify(name)}:"
                    f"{slugify(credential)}"
                )

                record = {
                    "id": program_id,
                    "name": name,
                    "credential": credential,
                    "level": level,
                    "url": url,
                    "source_url": PROGRAMS_URL,
                }

                programs.append(record)

    return programs


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--out",
        default=str(DATA_DIR / "programs.json"),
        help="Output JSON path",
    )

    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)

    print(f"Fetching {PROGRAMS_URL} ...")

    programs = discover_programs()

    # Remove exact duplicate records if the page contains repeated links.
    unique = {}

    for program in programs:
        key = (
            program["name"],
            program["credential"],
            program["url"],
        )
        unique[key] = program

    programs = sorted(
        unique.values(),
        key=lambda item: (
            item["name"],
            item["credential"],
        ),
    )

    out_path = Path(args.out)

    out_path.write_text(
        json.dumps(programs, indent=2),
        encoding="utf-8",
    )

    print(f"\nDiscovered {len(programs)} program/credential combinations.")
    print(f"Wrote data to {out_path}")

    counts = {}

    for program in programs:
        credential = program["credential"]
        counts[credential] = counts.get(credential, 0) + 1

    print("\nBy credential:")

    for credential, count in sorted(counts.items()):
        print(f"  {credential}: {count}")


if __name__ == "__main__":
    main()