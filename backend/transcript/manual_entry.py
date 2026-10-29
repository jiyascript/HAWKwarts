
import json
import re
from pathlib import Path

from transcript_validator import (
    normalize_course as shared_normalize_course,
    build_academic_history as shared_build_academic_history
)


# =========================================================
# HAWKwarts Manual Course Entry
# =========================================================

PASSING_GRADES = {
    "A", "A-", "B+", "B", "B-",
    "C+", "C", "C-", "D+", "D", "D-",
    "P", "S"
}

VALID_GRADES = PASSING_GRADES | {
    "F", "W", "I", "IP", "AU", "NR", "TR", ""
}

VALID_STATUSES = {
    "institution",
    "transfer",
    "in_progress"
}

VALID_LEVELS = {"UG", "GR"}


# =========================================================
# 1. Normalize and validate a course
# =========================================================

def normalize_course(course):
    code = " ".join(
        str(course.get("code", "")).upper().split()
    )

    title = str(course.get("title", "")).strip()
    grade = str(course.get("grade") or "").upper().strip()
    term = str(course.get("term") or "").strip()
    level = str(course.get("level") or "").upper().strip()
    status = str(course.get("status") or "").strip().lower()

    # Validate course code
    if not re.fullmatch(r"[A-Z]{2,6}\s\d{3,4}[A-Z]?", code):
        raise ValueError(
            f"Invalid course code: {code}. Example: CS 331"
        )

    if not title:
        raise ValueError("Course title cannot be empty.")

    # Validate credits
    try:
        credits = float(course.get("credits"))
    except (ValueError, TypeError):
        raise ValueError(f"Invalid credits for {code}.")

    if not 0 < credits <= 20:
        raise ValueError(
            f"Credits must be between 0 and 20 for {code}."
        )

    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status for {code}: {status}"
        )

    if grade not in VALID_GRADES:
        raise ValueError(
            f"Invalid grade for {code}: {grade}"
        )

    if level and level not in VALID_LEVELS:
        raise ValueError(
            f"Invalid academic level for {code}: {level}"
        )

    if status == "transfer":
        grade = "TR"

    elif status == "in_progress":
        grade = None

    elif not grade:
        raise ValueError(
            f"A grade is required for completed coursework: {code}"
        )

    return {
        "code": code,
        "title": title,
        "grade": grade,
        "credits": credits,
        "term": term or None,
        "level": level or None,
        "status": status
    }


# =========================================================
# 2. Build the same JSON schema as the PDF parser
# =========================================================

def build_academic_history(courses):

    normalized = [
        shared_normalize_course(course)
        for course in courses
    ]

    completed = [
        course for course in normalized
        if (
            course["status"] == "institution"
            and course["grade"] in PASSING_GRADES
        )
    ]

    transfer = [
        course for course in normalized
        if course["status"] == "transfer"
    ]

    in_progress = [
        course for course in normalized
        if course["status"] == "in_progress"
    ]

    institution_records = [
        course for course in normalized
        if course["status"] == "institution"
    ]

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
# 3. Collect courses through terminal
# =========================================================

def collect_courses():
    courses = []

    print("\nHAWKwarts Manual Course Entry")
    print("============================")
    print("Enter your courses one at a time.")
    print("Type 'done' when finished.\n")

    while True:

        code = input("Course code (or 'done'): ").strip()

        if code.lower() == "done":
            break

        title = input("Course title: ").strip()
        credits = input("Credits: ").strip()

        print("\nCourse status:")
        print("1. Completed / Institution")
        print("2. Transfer Credit")
        print("3. In Progress")

        selection = input("Select (1-3): ").strip()

        status_options = {
            "1": "institution",
            "2": "transfer",
            "3": "in_progress"
        }

        status = status_options.get(selection)

        if not status:
            print("\nInvalid selection. Please try again.\n")
            continue

        grade = None

        if status == "institution":
            grade = input("Grade (A, B+, C, etc.): ").strip()

        term = input(
            "Term (example: Fall 2025, optional): "
        ).strip()

        level = input(
            "Level (UG/GR, optional): "
        ).strip()

        course = {
            "code": code,
            "title": title,
            "credits": credits,
            "grade": grade,
            "term": term,
            "level": level,
            "status": status
        }

        try:
            normalized = shared_normalize_course(course)
            courses.append(normalized)

            print(
                f"\nAdded: {normalized['code']} - "
                f"{normalized['title']}\n"
            )

        except ValueError as error:
            print(f"\nError: {error}")
            print("Course was not added. Try again.\n")

    return courses


# =========================================================
# 4. Save results
# =========================================================

def main():

    courses = collect_courses()

    results = shared_build_academic_history(courses)

    if results["validation_errors"]:
        print("\nValidation errors found:")

        for error in results["validation_errors"]:
            print(
                f"Record {error['record']}: {error['error']}"
            )

        print("\nPlease correct these records before saving.")
        return

    output_path = Path("transcript/manual_results.json")

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        json.dumps(results, indent=2),
        encoding="utf-8"
    )

    print("\nHAWKwarts Manual Entry Summary")
    print("==============================")

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

    print("\nResults saved to:", output_path)


if __name__ == "__main__":
    main()
