
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CATALOG_DIR = PROJECT_ROOT / "banner_scraper" / "cleaned_data"


def normalize_course_id(course_id):
    """Convert course IDs like cs584 into CS 584."""
    value = " ".join(str(course_id).upper().split())

    match = re.fullmatch(r"([A-Z]{2,6})\s*(\d{3,4}[A-Z]?)", value)

    if not match:
        raise ValueError(f"Invalid course ID: {course_id}")

    return f"{match.group(1)} {match.group(2)}"


class CourseCatalog:

    def __init__(self):
        self.courses = {}
        self.terms = set()

    def load_semester(self, term):
        """Load one semester's scheduling.json file."""
        path = CATALOG_DIR / term / "scheduling.json"

        if not path.is_file():
            raise FileNotFoundError(f"Catalog not found: {path}")

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Catalog must contain a JSON object.")

        if data.get("term") != term:
            raise ValueError(
                f"Term mismatch: expected {term}, got {data.get('term')}"
            )

        courses = data.get("courses")

        if not isinstance(courses, list):
            raise ValueError("'courses' must be a list.")

        loaded = {}

        for course in courses:
            if not isinstance(course, dict):
                raise ValueError("Invalid course record.")

            code = normalize_course_id(course.get("course_id", ""))

            if code in loaded:
                raise ValueError(f"Duplicate course: {code}")

            if not isinstance(course.get("sections"), list):
                raise ValueError(f"{code}: sections must be a list.")

            loaded[code] = course

        for code, course in loaded.items():
            self.courses[(term, code)] = course

        self.terms.add(term)

    def load_all_semesters(self):
        """Load every semester folder containing scheduling.json."""
        if not CATALOG_DIR.is_dir():
            raise FileNotFoundError(
                f"Catalog directory not found: {CATALOG_DIR}"
            )

        paths = sorted(CATALOG_DIR.glob("*/scheduling.json"))

        if not paths:
            raise FileNotFoundError("No scheduling.json files found.")

        for path in paths:
            self.load_semester(path.parent.name)

    def get_course(self, course_id, term):
        """Return a course in a specific semester."""
        code = normalize_course_id(course_id)
        return self.courses.get((term, code))

    def get_sections(self, course_id, term):
        """Return all sections of a course."""
        course = self.get_course(course_id, term)
        return course.get("sections", []) if course else []

    def get_credits(self, course_id, term):
        """Return distinct credit values across sections."""
        sections = self.get_sections(course_id, term)

        return sorted({
            float(section["credits"])
            for section in sections
            if section.get("credits") is not None
        })

    def get_requirements(self, course_id, term):
        """Return prerequisite and restriction text."""
        course = self.get_course(course_id, term)

        if course is None:
            return None

        return {
            "prerequisites": course.get("prerequisites", ""),
            "general_requirements": course.get(
                "general_requirements", ""
            ),
            "restrictions": course.get("restrictions", ""),
            "mutual_exclusions": course.get(
                "mutual_exclusions", ""
            )
        }

    def get_available_sections(self, course_id, term):
        """Return sections with positive remaining seats in the snapshot."""
        return [
            section
            for section in self.get_sections(course_id, term)
            if (
                (section.get("availability") or {}).get("remaining") or 0
            ) > 0
        ]

    def summary(self):
        """Count courses and sections for each loaded semester."""
        result = {}

        for term in sorted(self.terms):
            courses = [
                course
                for (semester, _), course in self.courses.items()
                if semester == term
            ]

            result[term] = {
                "courses": len(courses),
                "sections": sum(
                    len(course["sections"]) for course in courses
                )
            }

        return result


if __name__ == "__main__":
    catalog = CourseCatalog()
    catalog.load_all_semesters()

    print("\nHAWKwarts Course Catalog")
    print("========================")

    for term, counts in catalog.summary().items():
        print(f"\n{term}")
        print("Courses:", counts["courses"])
        print("Sections:", counts["sections"])

    print("\nCourse Lookup: CS 584")
    print("------------------------")

    for term in sorted(catalog.terms):
        course = catalog.get_course("CS 584", term)

        print(f"\n{term}")

        if course is None:
            print("Not offered in this catalog.")
            continue

        print("Title:", course.get("title"))
        print("Level:", course.get("levels"))
        print("Credits:", catalog.get_credits("CS 584", term))
        print("Sections:", len(catalog.get_sections("CS 584", term)))

        requirements = catalog.get_requirements("CS 584", term)
        print("Requirements:", requirements["general_requirements"])

        available = catalog.get_available_sections("CS 584", term)
        print("Sections with remaining seats:", len(available))
