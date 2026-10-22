"""Scrape structured program requirements from the Illinois Tech catalog.

Stage 1: parse one program at a time.

Usage:
    python scrape_requirements.py computer-science:bs-bac-ba
"""

import argparse
import json
import re
from pathlib import Path
import time
import requests
from bs4 import BeautifulSoup
from audit_program_structures import classify_table

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; iit-catalog-rag/1.0)"
}

DATA_DIR = Path(__file__).parent / "data"
PROGRAMS_PATH = DATA_DIR / "programs.json"

COURSE_RE = re.compile(r"^[A-Z]{2,5}\s+\d{3}[A-Z]?$")
OR_COURSE_RE = re.compile(r"^or\s+([A-Z]{2,5}\s+\d{3}[A-Z]?)$", re.I)
CREDIT_RANGE_RE = re.compile(r"^\(?\s*(\d+)\s*[-–—]\s*(\d+)\s*\)?$")

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def fetch(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def load_program(program_id: str) -> dict:
    programs = json.loads(
        PROGRAMS_PATH.read_text(encoding="utf-8")
    )

    for program in programs:
        if program["id"] == program_id:
            return program

    raise ValueError(f"Program not found: {program_id}")


def parse_number(text: str):
    """Return an int when text contains a simple integer."""
    if not text:
        return None

    match = re.search(r"\d+", text)

    if not match:
        return None

    return int(match.group())

def parse_credit_value(text):
    """
    Parse either a single credit value or a credit range.

    Examples:
        "15"    -> 15
        "(4-6)" -> {"min": 4, "max": 6}
        "2–4"   -> {"min": 2, "max": 4}
    """

    text = clean_text(text)

    match = CREDIT_RANGE_RE.match(text)

    if match:
        return {
            "min": int(match.group(1)),
            "max": int(match.group(2)),
        }

    number = parse_number(text)

    if number is not None:
        return number

    return None

def get_row_values(row) -> list[str]:
    values = [
        clean_text(cell.get_text(" ", strip=True))
        for cell in row.find_all(["th", "td"])
    ]

    return [value for value in values if value]


def is_course_code(text: str) -> bool:
    return bool(COURSE_RE.fullmatch(text.strip()))


def extract_or_course(text: str):
    match = OR_COURSE_RE.fullmatch(text.strip())

    if match:
        return match.group(1).upper()

    return None


def is_section_header(values: list[str]) -> bool:
    """
    Detect requirement section rows such as:

        ['Computer Science Requirements', '(36)']
        ['Core Courses', '12']
        ['Electives', '20']
        ['Computer Science Requirements', '(4-6)']
        ['Free Electives', '(2-4)']

    Empty cells are ignored before classification.
    """

    values = [value for value in values if value]

    if len(values) != 2:
        return False

    name, credits = values

    # A section heading should not itself be a course.
    if is_course_code(name):
        return False

    # Selection/instruction rows should not become sections.
    lower = name.lower()

    if (
        lower.startswith("select")
        or lower.startswith("please select")
        or lower.startswith("see ")
        or lower.startswith("total ")
    ):
        return False

    # Accept either:
    #   12
    #   (12)
    #   4-6
    #   (4-6)
    # and Unicode dash variants.
    return bool(
        re.fullmatch(
            r"\(?\d+\s*(?:[-–—]\s*\d+)?\)?",
            credits.strip(),
        )
    )

def parse_credit_word(text: str):
    """
    Extract credit counts written as digits or common words.

    Examples:
        'Select 9 credit hours' -> 9
        'Select nine credit hours' -> 9
        'Select twelve credit hours' -> 12
    """
    digit_match = re.search(r"\d+", text)

    if digit_match:
        return int(digit_match.group())

    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
    }

    lower = text.lower()

    for word, value in number_words.items():
        if re.search(rf"\b{word}\b", lower):
            return value

    return None
def parse_course_count(text: str):
    """
    Extract a course count from selection instructions.

    Examples:
        "Select one course" -> 1
        "Select a minimum of two courses" -> 2
        "Choose three courses" -> 3
    """
    digit_match = re.search(r"\d+", text)

    if digit_match:
        return int(digit_match.group())

    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    lower = text.lower()

    for word, value in number_words.items():
        if re.search(rf"\b{word}\b", lower):
            return value

    return None

def is_total_row(values: list[str]) -> bool:
    if not values:
        return False

    return values[0].lower().startswith("total credit hours")


def parse_requirement_table(table) -> tuple[list[dict], int | None]:
    rows = table.find_all("tr")

    sections = []
    current_section = None
    total_credits = None

    i = 1  # skip Code / Title / Credit Hours header

    while i < len(rows):
        values = get_row_values(rows[i])

        if not values:
            i += 1
            continue

        # ------------------------------------------------------------
        # TOTAL CREDIT HOURS
        # ------------------------------------------------------------

        if is_total_row(values):
            if len(values) >= 2:
                total_credits = parse_number(values[-1])

            i += 1
            continue

        # ------------------------------------------------------------
        # SECTION HEADER
        # ------------------------------------------------------------

        if is_section_header(values):
            current_section = {
                "name": values[0],
                "credits": parse_number(values[1]),
                "items": [],
            }

            sections.append(current_section)
            i += 1
            continue

        if current_section is None:
            current_section = {
                "name": "Curriculum",
                "credits": None,
                "items": [],
            }

            sections.append(current_section)

        first = values[0]

        # ------------------------------------------------------------
        # NORMAL COURSE
        # ------------------------------------------------------------

        if is_course_code(first):
            title = values[1] if len(values) >= 2 else ""

            credits = (
                parse_number(values[2])
                if len(values) >= 3
                else None
            )

            item = {
                "type": "course",
                "course": first,
                "title": title,
                "credits": credits,
            }

            # Check whether following row is:
            #
            # or MATH 333
            #
            # If so, combine the two into one_of.
            if i + 1 < len(rows):
                next_values = get_row_values(rows[i + 1])

                if next_values:
                    alternative_code = extract_or_course(
                        next_values[0]
                    )

                    if alternative_code:
                        alternative_title = (
                            next_values[1]
                            if len(next_values) >= 2
                            else ""
                        )

                        item = {
                            "type": "one_of",
                            "options": [
                                {
                                    "course": first,
                                    "title": title,
                                },
                                {
                                    "course": alternative_code,
                                    "title": alternative_title,
                                },
                            ],
                            "credits": credits,
                        }

                        i += 1

            current_section["items"].append(item)
            i += 1
            continue

        # ------------------------------------------------------------
        # SELECT ONE OF THE FOLLOWING
        # ------------------------------------------------------------

        if first.lower().startswith(
            "select one of the following"
        ):
            credits = (
                parse_number(values[-1])
                if len(values) >= 2
                else None
            )

            options = []

            j = i + 1

            while j < len(rows):
                next_values = get_row_values(rows[j])

                if not next_values:
                    break

                next_first = next_values[0]

                if is_section_header(next_values):
                    break

                if is_total_row(next_values):
                    break

                if not is_course_code(next_first):
                    break

                options.append(next_first)
                j += 1

            current_section["items"].append(
                {
                    "type": "choose",
                    "count": 1,
                    "credits_required": credits,
                    "options": options,
                }
            )

            i = j
            continue
        # ------------------------------------------------------------
        # SELECT X CREDIT HOURS FROM THE FOLLOWING
        # ------------------------------------------------------------

        if (
            first.lower().startswith("select")
            and "credit" in first.lower()
            and "following" in first.lower()
        ):
            credits_required = parse_credit_word(first)

            # Prefer the explicit table credit value when present.
            if len(values) >= 2:
                table_credits = parse_number(values[-1])

                if table_credits is not None:
                    credits_required = table_credits

            options = []

            j = i + 1

            while j < len(rows):
                next_values = get_row_values(rows[j])

                if not next_values:
                    j += 1
                    continue

                next_first = next_values[0]

                if is_total_row(next_values):
                    break

                if is_section_header(next_values):
                    break

                if not is_course_code(next_first):
                    break

                option = {
                    "course": next_first,
                    "title": (
                        next_values[1]
                        if len(next_values) >= 2
                        else ""
                    ),
                    "credits": (
                        parse_number(next_values[2])
                        if len(next_values) >= 3
                        else None
                    ),
                }

                options.append(option)
                j += 1

            current_section["items"].append(
                {
                    "type": "credits_from",
                    "credits_required": credits_required,
                    "options": options,
                }
            )

            i = j
            continue
        # ------------------------------------------------------------
        # SELECT N COURSES FROM THE FOLLOWING
        # ------------------------------------------------------------

        lower_first = first.lower()

        if (
            (
                lower_first.startswith("select")
                or lower_first.startswith("choose")
            )
            and "course" in lower_first
            and "following" in lower_first
        ):
            count = parse_course_count(first)

            credits_required = (
                parse_number(values[-1])
                if len(values) >= 2
                else None
            )

            options = []

            j = i + 1

            while j < len(rows):
                next_values = get_row_values(rows[j])

                if not next_values:
                    j += 1
                    continue

                next_first = next_values[0]

                if is_total_row(next_values):
                    break

                if is_section_header(next_values):
                    break

                # Preserve non-course options such as:
                # "Any ITMM Elective"
                if not is_course_code(next_first):
                    options.append(
                        {
                            "type": "free_text",
                            "raw_text": " | ".join(next_values),
                        }
                    )
                    j += 1
                    continue

                options.append(
                    {
                        "type": "course",
                        "course": next_first,
                        "title": (
                            next_values[1]
                            if len(next_values) >= 2
                            else ""
                        ),
                        "credits": (
                            parse_number(next_values[2])
                            if len(next_values) >= 3
                            else None
                        ),
                    }
                )

                j += 1

            current_section["items"].append(
                {
                    "type": "choose",
                    "count": count,
                    "credits_required": credits_required,
                    "options": options,
                }
            )

            i = j
            continue
        # ------------------------------------------------------------
        # GENERIC "SELECT X CREDIT HOURS"
        # ------------------------------------------------------------

        if (
            first.lower().startswith("select")
            or first.lower().startswith("please select")
        ):
            credits = (
                parse_number(values[-1])
                if len(values) >= 2
                else None
            )

            current_section["items"].append(
                {
                    "type": "free_text",
                    "raw_text": first,
                    "credits_required": credits,
                    "parsed": False,
                }
            )

            i += 1
            continue

        # ------------------------------------------------------------
        # EXTERNAL REQUIREMENT
        # ------------------------------------------------------------

        if first.lower().startswith("see "):
            credits = (
                parse_number(values[-1])
                if len(values) >= 2
                else None
            )

            current_section["items"].append(
                {
                    "type": "external_requirement",
                    "raw_text": first,
                    "credits_required": credits,
                }
            )

            i += 1
            continue

        # ------------------------------------------------------------
        # FALLBACK
        # ------------------------------------------------------------

        current_section["items"].append(
            {
                "type": "free_text",
                "raw_text": " | ".join(values),
                "parsed": False,
            }
        )

        i += 1

    return sections, total_credits


def score_requirement_table(table) -> int:
    """
    Score how likely a table is to be the program's main
    degree-requirements table.

    Main requirement tables usually contain:
    - Code / Title / Credit Hours headers
    - Total Credit Hours
    - Select statements
    - course codes
    """
    rows = table.find_all("tr")

    if not rows:
        return -1

    score = 0

    first_values = get_row_values(rows[0])
    header_text = " ".join(first_values).lower()

    if "code" in header_text:
        score += 2

    if "title" in header_text:
        score += 2

    if "credit hours" in header_text:
        score += 2

    for row in rows[1:]:
        values = get_row_values(row)

        if not values:
            continue

        first = values[0]
        lower = first.lower()

        if lower.startswith("total credit hours"):
            score += 10

        if lower.startswith("select"):
            score += 2

        if lower.startswith("please select"):
            score += 2

        if is_course_code(first):
            score += 1

    return score


def find_main_requirement_table(soup):
    """
    Find the program's primary degree-requirements table.
    """

    tables = soup.find_all("table")

    if not tables:
        raise RuntimeError("No tables found on program page.")

    # ------------------------------------------------------------
    # FIRST PASS: table with explicit Total Credit Hours
    # ------------------------------------------------------------

    for index, table in enumerate(tables):
        rows = table.find_all("tr")

        if not rows:
            continue

        header_values = get_row_values(rows[0])
        header = " ".join(header_values).lower()

        has_requirement_columns = (
            "code" in header
            and "title" in header
            and "credit hours" in header
        )

        if not has_requirement_columns:
            continue

        has_total = False

        for row in rows[1:]:
            values = get_row_values(row)

            if is_total_row(values):
                has_total = True
                break

        if has_total:
            print(
                f"Selected requirement table {index} "
                "(contains Total Credit Hours)"
            )
            return table

    # ------------------------------------------------------------
    # SECOND PASS: curriculum without explicit total
    # ------------------------------------------------------------

    candidates = []

    for index, table in enumerate(tables):
        if classify_table(table) == "course_table_with_selection":
            candidates.append((index, table))

    if len(candidates) == 1:
        index, table = candidates[0]

        print(
            f"Selected requirement table {index} "
            "(curriculum without explicit total)"
        )

        return table

    if len(candidates) > 1:
        print(
            f"Found {len(candidates)} curriculum-like tables; "
            "leaving requirements unparsed."
        )
        return None

    # ------------------------------------------------------------
    # NOTHING SAFE TO PARSE
    # ------------------------------------------------------------

    print("No single authoritative requirement table found.")
    return None

def extract_notes(soup) -> list[str]:
    """
    Extract explanatory catalog notes while avoiding large container
    elements that duplicate whole sections of the page.
    """
    notes = []
    seen = set()

    for element in soup.find_all("p"):
        text = clean_text(element.get_text(" ", strip=True))

        if not text:
            continue

        # Keep notes that explain requirements, substitutions,
        # electives, approvals, restrictions, etc.
        lower = text.lower()

        keywords = (
            "elective",
            "equivalent",
            "may be used",
            "must be",
            "cannot be",
            "minimum",
            "maximum",
            "approval",
            "required",
        )

        if any(keyword in lower for keyword in keywords):
            if text not in seen:
                seen.add(text)
                notes.append(text)

    return notes
def extract_credit_summary(soup) -> dict:
    """
    Extract explicit program-level credit constraints from
    Requirement / Credits summary tables.

    If no summary table provides the minimum degree credits,
    fall back to an explicit prose statement such as:
        "Minimum degree credits required: 120"

    Does not infer totals by summing course rows.
    """

    summary = {
        "minimum_credits": None,
        "constraints": [],
    }

    # ------------------------------------------------------------
    # 1. Look for Requirement / Credits summary tables
    # ------------------------------------------------------------

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        if not rows:
            continue

        header = [
            value.lower()
            for value in get_row_values(rows[0])
        ]

        if not (
            "requirement" in header
            and "credits" in header
        ):
            continue

        for row in rows[1:]:
            values = get_row_values(row)

            if len(values) < 2:
                continue

            requirement = values[0]
            credit_text = values[-1]

            if requirement.lower() in (
                "minimum total credits required",
                "minimum credits required",
                "minimum degree credits",
            ):
                summary["minimum_credits"] = parse_number(
                    credit_text
                )

            summary["constraints"].append(
                {
                    "requirement": requirement,
                    "credits": credit_text,
                }
            )

    # ------------------------------------------------------------
    # 2. Remove exact duplicate constraints
    # ------------------------------------------------------------

    seen = set()
    unique_constraints = []

    for constraint in summary["constraints"]:
        key = (
            constraint["requirement"].lower(),
            constraint["credits"],
        )

        if key not in seen:
            seen.add(key)
            unique_constraints.append(constraint)

    summary["constraints"] = unique_constraints

    # ------------------------------------------------------------
    # 3. Prose fallback for minimum degree credits
    # ------------------------------------------------------------

    if summary["minimum_credits"] is None:
        page_text = clean_text(
            soup.get_text(" ", strip=True)
        )

        match = re.search(
            r"minimum degree credits required:\s*(\d+)",
            page_text,
            re.I,
        )

        if match:
            summary["minimum_credits"] = int(
                match.group(1)
            )

    return summary
def scrape_program_requirements(program: dict) -> dict:
    html = fetch(program["url"])
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.find("h1")

    title = (
        clean_text(h1.get_text(" ", strip=True))
        if h1
        else program["name"]
    )

    table = find_main_requirement_table(soup)
    if table is not None:
        requirements, total_credits = parse_requirement_table(table)
    else:
        requirements, total_credits = [], None
    notes = extract_notes(soup)
    credit_summary = extract_credit_summary(soup)

    return {
        "program_id": program["id"],
        "name": program["name"],
        "title": title,
        "credential": program["credential"],
        "level": program["level"],
        "total_credits": total_credits,
        "minimum_credits": credit_summary["minimum_credits"],
        "credit_constraints": credit_summary["constraints"],
        "requirements": requirements,
        "notes": notes,
        "url": program["url"],
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "program_id",
        nargs="?",
        help="Program ID from data/programs.json",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Scrape requirements for all discovered programs",
    )

    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON path",
    )

    args = parser.parse_args()

    # ------------------------------------------------------------
    # ALL PROGRAMS
    # ------------------------------------------------------------

    if args.all:
        programs = json.loads(
            PROGRAMS_PATH.read_text(encoding="utf-8")
        )

        results = []
        failures = []

        print(f"Scraping {len(programs)} programs...\n")

        for index, program in enumerate(programs, start=1):
            print(
                f"[{index}/{len(programs)}] "
                f"{program['name']} ({program['credential']})"
            )

            try:
                result = scrape_program_requirements(program)

                results.append(result)

                print(
                    f"  ✓ {result['total_credits']} credits, "
                    f"{len(result['requirements'])} sections"
                )

            except Exception as exc:
                print(f"  ✗ {type(exc).__name__}: {exc}")

                failures.append(
                    {
                        "program_id": program["id"],
                        "name": program["name"],
                        "credential": program["credential"],
                        "url": program["url"],
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            time.sleep(0.5)  # Being respectful to the server and avoiding rate-limiting

        out_path = Path(
            args.out
            or DATA_DIR / "program_requirements.json"
        )

        failure_path = DATA_DIR / "requirement_scrape_failures.json"

        out_path.write_text(
            json.dumps(results, indent=2),
            encoding="utf-8",
        )

        failure_path.write_text(
            json.dumps(failures, indent=2),
            encoding="utf-8",
        )

        print("\n" + "=" * 60)
        print("SCRAPE COMPLETE")
        print("=" * 60)

        print(f"Programs discovered: {len(programs)}")
        print(f"Successfully parsed: {len(results)}")
        print(f"Failed: {len(failures)}")

        print(f"\nRequirements: {out_path}")
        print(f"Failures:     {failure_path}")

        return

    # ------------------------------------------------------------
    # SINGLE PROGRAM
    # ------------------------------------------------------------

    if not args.program_id:
        parser.error(
            "Provide a program_id or use --all."
        )

    program = load_program(args.program_id)

    print(
        f"Scraping {program['name']} "
        f"({program['credential']})..."
    )

    result = scrape_program_requirements(program)

    out_path = Path(
        args.out
        or DATA_DIR / "program_requirement_test.json"
    )

    out_path.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {out_path}")
    print()
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()