import json
import re
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from scrape_requirements import (
    clean_text,
    get_row_values,
    is_course_code,
    parse_number,
    parse_course_count,
    extract_or_course,
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

DATA_DIR = Path(__file__).parent / "data"
PROGRAMS_PATH = DATA_DIR / "programs.json"
OUTPUT_PATH = DATA_DIR / "specializations.json"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


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
                time.sleep(1.5 * (attempt + 1))

    raise last_exc


def find_specialization_region(soup):
    """
    Find the heading that introduces the specialization section.
    """

    for heading in soup.find_all(["h2", "h3"]):
        text = clean_text(
            heading.get_text(" ", strip=True)
        ).lower()

        if "specialization" in text:
            return heading

    return None


def specialization_name_for_table(table, region_heading):
    """
    Walk backward from a table and find the specialization name.

    Handles patterns such as:

        h2 Artificial Intelligence
        table

    and:

        h3 Specialization in Applied Analysis
        h4 Required Courses
        table
    """

    heading = table.find_previous(
        ["h2", "h3", "h4"]
    )

    while heading is not None:
        if heading == region_heading:
            return None

        text = clean_text(
            heading.get_text(" ", strip=True)
        )

        lower = text.lower()

        # Skip generic headings.
        if lower not in {
            "required courses",
            "requirements",
            "curriculum",
        }:
            if lower.startswith("specialization in "):
                return text[len("Specialization in "):].strip()

            return text

        heading = heading.find_previous(
            ["h2", "h3", "h4"]
        )

    return None


def table_is_after_heading(table, heading) -> bool:
    """
    Check whether the table occurs after the specialization
    section begins.
    """

    for element in heading.find_all_next():
        if element == table:
            return True

    return False


def parse_specialization_table(table):
    """
    Parse specialization requirements conservatively.

    Handles:
      - ordinary required courses
      - "or COURSE" alternatives
      - "select N courses" option groups
      - recommended electives separately from requirements
    """

    requirements = []
    recommended = []

    rows = table.find_all("tr")
    i = 1

    in_recommended = False

    while i < len(rows):
        values = get_row_values(rows[i])

        if not values:
            i += 1
            continue

        first = values[0]
        lower = first.lower()

        # --------------------------------------------------------
        # Recommended/additional electives boundary
        # --------------------------------------------------------

        if (
            "recommended as additional electives" in lower
            or "recommended electives" in lower
        ):
            in_recommended = True
            i += 1
            continue

        target = recommended if in_recommended else requirements

        # --------------------------------------------------------
        # Selection groups
        #
        # Example:
        # Select a minimum of three courses from the following:
        # --------------------------------------------------------

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
                next_values = get_row_values(rows[j])

                if not next_values:
                    j += 1
                    continue

                next_first = next_values[0]
                next_lower = next_first.lower()

                if (
                    "recommended as additional electives"
                    in next_lower
                    or "recommended electives"
                    in next_lower
                ):
                    break

                if is_course_code(next_first):
                    options.append(next_first)
                    j += 1
                    continue

                break

            item = {
                "type": "choose",
                "count": count,
                "options": options,
                "raw_text": first,
            }

            if "minimum" in lower:
                item["minimum"] = True

            if credits_required is not None:
                item["credits_required"] = credits_required

            target.append(item)

            i = j
            continue

        # --------------------------------------------------------
        # Normal course
        #
        # Also detect a following:
        #     or CS 584
        # --------------------------------------------------------

        if is_course_code(first):
            course_item = {
                "type": "course",
                "course": first,
            }

            if len(values) >= 2:
                course_item["title"] = values[1]

            if len(values) >= 3:
                credits = parse_number(values[-1])

                if credits is not None:
                    course_item["credits"] = credits

            # Check for an immediately following "or COURSE" row.
            if i + 1 < len(rows):
                next_values = get_row_values(rows[i + 1])

                if next_values:
                    alternative = extract_or_course(
                        next_values[0]
                    )

                    if alternative:
                        target.append(
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

            target.append(course_item)
            i += 1
            continue

        # --------------------------------------------------------
        # Anything complicated stays raw
        # --------------------------------------------------------

        target.append(
            {
                "type": "free_text",
                "raw_text": " | ".join(values),
                "parsed": False,
            }
        )

        i += 1

    return {
        "requirements": requirements,
        "recommended_electives": recommended,
    }


def scrape_specializations(program: dict):
    html = fetch(program["url"])
    soup = BeautifulSoup(html, "html.parser")

    region = find_specialization_region(soup)

    if region is None:
        return []

    specializations = []

    for table in soup.find_all("table"):
        if not table_is_after_heading(table, region):
            continue

        name = specialization_name_for_table(
            table,
            region,
        )

        if not name:
            continue

        # Stop if we've moved into a later unrelated page section.
        if name.lower() == "print options":
            break

        parsed = parse_specialization_table(table)

        if not parsed["requirements"]:
            continue

        specializations.append(
            {
                "id": (
                    f"{program['id']}:"
                    f"{slugify(name)}"
                ),
                "name": name,
                "parent_program_id": program["id"],
                "parent_program_name": program["name"],
                "credential": program["credential"],
                "requirements": parsed["requirements"],
                "recommended_electives": parsed["recommended_electives"],
                "url": program["url"],
            }
        )

    return specializations


def main():
    with PROGRAMS_PATH.open() as f:
        programs = json.load(f)

    all_specializations = []

    for i, program in enumerate(programs, start=1):
        print(
            f"[{i}/{len(programs)}] "
            f"{program['name']} "
            f"({program['credential']})"
        )

        try:
            found = scrape_specializations(program)

            if found:
                print(
                    f"  -> found {len(found)} specialization(s)"
                )

                for specialization in found:
                    print(
                        f"     {specialization['name']}"
                    )

                all_specializations.extend(found)

        except Exception as exc:
            print(
                f"  !! {type(exc).__name__}: {exc}"
            )

        time.sleep(0.25)

    DATA_DIR.mkdir(exist_ok=True)

    with OUTPUT_PATH.open("w") as f:
        json.dump(
            all_specializations,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 60)
    print("SPECIALIZATION SCRAPE COMPLETE")
    print("=" * 60)
    print(
        f"Specializations discovered: "
        f"{len(all_specializations)}"
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()