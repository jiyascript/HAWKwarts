import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from scrape_requirements import (
    clean_text,
    extract_or_course,
    get_row_values,
    is_course_code,
    is_total_row,
    parse_course_count,
    parse_number,
)


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

DATA_DIR = Path(__file__).parent / "data"

MINORS_PATH = DATA_DIR / "minors.json"

OUTPUT_PATH = (
    DATA_DIR / "minor_requirements.json"
)

FAILURES_PATH = (
    DATA_DIR / "minor_requirement_scrape_failures.json"
)


def fetch(url: str, attempts: int = 3) -> str:
    last_exc = None

    for attempt in range(attempts):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=30,
            )

            response.raise_for_status()

            return response.text

        except requests.RequestException as exc:
            last_exc = exc

            if attempt < attempts - 1:
                time.sleep(
                    1.5 * (attempt + 1)
                )

    raise last_exc


def find_requirement_table(soup):
    """
    Find the main minor requirement table.

    Minor pages generally contain a table with:
        Code | Title | Credit Hours
    """

    candidates = []

    for index, table in enumerate(
        soup.find_all("table")
    ):
        first_row = table.find("tr")

        if not first_row:
            continue

        headers = [
            clean_text(
                cell.get_text(
                    " ",
                    strip=True,
                )
            ).lower()
            for cell in first_row.find_all(
                ["th", "td"]
            )
        ]

        if (
            "code" in headers
            and "title" in headers
            and "credit hours" in headers
        ):
            candidates.append(
                (index, table)
            )

    # Prefer a table containing an explicit total.
    for index, table in candidates:
        for row in table.find_all("tr"):
            values = get_row_values(row)

            if is_total_row(values):
                return table

    # If there is exactly one curriculum-like
    # table, it is safe to use it.
    if len(candidates) == 1:
        return candidates[0][1]

    return None


def parse_minor_table(table):
    requirements = []
    total_credits = None

    rows = table.find_all("tr")

    i = 1

    while i < len(rows):
        values = get_row_values(rows[i])

        if not values:
            i += 1
            continue

        first = values[0]
        lower = first.lower()

        # -----------------------------------------
        # Total Credit Hours
        # -----------------------------------------

        if is_total_row(values):
            total_credits = parse_number(
                values[-1]
            )

            i += 1
            continue

        # -----------------------------------------
        # Selection group
        #
        # Example:
        # Select a minimum of three courses.
        # followed by CS 422, CS 429, ...
        # -----------------------------------------

        if (
            lower.startswith("select")
            or lower.startswith("please select")
        ):
            count = parse_course_count(first)

            credits_required = (
                parse_number(values[-1])
                if len(values) > 1
                else None
            )

            options = []

            j = i + 1

            while j < len(rows):
                next_values = get_row_values(
                    rows[j]
                )

                if not next_values:
                    j += 1
                    continue

                next_first = next_values[0]

                if not is_course_code(
                    next_first
                ):
                    break

                options.append(next_first)

                j += 1

            # Only create a structured choose
            # rule if explicit course options
            # actually follow the instruction.
            if options:
                item = {
                    "type": "choose",
                    "count": count,
                    "options": options,
                    "raw_text": first,
                }

                if "minimum" in lower:
                    item["minimum"] = True

                if (
                    credits_required
                    is not None
                ):
                    item[
                        "credits_required"
                    ] = credits_required

                requirements.append(item)

                i = j
                continue

            # Something like:
            # "Select at least two mathematics
            # courses at the 400-level"
            #
            # Keep it raw rather than pretending
            # we understand the rule completely.
            requirements.append(
                {
                    "type": "free_text",
                    "raw_text": (
                        " | ".join(values)
                    ),
                    "parsed": False,
                }
            )

            i += 1
            continue

        # -----------------------------------------
        # Normal course + possible OR alternative
        # -----------------------------------------

        if is_course_code(first):
            if i + 1 < len(rows):
                next_values = get_row_values(
                    rows[i + 1]
                )

                if next_values:
                    alternative = (
                        extract_or_course(
                            next_values[0]
                        )
                    )

                    if alternative:
                        requirements.append(
                            {
                                "type": "one_of",
                                "options": [
                                    first,
                                    alternative,
                                ],
                            }
                        )

                        i += 2
                        continue

            item = {
                "type": "course",
                "course": first,
            }

            if len(values) >= 2:
                item["title"] = values[1]

            if len(values) >= 3:
                raw_credits = values[-1].strip()

                if raw_credits.isdigit():
                    item["credits"] = int(
                        raw_credits
                    )
                else:
                    item["credits_text"] = (
                        raw_credits
                    )

            requirements.append(item)

            i += 1
            continue

        # -----------------------------------------
        # Anything else remains raw
        # -----------------------------------------

        requirements.append(
            {
                "type": "free_text",
                "raw_text": (
                    " | ".join(values)
                ),
                "parsed": False,
            }
        )

        i += 1

    return requirements, total_credits

def extract_minor_prose_requirements(soup):
    """
    Extract requirement prose from pages that do not
    contain requirement tables.
    """

    requirements = []

    for p in soup.find_all("p"):
        text = clean_text(
            p.get_text(" ", strip=True)
        )

        if not text:
            continue

        lower = text.lower()

        if (
            "credit" in lower
            or "course" in lower
            or "required" in lower
            or "elective" in lower
        ):
            requirements.append(
                {
                    "type": "free_text",
                    "raw_text": text,
                    "parsed": False,
                }
            )

    return requirements
def find_requirement_tables(soup):
    """
    Return all Code / Title / Credit Hours tables.
    """

    tables = []

    for table in soup.find_all("table"):
        first_row = table.find("tr")

        if not first_row:
            continue

        headers = [
            clean_text(
                cell.get_text(
                    " ",
                    strip=True,
                )
            ).lower()
            for cell in first_row.find_all(
                ["th", "td"]
            )
        ]

        if (
            "code" in headers
            and "title" in headers
            and "credit hours" in headers
        ):
            tables.append(table)

    return tables
def get_table_context(table):
    """
    Find nearby prose that describes the requirement
    represented by this table.
    """

    keywords = (
        "required",
        "choose",
        "select",
        "following",
        "elective",
        "courses",
        "credits",
        "one of",
        "both",
        "any ",
        "at least",
    )

    checked = 0

    for previous in table.find_all_previous(
        ["p", "h2", "h3", "h4"]
    ):
        text = clean_text(
            previous.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        lower = text.lower()

        if any(
            keyword in lower
            for keyword in keywords
        ):
            return text

        checked += 1

        # Don't wander arbitrarily far up the page.
        if checked >= 6:
            break

    return None

def scrape_minor(minor: dict) -> dict:
    html = fetch(minor["url"])

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    title = None

    h1 = soup.find("h1")

    if h1:
        title = clean_text(
            h1.get_text(
                " ",
                strip=True,
            )
        )

    tables = find_requirement_tables(soup)

    # ------------------------------------------------
    # No tables: preserve prose requirements.
    # ------------------------------------------------

    if not tables:
        requirements = (
            extract_minor_prose_requirements(
                soup
            )
        )

        if not requirements:
            raise ValueError(
                "No requirement tables or "
                "requirement prose found"
            )

        return {
            "minor_id": minor["id"],
            "name": minor["name"],
            "title": title,
            "total_credits": None,
            "requirements": requirements,
            "requirement_groups": [],
            "url": minor["url"],
        }

    # ------------------------------------------------
    # One table: keep our existing representation.
    # ------------------------------------------------

    if len(tables) == 1:
        requirements, total_credits = (
            parse_minor_table(tables[0])
        )

        return {
            "minor_id": minor["id"],
            "name": minor["name"],
            "title": title,
            "total_credits": total_credits,
            "requirements": requirements,
            "requirement_groups": [],
            "url": minor["url"],
        }

    # ------------------------------------------------
    # Multiple tables:
    #
    # Preserve each table as a separate group so we
    # don't lose the distinction between core,
    # electives, prerequisites, etc.
    # ------------------------------------------------

    groups = []
    total_credits = None

    for index, table in enumerate(
        tables,
        start=1,
    ):
        requirements, table_total = (
            parse_minor_table(table)
        )

        if table_total is not None:
            total_credits = table_total

        groups.append(
            {
                "group": index,
                "context": get_table_context(
                    table
                ),
                "requirements": requirements,
            }
        )

    return {
        "minor_id": minor["id"],
        "name": minor["name"],
        "title": title,
        "total_credits": total_credits,
        "requirements": [],
        "requirement_groups": groups,
        "url": minor["url"],
    }


def main():
    with MINORS_PATH.open() as f:
        minors = json.load(f)

    results = []
    failures = []

    for i, minor in enumerate(
        minors,
        start=1,
    ):
        print(
            f"[{i}/{len(minors)}] "
            f"{minor['name']}"
        )

        try:
            result = scrape_minor(minor)

            results.append(result)

            print(
                f"  -> {result['total_credits']} "
                f"credits, "
                f"{len(result['requirements'])} "
                f"requirement item(s)"
            )

        except Exception as exc:
            print(
                f"  !! "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            failures.append(
                {
                    "minor_id": minor["id"],
                    "name": minor["name"],
                    "url": minor["url"],
                    "error_type": (
                        type(exc).__name__
                    ),
                    "error": str(exc),
                }
            )

        time.sleep(0.25)

    with OUTPUT_PATH.open("w") as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False,
        )

    with FAILURES_PATH.open("w") as f:
        json.dump(
            failures,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 60)
    print("MINOR REQUIREMENT SCRAPE COMPLETE")
    print("=" * 60)
    print(
        f"Minors discovered: {len(minors)}"
    )
    print(
        f"Successfully parsed: {len(results)}"
    )
    print(
        f"Failed: {len(failures)}"
    )
    print(f"Requirements: {OUTPUT_PATH}")
    print(f"Failures: {FAILURES_PATH}")


if __name__ == "__main__":
    main()