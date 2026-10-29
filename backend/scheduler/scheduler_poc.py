import processscheduler as ps
import z3
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

# =========================================================
# Existing In-Progress Semester Credits
# =========================================================

existing_semester_credits = {
    semester: 0
    for semester in SEMESTER_NAMES
}

for course in history["in_progress_courses"]:
    course_term = course.get("term")
    course_credits = course.get("credits")

    if course_credits is None:
        raise ValueError(
            f"Missing credits for in-progress course {course['code']}"
        )

    for semester, term_name in SEMESTER_NAMES.items():
        if course_term == term_name:
            existing_semester_credits[semester] += course_credits

print("\nExisting Semester Credit Loads")
print("==============================")

for semester, term_name in SEMESTER_NAMES.items():
    print(
        f"{term_name}: "
        f"{existing_semester_credits[semester]} credits"
    )

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
    "CS 513",
    "CS 514",
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


# =========================================================
# 4. Create Remaining Course Tasks
# =========================================================

remaining_courses = {}

for code in remaining_codes:
    task = ps.FixedDurationTask(
        name=code.replace(" ", "_"),
        duration=1
    )

    remaining_courses[code] = task

# =========================================================
# 5. Prerequisite Constraints
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
# 6. Two-Semester Scheduling Window
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

# =========================================================
# 7. Semester Credit Capacity Constraints
# =========================================================

for semester in SEMESTER_NAMES:

    newly_scheduled_credits = z3.Sum([
        z3.If(
            task._start == semester,
            COURSE_CREDITS[code],
            0
        )
        for code, task in remaining_courses.items()
    ])

    total_semester_credits = (
        newly_scheduled_credits
        + existing_semester_credits[semester]
    )

    ps.ConstraintFromExpression(
        name=f"Semester_{semester}_Credit_Limit",
        expression=(
            total_semester_credits <= MAX_CREDITS_PER_SEMESTER
        )
    )

# ---------------------------------------------------------
# 8. Solve Scheduling Problem
# ---------------------------------------------------------

solver = ps.SchedulingSolver(
    problem=problem
)

solution = solver.solve()


# ---------------------------------------------------------
# 9. Handle Unsatisfiable Schedule
# ---------------------------------------------------------

if not solution:
    print("\nHAWKwarts Degree Plan")
    print("=====================")

    print("\nNo valid degree plan could be generated.")
    print("The scheduling constraints are unsatisfiable.")

    exit()


# ---------------------------------------------------------
# 10. Semester Mapping
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
# 11. Extract Solver Results
# ---------------------------------------------------------

for course_name, task_solution in solution.tasks.items():

    semester = task_solution.start

    if semester in semester_courses:
        semester_courses[semester].append(course_name)


# ---------------------------------------------------------
# 12. Presentation-Friendly Output
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
# 13. Summary
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

print(
    "POC prerequisite constraints applied:",
    "✓" if PREREQUISITES else "None (demo only)"
)
print("In-progress prerequisites assumed completed before planning.")
print("Combined existing and newly scheduled credit limits satisfied: ✓")
print("Existing in-progress semester credits included.")
print("Catalog prerequisite validation not yet implemented.")

# =========================================================
# 14. Export Semester Plan to JSON
# =========================================================

def export_schedule_json(
    semester_courses,
    existing_courses,
    course_credits,
    semester_names,
    max_credits,
    output_path
):
    semesters = []

    for semester_index, semester_name in semester_names.items():

        # Courses already registered for this semester.
        enrolled = [
            {
                "code": course["code"],
                "title": course.get("title"),
                "credits": course["credits"],
                "status": "in_progress"
            }
            for course in existing_courses
            if course.get("term") == semester_name
        ]

        # Courses assigned by the scheduler.
        planned = []

        for task_name in semester_courses[semester_index]:
            code = task_name.replace("_", " ")

            planned.append({
                "code": code,
                "credits": course_credits[code],
                "status": "planned"
            })

        existing_credits = sum(
            course["credits"] for course in enrolled
        )

        planned_credits = sum(
            course["credits"] for course in planned
        )

        semesters.append({
            "term": semester_name,
            "existing_courses": enrolled,
            "planned_courses": planned,
            "existing_credits": existing_credits,
            "planned_credits": planned_credits,
            "total_credits": existing_credits + planned_credits,
            "max_credits": max_credits,
            "remaining_capacity": (
                max_credits - existing_credits - planned_credits
            )
        })

    output = {
        "schema_version": "1.0",
        "status": "success",
        "semesters": semesters,
        "total_planned_credits": sum(
            semester["planned_credits"]
            for semester in semesters
        ),
        "notes": [
            "This is a demonstration schedule, not a verified degree audit.",
            "Catalog prerequisites and section time conflicts are not yet validated.",
            "In-progress courses are included in semester credit limits."
        ]
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    return output_path


# =========================================================
# 15. Generate JSON Output
# =========================================================

OUTPUT_PATH = BACKEND_DIR / "scheduler" / "results" / "schedule.json"

saved_path = export_schedule_json(
    semester_courses=semester_courses,
    existing_courses=history["in_progress_courses"],
    course_credits=COURSE_CREDITS,
    semester_names=SEMESTER_NAMES,
    max_credits=MAX_CREDITS_PER_SEMESTER,
    output_path=OUTPUT_PATH
)

print(f"\nSchedule JSON exported to: {saved_path}")