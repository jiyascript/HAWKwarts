
import argparse
import json
import re
import unicodedata
from pathlib import Path

import pymupdf
from transcript_validator import validate_academic_history


# =========================================================
# HAWKwarts Transcript Parser
# Illinois Tech Unofficial Transcript (PDF)
# =========================================================

TERM = re.compile(
    r"^Term:\s*(Fall|Spring|Summer|Winter)\s+(\d{4})$"
)

SUBJECT = re.compile(r"^[A-Z]{2,6}$")
NUMBER = re.compile(r"^\d{3,4}[A-Z]?$")
DECIMAL = re.compile(r"^\d+\.\d{2,3}$")

GRADES = {
    "A", "A-", "B+", "B", "B-",
    "C+", "C", "C-", "D+", "D", "D-",
    "F", "P", "S", "U", "W", "I",
    "IP", "AU", "TR", "NR"
}

PASSING_GRADES = {
    "A", "A-", "B+", "B", "B-",
    "C+", "C", "C-", "D+", "D", "D-",
    "P", "S"
}


# =========================================================
# 1. Extract text from PDF
# =========================================================

def normalize(text):
    return unicodedata.normalize("NFKC", text).strip()


def get_lines(pdf_path):
    lines = []

    with pymupdf.open(pdf_path) as pdf:
        for page in pdf:
            text = page.get_text("text")

            for line in text.splitlines():
                if line.strip():
                    lines.append(normalize(line))

    return lines


# =========================================================
# 2. Parse transcript
# =========================================================

def parse_transcript(pdf_path):

    lines = get_lines(pdf_path)

    if not any(
        "Unofficial Academic Transcript" in line
        for line in lines
    ):
        raise ValueError(
            "Not a recognized Illinois Tech unofficial transcript."
        )

    section = None
    term = None
    courses = []
    i = 0

    while i < len(lines):

        current = lines[i]

        # Identify transcript sections
        if current == "TRANSFER CREDIT ACCEPTED BY INSTITUTION":
            section = "transfer"
            term = None

        elif current == "INSTITUTION CREDIT":
            section = "institution"
            term = None

        elif current == "COURSE(S) IN PROGRESS":
            section = "in_progress"
            term = None

        elif current == "TRANSCRIPT TOTALS":
            section = None
            term = None

        # Identify semester
        match = TERM.match(current)

        if match and section in ("institution", "in_progress"):
            term = f"{match.group(1)} {match.group(2)}"

        # -------------------------------------------------
        # Parse transfer courses
        # -------------------------------------------------

        if (
            section == "transfer"
            and SUBJECT.fullmatch(current)
            and i + 2 < len(lines)
            and NUMBER.fullmatch(lines[i + 1])
        ):

            j = i + 2
            title = []

            while (
                j < len(lines)
                and lines[j] not in GRADES
                and j - i < 12
            ):
                title.append(lines[j])
                j += 1

            if (
                j + 2 < len(lines)
                and lines[j] in GRADES
                and DECIMAL.fullmatch(lines[j + 1])
                and DECIMAL.fullmatch(lines[j + 2])
            ):

                courses.append({
                    "code": f"{current} {lines[i + 1]}",
                    "title": " ".join(title),
                    "grade": lines[j],
                    "credits": float(lines[j + 1]),
                    "term": None,
                    "level": None,
                    "status": "transfer"
                })

                i = j + 3
                continue

        # -------------------------------------------------
        # Parse institution and in-progress courses
        # -------------------------------------------------

        if (
            section in ("institution", "in_progress")
            and term
            and SUBJECT.fullmatch(current)
            and i + 3 < len(lines)
            and NUMBER.fullmatch(lines[i + 1])
            and lines[i + 3] in ("UG", "GR")
        ):

            j = i + 4
            title = []
            grade = None

            while j < len(lines) and j - i < 20:

                token = lines[j]

                if section == "institution":

                    if (
                        token in GRADES
                        and j + 2 < len(lines)
                        and DECIMAL.fullmatch(lines[j + 1])
                        and DECIMAL.fullmatch(lines[j + 2])
                    ):
                        grade = token
                        break

                    # Handle a grade attached to the title
                    attached_grade = re.match(
                        r"^(.+?)\s*(A-|B\+|B-|C\+|C-|D\+|D-|A|B|C|D|F|P|W|I|IP|S|U)$",
                        token
                    )

                    if (
                        attached_grade
                        and j + 2 < len(lines)
                        and DECIMAL.fullmatch(lines[j + 1])
                        and DECIMAL.fullmatch(lines[j + 2])
                    ):
                        title.append(attached_grade.group(1))
                        grade = attached_grade.group(2)
                        break

                else:
                    if DECIMAL.fullmatch(token):
                        break

                if token.startswith((
                    "Term Totals",
                    "Term:",
                    "TRANSCRIPT TOTALS"
                )):
                    break

                title.append(token)
                j += 1

            if section == "institution" and grade is not None:
                credits = float(lines[j + 1])
                advance = j + 3

            elif (
                section == "in_progress"
                and j < len(lines)
                and DECIMAL.fullmatch(lines[j])
            ):
                credits = float(lines[j])
                advance = j + 1

            else:
                i += 1
                continue

            courses.append({
                "code": f"{current} {lines[i + 1]}",
                "title": " ".join(title),
                "grade": grade,
                "credits": credits,
                "term": term,
                "level": lines[i + 3],
                "status": (
                    "in_progress"
                    if section == "in_progress"
                    else "institution"
                )
            })

            i = advance
            continue

        i += 1

    # =====================================================
    # 3. Categorize extracted courses
    # =====================================================

    completed = [
        course for course in courses
        if (
            course["status"] == "institution"
            and course["grade"] in PASSING_GRADES
        )
    ]

    transfer = [
        course for course in courses
        if course["status"] == "transfer"
    ]

    in_progress = [
        course for course in courses
        if course["status"] == "in_progress"
    ]

    institution_records = [
        course for course in courses
        if course["status"] == "institution"
    ]

    # Deduplicate course codes for scheduler use.
    # Keep original UG/GR records in completed_courses.
    scheduler_codes = sorted({
        course["code"]
        for course in completed + transfer
    })

    return {
        "completed_courses": completed,
        "transfer_courses": transfer,
        "in_progress_courses": in_progress,
        "all_institution_records": institution_records,
        "scheduler_course_codes": scheduler_codes,
        "warnings": [
            "Completion is provisional. Verify grades, "
            "repeated courses, transfer equivalencies, "
            "and degree requirements before scheduling."
        ]
    }


# =========================================================
# 4. Save extracted information as JSON
# =========================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "pdf",
        type=Path,
        help="Path to Illinois Tech unofficial transcript"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("transcript_results.json")
    )

    args = parser.parse_args()

    results = validate_academic_history(parse_transcript(args.pdf))

    args.output.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\nHAWKwarts Transcript Parser")
    print("===========================")

    print(
        "Completed course records:",
        len(results["completed_courses"])
    )

    print(
        "Transfer courses:",
        len(results["transfer_courses"])
    )

    print(
        "In-progress courses:",
        len(results["in_progress_courses"])
    )

    print(
        "Unique completed/transfer course codes:",
        len(results["scheduler_course_codes"])
    )

    print("\nResults saved to:", args.output)


if __name__ == "__main__":
    main()
