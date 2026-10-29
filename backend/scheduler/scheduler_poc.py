import processscheduler as ps
import argparse
import json
import sys
from pathlib import Path

# Allow the scheduler to import the shared validator.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "transcript"))

from transcript_validator import validate_academic_history
from catalog_adapter import CatalogAdapter

# =========================================================
# 1. Load Student Academic History
# =========================================================

parser = argparse.ArgumentParser()
parser.add_argument(
    "--history",
    type=Path,
    default=BACKEND_DIR / "transcript" / "results.json",
    help="Academic history JSON from PDF or manual entry"
)
args = parser.parse_args()

with args.history.open("r", encoding="utf-8") as file:
    raw_history = json.load(file)

# Never schedule using records that were rejected earlier.
if raw_history.get("validation_errors"):
    raise ValueError(
        "Academic history contains validation errors. "
        "Correct them before scheduling."
    )

history = validate_academic_history(raw_history)

if history["validation_errors"]:
    raise ValueError(
        f"Invalid academic history: {history['validation_errors']}"
    )

completed_codes = set(history["scheduler_course_codes"])

in_progress_codes = {
    course["code"]
    for course in history["in_progress_courses"]
}

print("\nHAWKwarts Academic History Loaded")
print("=================================")
print("Completed/transfer course codes:", len(completed_codes))
print("In-progress course codes:", len(in_progress_codes))

for warning in history["warnings"]:
    print("WARNING:", warning)

# =========================================================
# Load Real Semester Course Catalogs
# =========================================================

adapter = CatalogAdapter()

SEMESTER_NAMES = {
    0: "Fall 2026",
    1: "Spring 2027",
}

print("\nHAWKwarts Course Catalog Loaded")
print("================================")

for term in SEMESTER_NAMES.values():
    print(f"{term}: {adapter.catalog.summary()[term]['courses']} courses")


# ---------------------------------------------------------
# 2. Create Scheduling Problem
# ---------------------------------------------------------

problem = ps.SchedulingProblem(
    name="HAWKwarts_Degree_Plan_POC"
)

# =========================================================
# Scheduling Configuration
# =========================================================

CREDITS_PER_COURSE = 3
MAX_CREDITS_PER_SEMESTER = 12


# =========================================================
# 3. POC Course Requirements
# =========================================================

# These are demonstration requirements, not a verified
# Illinois Tech degree audit.
COURSE_REQUIREMENTS = [
    "CS 512",
    "CS 513",
    "CS 525",
]

# Prerequisites are not enforced in this demonstration.
# Real catalog prerequisite parsing will be added later.
PREREQUISITES = {}

# Remove completed and in-progress courses.
candidate_codes = [
    code for code in COURSE_REQUIREMENTS
    if code not in completed_codes
    and code not in in_progress_codes
]

# Only include courses offered during the planning window.
remaining_codes = []
unavailable_codes = []

for code in candidate_codes:
    offered = [
        term for term in SEMESTER_NAMES.values()
        if adapter.is_offered(code, term)
    ]

    if offered:
        remaining_codes.append(code)
    else:
        unavailable_codes.append(code)

# This POC supports courses with a single, positive credit
# value that is consistent across offered semesters.
COURSE_CREDITS = {}

for code in remaining_codes:
    credit_options = set()

    for term in SEMESTER_NAMES.values():
        if adapter.is_offered(code, term):
            credit_options.update(adapter.credit_options(code, term))

    if len(credit_options) != 1:
        raise ValueError(
            f"{code}: ambiguous credit options {credit_options}. "
            "Section-level credit handling is needed."
        )

    credits = credit_options.pop()

    if credits <= 0 or int(credits) != credits:
        raise ValueError(
            f"{code}: unsupported credit value {credits}"
        )

    COURSE_CREDITS[code] = int(credits)

print("\nCatalog Availability Check")
print("==========================")

print("Candidate courses:", candidate_codes)
print("Remaining schedulable courses:", remaining_codes)
print("Unavailable courses:", unavailable_codes)
print("Course credits:", COURSE_CREDITS)

for code in remaining_codes:
    print(f"✓ {code}: {adapter.offered_terms(code)}")


for code in unavailable_codes:
    print(f"WARNING: {code} is not offered in the planning window.")


# =========================================================
# Find Available CS Courses for Testing
# =========================================================

print("\nAvailable CS Courses for Testing")
print("================================")

test_candidates = []

for code in sorted({
    code
    for term, code in adapter.catalog.courses
    if code.startswith("CS ")
}):
    if code in completed_codes or code in in_progress_codes:
        continue

    offered = adapter.offered_terms(code)

    if offered:
        test_candidates.append(code)

for code in test_candidates[:20]:
    print(
        f"{code}: "
        f"{adapter.offered_terms(code)}"
    )


# =========================================================
# Handle Empty Scheduling Problem
# =========================================================

if not remaining_codes:
    print("\nHAWKwarts Degree Plan")
    print("=====================")

    print("\nNo remaining catalog-available demonstration courses.")
    print("Skipping ProcessScheduler because there are no tasks.")

    if unavailable_codes:
        print("\nCourses requiring further planning:")
        for code in unavailable_codes:
            print(f"• {code}: not offered in Fall 2026 or Spring 2027")

    print("\nNOTE: This does not mean all degree requirements are met.")
    print("A verified degree audit is still required.")

    sys.exit(0)

# ---------------------------------------------------------
# 4. Semester Credit Capacity
# ---------------------------------------------------------

semester_capacity = ps.CumulativeWorker(
    name="Semester_Credit_Capacity",
    size=MAX_CREDITS_PER_SEMESTER
)

# =========================================================
# 5. Create Remaining Course Tasks
# =========================================================

remaining_courses = {}

for code in remaining_codes:

    task = ps.FixedDurationTask(
        name=code.replace(" ", "_"),
        duration=1
    )

    credits = COURSE_CREDITS[code]

    # Reserve one unit of capacity for each credit.
    for _ in range(credits):
        task.add_required_resource(semester_capacity)

    remaining_courses[code] = task

# =========================================================
# 6. Prerequisite Constraints
# =========================================================

for course_code, prerequisites in PREREQUISITES.items():

    if course_code not in remaining_courses:
        continue

    for prerequisite_code in prerequisites:

        if prerequisite_code in remaining_courses:
            ps.TaskPrecedence(
                task_before=remaining_courses[prerequisite_code],
                task_after=remaining_courses[course_code]
            )

        elif prerequisite_code in completed_codes:
            # Prerequisite already completed.
            pass

        elif prerequisite_code in in_progress_codes:
            # POC assumption: the in-progress course will be
            # successfully completed before the planning window.
            #
            # This must be verified before using the plan.
            pass

        else:
            raise ValueError(
                f"Cannot schedule {course_code}: "
                f"missing prerequisite {prerequisite_code}"
            )


# =========================================================
# 8. Two-Semester Scheduling Window
# =========================================================

for code, task in remaining_courses.items():

    offered_indices = [
        index
        for index, term in SEMESTER_NAMES.items()
        if adapter.is_offered(code, term)
    ]

    if not offered_indices:
        raise ValueError(
            f"No available semester for {code}"
        )

    # Restrict tasks to the two-semester planning window.
    ps.TaskStartAfter(task=task, value=0)
    ps.TaskEndBefore(task=task, value=2)

    # If offered in only one semester, force that semester.
    if len(offered_indices) == 1:
        ps.TaskStartAt(
            task=task,
            value=offered_indices[0]
        )


# ---------------------------------------------------------
# 9. Solve Scheduling Problem
# ---------------------------------------------------------

solver = ps.SchedulingSolver(
    problem=problem
)

solution = solver.solve()


# ---------------------------------------------------------
# 10. Handle Unsatisfiable Schedule
# ---------------------------------------------------------

if not solution:
    print("\nHAWKwarts Degree Plan")
    print("=====================")

    print("\nNo valid degree plan could be generated.")
    print("The scheduling constraints are unsatisfiable.")

    exit()


# ---------------------------------------------------------
# 11. Semester Mapping
# ---------------------------------------------------------
#
# Convert ProcessScheduler's integer time positions into
# semester names that make sense to the user.
# ---------------------------------------------------------

semester_names = {
    0: "Fall 2026",
    1: "Spring 2027",
}

semester_courses = {
    0: [],
    1: [],
}


# ---------------------------------------------------------
# 12. Extract Solver Results
# ---------------------------------------------------------

for course_name, task_solution in solution.tasks.items():

    semester = task_solution.start

    if semester in semester_courses:
        semester_courses[semester].append(course_name)


# ---------------------------------------------------------
# 13. Presentation-Friendly Output
# ---------------------------------------------------------

print("\nCompleted / Transfer Courses")
print("----------------------------")

for code in sorted(completed_codes):
    print(f"✓ {code}")

print("\nCurrently In Progress")
print("---------------------")

for code in sorted(in_progress_codes):
    print(f"• {code}")


for semester_number, semester_name in SEMESTER_NAMES.items():

    courses = semester_courses[semester_number]

    total_credits = 0

    print(f"\n{semester_name}")
    print("-" * len(semester_name))

    for course in sorted(courses):

        code = course.replace("_", " ")
        credits = COURSE_CREDITS[code]

        total_credits += credits

        print(f"• {code} ({credits} credits)")

    print(f"\nNewly scheduled: {total_credits} credits")


# ---------------------------------------------------------
# 14. Summary
# ---------------------------------------------------------

total_remaining_credits = sum(
    COURSE_CREDITS[code]
    for code in remaining_courses
)

print("\nPlan Summary")
print("------------")

print(
    f"Remaining credits scheduled: "
    f"{total_remaining_credits}"
)

print(
    f"Maximum credits per semester: "
    f"{MAX_CREDITS_PER_SEMESTER}"
)

print("POC prerequisite constraints applied: ✓")
print("In-progress prerequisites assumed completed before planning.")
print("Newly scheduled course credit limits satisfied: ✓")
print("Existing in-progress credit loads not yet included.")
print("Catalog prerequisite validation not yet implemented.")