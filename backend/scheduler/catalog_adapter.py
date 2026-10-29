
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from catalog.course_catalog import CourseCatalog, normalize_course_id


class CatalogAdapter:
    """Connect semester course catalogs to the scheduler."""

    def __init__(self, catalog=None):
        self.catalog = catalog or CourseCatalog()

        if catalog is None:
            self.catalog.load_all_semesters()

    def offered_terms(self, course_id):
        """Find semesters in which a course is offered."""
        code = normalize_course_id(course_id)

        return [
            term
            for term in sorted(self.catalog.terms)
            if self.catalog.get_course(code, term) is not None
        ]

    def is_offered(self, course_id, term):
        """Check whether a course exists in a semester catalog."""
        return self.catalog.get_course(course_id, term) is not None

    def credit_options(self, course_id, term):
        """Get the possible credit values for course sections."""
        return self.catalog.get_credits(course_id, term)

    def course_info(self, course_id, term):
        """Return the course information needed for scheduling."""
        code = normalize_course_id(course_id)
        course = self.catalog.get_course(code, term)

        if course is None:
            return None

        return {
            "course_id": code,
            "term": term,
            "title": course.get("title", ""),
            "levels": course.get("levels", ""),
            "credit_options": self.credit_options(code, term),
            "section_count": len(
                self.catalog.get_sections(code, term)
            ),
            "requirements": self.catalog.get_requirements(
                code, term
            ),
        }

    def planning_options(self, course_id):
        """Summarize course availability across loaded semesters."""
        code = normalize_course_id(course_id)

        return {
            "course_id": code,
            "offered_terms": self.offered_terms(code),
            "semesters": {
                term: self.course_info(code, term)
                for term in self.offered_terms(code)
            },
        }


if __name__ == "__main__":
    adapter = CatalogAdapter()

    print("\nHAWKwarts Catalog Adapter")
    print("=========================")

    test_courses = [
        "CS 584",
        "CS 450",
        "CS 583",
        "IPRO 497",
    ]

    for course_id in test_courses:
        options = adapter.planning_options(course_id)

        print(f"\nCourse: {course_id}")
        print("Offered terms:", options["offered_terms"])

        for term, info in options["semesters"].items():
            print(
                f"  {term}: "
                f"{info['credit_options']} credits, "
                f"{info['section_count']} sections"
            )
