import processscheduler as ps
import z3
import argparse
import json
import sys
from pathlib import Path
from backend.scheduler.course_level import get_course_level
from backend.scheduler.schedule_export import export_failure_json
from courses_rag.requirements_lookup import get_requirements
from backend.scheduler.requirement_resolver import resolve_requirements
from backend.scheduler.pathway_scheduler import (prepare_pathway_options)

BACKEND_DIR = Path(__file__).resolve().parents[1]

from backend.transcript.transcript_validator import validate_academic_history
from backend.scheduler.catalog_adapter import CatalogAdapter
from backend.scheduler.prerequisite_constraints import build_prerequisite_constraint
from backend.scheduler.prerequisite_expression import parse_expression
from backend.scheduler.prerequisite_parser import (
    parse_prerequisites,
    extract_prerequisite_details,
)

from backend.scheduler.credit_policy import get_credit_policy

def get_banner_course(course_code, semester_name):
    """
    Retrieve a course's Banner record for a specific semester.

    Returns None if the course is not present in that catalog.
    """

    catalog_path = (
        Path(__file__).resolve().parents[2]
        / "banner_scraper"
        / "cleaned_data"
        / semester_name
        / "scheduling.json"
    )

    with catalog_path.open("r", encoding="utf-8") as file:
        catalog = json.load(file)

    for course in catalog["courses"]:
        if course["course_id"] == course_code:
            return course

    return None

# =========================================================
# Export Unsuccessful Scheduling Results
# =========================================================

def export_failure_json(
    output_path,
    status,
    message,
    candidate_courses,
    unavailable_courses
):
    output = {
        "schema_version": "1.0",
        "status": status,
        "message": message,
        "candidate_courses": candidate_courses,
        "unavailable_courses": unavailable_courses,
        "semesters": [],
        "total_planned_credits": 0,
        "notes": [
            "No valid semester plan was generated.",
            "The schedule is a demonstration, not a verified degree audit."
        ]
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    return output_path

# =========================================================
# Export Semester Plan to JSON
# =========================================================

def export_schedule_json(
    semester_courses,
    existing_courses,
    course_credits,
    semester_names,
    max_credits,
    output_path,
    academic_level,
    enrollment_status,
    min_credits
):
    semesters = []

    for semester_index, semester_name in semester_names.items():

        # Courses already registered for this semester.
        enrolled = [
            {
                "code": course["code"],
                "title": course.get("title"),
                "credits": course["credits"],
                "course_level": get_course_level(course["code"]),
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
                "course_level": get_course_level(code),
                "status": "planned"
            })

        # Total credits from existing in-progress courses.
        existing_credits = sum(
            course["credits"] for course in enrolled
        )

        # Breakdown of existing in-progress credits by course level.
        existing_undergraduate_credits = sum(
            course["credits"]
            for course in enrolled
            if course["course_level"] == "undergraduate"
        )

        existing_graduate_credits = sum(
            course["credits"]
            for course in enrolled
            if course["course_level"] == "graduate"
        )

        existing_unknown_level_credits = sum(
            course["credits"]
            for course in enrolled
            if course["course_level"] == "unknown"
        )

        planned_credits = sum(
            course["credits"] for course in planned
        )

        # Breakdown of newly scheduled credits by course level.
        planned_undergraduate_credits = sum(
            course["credits"]
            for course in planned
            if course["course_level"] == "undergraduate"
        )

        planned_graduate_credits = sum(
            course["credits"]
            for course in planned
            if course["course_level"] == "graduate"
        )

        planned_unknown_level_credits = sum(
            course["credits"]
            for course in planned
            if course["course_level"] == "unknown"
        )

        total_credits = existing_credits + planned_credits

        # Combined existing and planned credits by course level.
        total_undergraduate_credits = (
            existing_undergraduate_credits
            + planned_undergraduate_credits
        )

        total_graduate_credits = (
            existing_graduate_credits
            + planned_graduate_credits
        )

        total_unknown_level_credits = (
            existing_unknown_level_credits
            + planned_unknown_level_credits
        )

        enrollment_warnings = []

        if total_credits < min_credits:
            enrollment_warnings.append(
                f"Semester credit load is below the configured "
                f"{enrollment_status} minimum of {min_credits} credits. "
                "The course plan may be incomplete."
            )

        if total_credits > max_credits:
            enrollment_warnings.append(
                f"Semester credit load exceeds the configured "
                f"maximum of {max_credits} credits."
            )
        
        semesters.append({
            "term": semester_name,
            "existing_courses": enrolled,
            "planned_courses": planned,
            "existing_credits": existing_credits,
            "planned_credits": planned_credits,
            "existing_undergraduate_credits": existing_undergraduate_credits,
            "existing_graduate_credits": existing_graduate_credits,
            "existing_unknown_level_credits": existing_unknown_level_credits,
            "total_credits": total_credits,
            "total_undergraduate_credits": total_undergraduate_credits,
            "total_graduate_credits": total_graduate_credits,
            "total_unknown_level_credits": total_unknown_level_credits,
            "planned_undergraduate_credits": planned_undergraduate_credits,
            "planned_graduate_credits": planned_graduate_credits,
            "planned_unknown_level_credits": planned_unknown_level_credits,
            "min_credits": min_credits,
            "max_credits": max_credits,
            "remaining_capacity": max_credits - total_credits,
            "enrollment_warnings": enrollment_warnings
        })

    # Overall credit breakdown across the planning window.
    overall_undergraduate_credits = sum(
        semester["total_undergraduate_credits"]
        for semester in semesters
    )

    overall_graduate_credits = sum(
        semester["total_graduate_credits"]
        for semester in semesters
    )

    overall_unknown_level_credits = sum(
        semester["total_unknown_level_credits"]
        for semester in semesters
    )

    overall_total_credits = sum(
        semester["total_credits"]
        for semester in semesters
    )


    output = {
        "schema_version": "1.0",
        "status": "success",
        "academic_level": academic_level,
        "enrollment_status": enrollment_status,
        "semesters": semesters,
        "credit_summary": {
            "undergraduate_credits": overall_undergraduate_credits,
            "graduate_credits": overall_graduate_credits,
            "unknown_level_credits": overall_unknown_level_credits,
            "total_credits": overall_total_credits
        },
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
# 1. Load Student Academic History
# =========================================================

parser = argparse.ArgumentParser()

parser.add_argument(
    "--history",
    type=Path,
    default=BACKEND_DIR / "transcript" / "results.json",
    help="Academic history JSON from PDF or manual entry"
)

parser.add_argument(
    "--academic-level",
    choices=["undergraduate", "graduate", "coterminal"],
    default="undergraduate",
    help="Student academic level"
)

parser.add_argument(
    "--enrollment-status",
    choices=["full_time", "part_time"],
    default="full_time",
    help="Student enrollment status"
)

parser.add_argument(
    "--program-id",
    type=str,
    required=True,
    help="Exact academic program ID from the requirements catalog"
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

OUTPUT_PATH = BACKEND_DIR / "scheduler" / "results" / "schedule.json"

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

# Student academic enrollment configuration
ACADEMIC_LEVEL = args.academic_level
ENROLLMENT_STATUS = args.enrollment_status

# Load the applicable academic credit policy
credit_policy = get_credit_policy(
    ACADEMIC_LEVEL,
    ENROLLMENT_STATUS,
)

MIN_CREDITS_PER_SEMESTER = credit_policy["minimum"]
MAX_CREDITS_PER_SEMESTER = credit_policy["maximum"]

print("\nHAWKwarts Academic Credit Policy")
print("================================")
print(f"Academic level: {ACADEMIC_LEVEL}")
print(f"Enrollment status: {ENROLLMENT_STATUS}")
print(f"Enrollment minimum: {MIN_CREDITS_PER_SEMESTER}")
print(f"Maximum semester credits: {MAX_CREDITS_PER_SEMESTER}")

# =========================================================
# 3. Dynamic Degree Requirements
# =========================================================
program = get_requirements("program", args.program_id)

if program is None:
    raise ValueError(
        f"Academic program not found: {args.program_id}"
    )

resolved = resolve_requirements(program, history)

# Prepare unfinished alternative programming pathways.
prepared_pathways = prepare_pathway_options(
    unsatisfied_pathways=resolved["unsatisfied_pathways"],
    completed_codes=completed_codes,
    in_progress_codes=in_progress_codes
)

# Start with ordinary mandatory degree requirements.
COURSE_REQUIREMENTS = list(resolved["remaining_courses"])

# Add remaining courses from pathways the student
# has already started.
for pathway in prepared_pathways:
    if pathway["mode"] == "required":
        COURSE_REQUIREMENTS.extend(
            pathway["required_courses"]
        )

# Avoid duplicate mandatory scheduling tasks.
COURSE_REQUIREMENTS = list(dict.fromkeys(COURSE_REQUIREMENTS))

# Collect courses belonging to unstarted alternative pathways.
# These will become optional Z3 scheduling tasks.
PATHWAY_CHOICE_CODES = []

for pathway in prepared_pathways:
    if pathway["mode"] != "choice":
        continue

    for option in pathway["options"]:
        for code in option:
            if (
                code not in completed_codes
                and code not in in_progress_codes
                and code not in COURSE_REQUIREMENTS
            ):
                PATHWAY_CHOICE_CODES.append(code)

# Avoid creating duplicate optional pathway tasks.
PATHWAY_CHOICE_CODES = list(dict.fromkeys(PATHWAY_CHOICE_CODES))

print("\nHAWKwarts Pathway Scheduling")
print("===========================")

for pathway in prepared_pathways:
    print("Pathway:", pathway["name"])
    print("Mode:", pathway["mode"])

    if pathway["mode"] == "required":
        print("Required courses:", pathway["required_courses"])
    else:
        print("Available alternatives:", pathway["options"])

# Identify catalog-available options for outstanding choice groups.
CHOICE_GROUP_CANDIDATES = []

for group in resolved["choice_groups"]:
    available_options = [
        code
        for code in group["options"]
        if code not in completed_codes
        and code not in in_progress_codes
        and any(
            adapter.is_offered(code, term)
            for term in SEMESTER_NAMES.values()
        )
    ]

    CHOICE_GROUP_CANDIDATES.append({
        **group,
        "available_options": available_options
    })

print("\nHAWKwarts Choice Group Candidates")
print("=================================")

for group in CHOICE_GROUP_CANDIDATES:
    print("Group:", group["group"])
    print("Required:", group["remaining_count"])
    print("Available:", group["available_options"])

print("\nHAWKwarts Degree Requirements")
print("============================")
print("Program:", program.get("title"))
print("Remaining mandatory courses:", len(COURSE_REQUIREMENTS))
print("Outstanding choice groups:", len(resolved["choice_groups"]))
print(
    "Unresolved requirement items:",
    len(resolved["unresolved_requirements"])
)

if resolved["choice_groups"] or resolved["unresolved_requirements"]:
    print(
        "WARNING: This plan covers mandatory courses only. "
        "Elective choices and unresolved requirements "
        "are not yet included."
    )

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
            credit_options.update(
                adapter.credit_options(code, term)
            )

    # Zero-credit components (such as labs) do not
    # contribute additional semester credits.
    positive_credit_options = {
        credits
        for credits in credit_options
        if credits > 0
    }

    if len(positive_credit_options) != 1:
        raise ValueError(
            f"{code}: ambiguous positive credit options "
            f"{positive_credit_options}. "
            "Section-level credit handling is needed."
        )

    credits = positive_credit_options.pop()

    if credits <= 0 or int(credits) != credits:
        raise ValueError(
            f"{code}: unsupported credit value {credits}"
        )

    COURSE_CREDITS[code] = int(credits)

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

if (
    not remaining_codes
    and not any(
        group["remaining_count"] > 0
        and group["available_options"]
        for group in CHOICE_GROUP_CANDIDATES
    )
    and not any(
        pathway["mode"] == "choice"
        and any(
            all(
                code in PATHWAY_CHOICE_CODES
                for code in option
            )
            for option in pathway["options"]
        )
        for pathway in prepared_pathways
    )
):
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

    saved_path = export_failure_json(
        output_path=OUTPUT_PATH,
        status="no_schedulable_courses",
        message=(
            "No remaining courses are available "
            "for scheduling in the selected semesters."
        ),
        candidate_courses=candidate_codes,
        unavailable_courses=unavailable_codes
    )

    print(f"\nSchedule status JSON exported to: {saved_path}")

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

# Create optional tasks for unstarted alternative pathways.
pathway_courses = {}

for code in PATHWAY_CHOICE_CODES:
    # Avoid duplicating an existing mandatory task.
    if code in remaining_courses:
        continue

    # Only create tasks for courses offered in the planning window.
    if not any(
        adapter.is_offered(code, term)
        for term in SEMESTER_NAMES.values()
    ):
        print(
            f"WARNING: Pathway course {code} is unavailable "
            "in the planning window."
        )
        continue

    task = ps.FixedDurationTask(
        name=code.replace(" ", "_"),
        duration=1,
        optional=True
    )

    pathway_courses[code] = task

print("\nHAWKwarts Optional Pathway Tasks")
print("===============================")
print("Optional pathway courses:", list(pathway_courses))

# Create optional tasks for outstanding elective choice groups.
elective_courses = {}

for group in CHOICE_GROUP_CANDIDATES:
    if group["remaining_count"] <= 0:
        continue

    for code in group["available_options"]:
        if code in remaining_courses:
            continue

        if code in elective_courses:
            continue

        # Reuse an existing pathway task instead of creating
        # another scheduling task for the same course.
        if code in pathway_courses:
            elective_courses[code] = pathway_courses[code]
            continue

        task = ps.FixedDurationTask(
            name=code.replace(" ", "_"),
            duration=1,
            optional=True
        )

        elective_courses[code] = task

print("\nHAWKwarts Elective Tasks")
print("=======================")
print("Optional elective tasks:", list(elective_courses))

# =========================================================
# Alternative Pathway Selection Constraints
# =========================================================

# Explicitly track which alternative is selected for each pathway.
pathway_selection_vars = {}

for pathway_index, pathway in enumerate(prepared_pathways):
    if pathway["mode"] != "choice":
        continue

    for option_index, option in enumerate(pathway["options"]):
        pathway_selection_vars[(pathway_index, option_index)] = z3.Bool(
            f"pathway_selected_{pathway_index}_{option_index}"
        )

for pathway_index, pathway in enumerate(prepared_pathways):

    if pathway["mode"] != "choice":
        continue

    # Each option represents a complete course pathway.
    option_conditions = []

    for option in pathway["options"]:

        # An option is available only if all its courses
        # have corresponding scheduling tasks.
        if not all(
            code in pathway_courses
            for code in option
        ):
            continue

        
        # Selecting a pathway requires all courses in that
        # alternative to be scheduled. Courses belonging to
        # other alternatives may be scheduled independently.
        option_conditions.append(
            z3.And(
                *[
                    pathway_courses[code]._scheduled
                    for code in option
                ]
            )
        )

    if not option_conditions:
        raise ValueError(
            f"No schedulable alternatives for "
            f"pathway: {pathway['name']}"
        )

    # Link explicit selection variables to the existing
    # complete-pathway conditions.
    available_selection_vars = []

    for option_index, option in enumerate(pathway["options"]):
        if not all(
            code in pathway_courses
            for code in option
        ):
            continue

        selection_var = pathway_selection_vars[
            (pathway_index, option_index)
        ]

        # Match the available option conditions in their
        # original iteration order.
        condition = option_conditions[len(available_selection_vars)]

        ps.ConstraintFromExpression(
            name=f"Pathway_Selection_Link_{pathway_index}_{option_index}",
            expression=z3.Implies(
                selection_var,
                condition
            )
        )

        available_selection_vars.append((selection_var, 1))

    # Require exactly one selected pathway alternative.
    ps.ConstraintFromExpression(
        name=f"Pathway_Choice_{pathway_index}",
        expression=z3.PbEq(
            available_selection_vars,
            1
        )
    )

    print(
        f"Pathway '{pathway['name']}': "
        f"select exactly one of "
        f"{len(option_conditions)} alternatives"
    )

# Track which elective requirement receives credit for each course.
# A scheduled course and a requirement assignment are distinct.
elective_assignments = {}

# Require the correct number of electives from each choice group.
for group_index, group in enumerate(CHOICE_GROUP_CANDIDATES):
    required_count = group["remaining_count"]

    if required_count <= 0:
        continue

    options = [
        code
        for code in group["available_options"]
        if code in elective_courses
    ]

    if len(options) < required_count:
        raise ValueError(
            f"Not enough available courses for "
            f"{group['group']}: need {required_count}, "
            f"found {len(options)}"
        )

    # Create one assignment variable per eligible course and group.
    assignment_pairs = []

    for code in options:
        assignment = z3.Bool(
            f"elective_assignment_{group_index}_{code.replace(' ', '_')}"
        )

        elective_assignments[(group_index, code)] = assignment
        assignment_pairs.append((assignment, 1))

        # A course cannot satisfy a requirement unless scheduled.
        ps.ConstraintFromExpression(
            name=(
                f"Elective_Assignment_Scheduled_"
                f"{group_index}_{code.replace(' ', '_')}"
            ),
            expression=z3.Implies(
                assignment,
                elective_courses[code]._scheduled
            )
        )

    # Exactly the required number of courses must be assigned.
    ps.ConstraintFromExpression(
        name=f"Choice_Group_{group_index}",
        expression=z3.PbEq(
            assignment_pairs,
            required_count
        )
    )

    print(
        f"Choice group '{group['group']}': "
        f"select {required_count} of {len(options)} courses"
    )

    # Prevent one scheduled course from satisfying multiple
    # exclusive elective requirements.
    elective_assignment_codes = sorted({
        code
        for _, code in elective_assignments
    })

    for code in elective_assignment_codes:
        assignments_for_course = [
            assignment
            for (group_index, course_code), assignment
            in elective_assignments.items()
            if course_code == code
        ]

        if len(assignments_for_course) <= 1:
            continue

        ps.ConstraintFromExpression(
            name=f"Elective_Exclusive_{code.replace(' ', '_')}",
            expression=z3.PbLe(
                [
                    (assignment, 1)
                    for assignment in assignments_for_course
                ],
                1
            )
        )

        print(
            f"Elective exclusivity enforced for {code}: "
            f"{len(assignments_for_course)} eligible groups"
        )

# =========================================================
# Prevent Pathway / Elective Requirement Double-Counting
# =========================================================

# An elective assignment cannot use a course that belongs
# to the selected alternative of an exclusive pathway.
for (group_index, code), assignment in elective_assignments.items():

    if code not in pathway_courses:
        continue

    for pathway_index, pathway in enumerate(prepared_pathways):

        if pathway["mode"] != "choice":
            continue

        for option_index, option in enumerate(pathway["options"]):

            if code not in option:
                continue

            ps.ConstraintFromExpression(
                name=(
                    f"Pathway_Elective_Exclusive_"
                    f"{group_index}_{pathway_index}_"
                    f"{option_index}_{code.replace(' ', '_')}"
                ),
                expression=z3.Implies(
                    pathway_selection_vars[
                        (pathway_index, option_index)
                    ],
                    z3.Not(assignment)
                )
            )

# =========================================================
# 5. Real Banner Prerequisite Constraints
# =========================================================

in_progress_terms = {}

for course in history["in_progress_courses"]:
    term_name = course.get("term")

    for term_index, semester_name in SEMESTER_NAMES.items():
        if term_name == semester_name:
            in_progress_terms[course["code"]] = term_index

prerequisite_constraint_count = 0

for course_code, task in {**remaining_courses, **elective_courses, **pathway_courses}.items():
    for term_index, semester_name in SEMESTER_NAMES.items():

        if not adapter.is_offered(course_code, semester_name):
            continue

        banner_course = get_banner_course(course_code, semester_name)

        if banner_course is None:
            raise ValueError(
                f"Missing Banner record for {course_code} "
                f"in {semester_name}"
            )

        indicator = (
            banner_course.get("prerequisites") or ""
        ).strip()

        general = (
            banner_course.get("general_requirements") or ""
        ).strip()

        if not indicator and not general:
            continue

        parsed = parse_prerequisites(indicator, general)

        details = extract_prerequisite_details(general)

        detail_lookup = {
            detail["code"]: detail
            for detail in details
            if detail.get("range_end") is None
        }

        range_details = [
            detail
            for detail in details
            if detail.get("range_end") is not None
        ]

        for detail in range_details:
            range_key = (
                f'{detail["code"]} to {detail["range_end"]}'
            )
            detail_lookup[range_key] = detail

        def has_missing_range_metadata(node):
            if node["type"] == "course_range":
                range_code = (
                    f'{node["subject"]} {node["start"]:03d}'
                )

                return not any(
                    detail["code"] == range_code
                    and detail.get("range_end") == node["end"]
                    for detail in details
                )

            return any(
                has_missing_range_metadata(child)
                for child in node.get("children", [])
            )

        if general:
            if (
                parsed["status"] != "parsed"
                or parsed["logic"] not in ("SINGLE", "OR", "AND", "course_range", "placement_requirement")
            ):
                if (
                    course_code in elective_courses
                    or course_code in pathway_courses
                ):
                    ps.ConstraintFromExpression(
                        name=(
                            f"Unverified_Prerequisites_"
                            f"{course_code.replace(' ', '_')}_"
                            f"{term_index}"
                        ),
                        expression=z3.Implies(
                            task._start == term_index,
                            z3.Not(task._scheduled)
                        )
                    )
                    print(
                        f"WARNING: {course_code} has unsupported "
                        f"Banner prerequisites in {semester_name}. "
                        f"Selection is prohibited for this term."
                    )
                    continue
                raise ValueError(
                    f"Unsupported Banner prerequisites for "
                    f"{course_code}: {general}"
                )
            
            if (
                any(
                    code not in detail_lookup
                    or detail_lookup[code].get("range_end") is not None
                    for code in parsed["courses"]
                )
                or (
                    parsed.get("expression") is not None
                    and has_missing_range_metadata(
                        parsed["expression"]
                    )
                )
            ):

                if (
                    course_code in elective_courses
                    or course_code in pathway_courses
                ):
                    ps.ConstraintFromExpression(
                        name=(
                            f"Incomplete_Prerequisite_Metadata_"
                            f"{course_code.replace(' ', '_')}_"
                            f"{term_index}"
                        ),
                        expression=z3.Implies(
                            task._start == term_index,
                            z3.Not(task._scheduled)
                        )
                    )

                    print(
                        f"WARNING: {course_code} has incomplete "
                        f"prerequisite metadata in {semester_name}. "
                        f"Selection is prohibited for this term."
                    )

                    continue

                raise ValueError(
                    f"Incomplete Banner prerequisite metadata "
                    f"for {course_code}"
                )

            expression_text = (
                parsed.get("expression")
                or " or ".join(parsed["courses"])
            )

        else:
            expression_text = indicator

        try:
            expression = (
                expression_text
                if isinstance(expression_text, dict)
                else parse_expression(expression_text)
            )
        except ValueError as error:
            if (
                course_code in elective_courses
                or course_code in pathway_courses
            ):
                ps.ConstraintFromExpression(
                    name=(
                        f"Unparseable_Prerequisites_"
                        f"{course_code.replace(' ', '_')}_"
                        f"{term_index}"
                    ),
                    expression=z3.Implies(
                        task._start == term_index,
                        z3.Not(task._scheduled)
                    )
                )
                print(
                    f"WARNING: Cannot parse prerequisites "
                    f"for {course_code} in {semester_name}. "
                    f"Selection is prohibited for this term."
                )
                continue

            raise ValueError(
                f"Cannot parse prerequisites for "
                f"{course_code}: {expression_text}"
            ) from error

        constraint = build_prerequisite_constraint(
            expression=expression,
            history=history,
            target_start=task._start,
            scheduled_tasks={**remaining_courses, **elective_courses, **pathway_courses},
            detail_lookup=detail_lookup,
            in_progress_terms=in_progress_terms
        )

        # Apply this catalog rule only if the course
        # is assigned to the corresponding semester.
        ps.ConstraintFromExpression(
            name=(
                f"Prerequisite_"
                f"{course_code.replace(' ', '_')}_"
                f"{term_index}"
            ),
            expression=z3.Implies(
                z3.And(
                    task._scheduled,
                    task._start == term_index
                ),
                constraint
            )
        )

        prerequisite_constraint_count += 1

print(
    f"\nBanner prerequisite constraints added: "
    f"{prerequisite_constraint_count}"
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

    # A course can only be scheduled in a semester
    # where Banner confirms that it is offered.
    ps.ConstraintFromExpression(
        name=f"Availability_{code.replace(' ', '_')}",
        expression=z3.Or([
            task._start == index
            for index in offered_indices
        ])
    )

# Apply semester availability constraints to optional electives.
for code, task in elective_courses.items():

    offered_indices = [
        index
        for index, term in SEMESTER_NAMES.items()
        if adapter.is_offered(code, term)
    ]

    if not offered_indices:
        raise ValueError(
            f"No available semester for elective {code}"
        )

    # Only constrain semester placement when selected.
    ps.ConstraintFromExpression(
        name=f"Elective_Availability_{code.replace(' ', '_')}",
        expression=z3.Implies(
            task._scheduled,
            z3.Or([
                task._start == index
                for index in offered_indices
            ])
        )
    )

print(
    "Elective availability constraints added:",
    len(elective_courses)
)

# Apply semester availability constraints to optional pathway courses.
for code, task in pathway_courses.items():

    offered_indices = [
        index
        for index, term in SEMESTER_NAMES.items()
        if adapter.is_offered(code, term)
    ]

    if not offered_indices:
        raise ValueError(
            f"No available semester for pathway course {code}"
        )

    ps.ConstraintFromExpression(
        name=f"Pathway_Availability_{code.replace(' ', '_')}",
        expression=z3.Implies(
            task._scheduled,
            z3.Or([
                task._start == index
                for index in offered_indices
            ])
        )
    )

print(
    "Pathway availability constraints added:",
    len(pathway_courses)
)

# Determine credit values for elective candidates.
ELECTIVE_CREDITS = {}

for code in elective_courses:
    credit_options = set()

    for term in SEMESTER_NAMES.values():
        if adapter.is_offered(code, term):
            credit_options.update(
                adapter.credit_options(code, term)
            )

    positive_credits = {
        credits for credits in credit_options
        if credits > 0
    }

    if len(positive_credits) != 1:
        raise ValueError(
            f"{code}: ambiguous elective credit values "
            f"{positive_credits}"
        )

    credits = positive_credits.pop()

    if int(credits) != credits:
        raise ValueError(
            f"{code}: fractional elective credits "
            f"are not yet supported"
        )

    ELECTIVE_CREDITS[code] = int(credits)

print("Elective credits:", ELECTIVE_CREDITS)

# Determine credit values for optional pathway courses.
PATHWAY_CREDITS = {}

for code in pathway_courses:
    credit_options = set()

    for term in SEMESTER_NAMES.values():
        if adapter.is_offered(code, term):
            credit_options.update(
                adapter.credit_options(code, term)
            )

    positive_credits = {
        credits
        for credits in credit_options
        if credits > 0
    }

    if len(positive_credits) != 1:
        raise ValueError(
            f"{code}: ambiguous pathway credit values "
            f"{positive_credits}"
        )

    credits = positive_credits.pop()

    if int(credits) != credits:
        raise ValueError(
            f"{code}: fractional pathway credits "
            "are not yet supported"
        )

    PATHWAY_CREDITS[code] = int(credits)

print("Pathway credits:", PATHWAY_CREDITS)

# =========================================================
# 7. Semester Credit Capacity Constraints
# =========================================================

for semester in SEMESTER_NAMES:

    mandatory_credits = z3.Sum([
        z3.If(
            task._start == semester,
            COURSE_CREDITS[code],
            0
        )
        for code, task in remaining_courses.items()
    ])

    # Count electives only when they are not already
    # included in the pathway credit calculation.
    elective_credits = z3.Sum([
        z3.If(
            z3.And(
                task._scheduled,
                task._start == semester
            ),
            ELECTIVE_CREDITS[code],
            0
        )
        for code, task in elective_courses.items()
        if code not in pathway_courses
    ])

    pathway_credits = z3.Sum([
    z3.If(
        z3.And(
            task._scheduled,
            task._start == semester
        ),
        PATHWAY_CREDITS[code],
        0
    )
    for code, task in pathway_courses.items()
])

    newly_scheduled_credits = (
        mandatory_credits
        + elective_credits
        + pathway_credits
    )

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

    message = (
        "No valid schedule satisfies all configured constraints. "
        "Possible conflicts include semester availability, "
        "credit limits, and Banner prerequisites. "
        "Review the course requirements and planning window."
    )

    print(f"\n{message}")

    saved_path = export_failure_json(
        output_path=OUTPUT_PATH,
        status="unsatisfiable",
        message=message,
        candidate_courses=candidate_codes,
        unavailable_courses=unavailable_codes
    )

    print(f"\nFailure JSON exported to: {saved_path}")

    sys.exit(0)


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
    # Exclude optional courses that Z3 did not select.
    if not task_solution.scheduled:
        continue

    semester = task_solution.start

    if semester in semester_courses:
        semester_courses[semester].append(course_name)

# Combine credit values for all scheduling task categories.
ALL_COURSE_CREDITS = {
    **COURSE_CREDITS,
    **ELECTIVE_CREDITS,
    **PATHWAY_CREDITS
}

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
        
        credits = ALL_COURSE_CREDITS[code]

        total_credits += credits

        print(f"• {code} ({credits} credits)")

    print(f"\nNewly scheduled: {total_credits} credits")


# =========================================================
# Enrollment Status Validation
# =========================================================

print("\nEnrollment Status Validation")
print("============================")

for semester_index, semester_name in SEMESTER_NAMES.items():

    existing_credits = existing_semester_credits[semester_index]

    planned_credits = sum(
        ALL_COURSE_CREDITS[course.replace("_", " ")]
        for course in semester_courses[semester_index]
    )

    total_credits = existing_credits + planned_credits

    print(f"\n{semester_name}")
    print(f"Existing credits: {existing_credits}")
    print(f"Planned credits: {planned_credits}")
    print(f"Total credits: {total_credits}")

    if total_credits < MIN_CREDITS_PER_SEMESTER:
        print(
            f"WARNING: Below the configured "
            f"{ENROLLMENT_STATUS} enrollment minimum "
            f"of {MIN_CREDITS_PER_SEMESTER} credits."
        )
        print(
            "This may be an incomplete course plan. "
            "Verify enrollment requirements before registration."
        )

    elif total_credits <= MAX_CREDITS_PER_SEMESTER:
        print(
            "✓ Credit load meets the configured "
            "enrollment range."
        )

    else:
        print(
            "WARNING: Credit load exceeds the "
            "configured semester maximum."
        )

# ---------------------------------------------------------
# 13. Summary
# ---------------------------------------------------------

total_remaining_credits = sum(
    ALL_COURSE_CREDITS[course.replace("_", " ")]
    for courses in semester_courses.values()
    for course in courses
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
    "Banner prerequisite constraints applied:",
    prerequisite_constraint_count
)

print(
    "Supported Banner prerequisite expressions enforced: ✓"
)

print(
    "In-progress prerequisites are conditional "
    "on successful course completion."
)

print(
    "Combined existing and newly scheduled "
    "credit limits satisfied: ✓"
)

print(
    "Existing in-progress semester credits included: ✓"
)

print(
    "Unsupported Banner requirements and other "
    "registration restrictions require verification."
)


# =========================================================
# 15. Generate JSON Output
# =========================================================

saved_path = export_schedule_json(
    semester_courses=semester_courses,
    existing_courses=history["in_progress_courses"],
    course_credits=ALL_COURSE_CREDITS,
    semester_names=SEMESTER_NAMES,
    max_credits=MAX_CREDITS_PER_SEMESTER,
    output_path=OUTPUT_PATH,
    academic_level=ACADEMIC_LEVEL,
    enrollment_status=ENROLLMENT_STATUS,
    min_credits=MIN_CREDITS_PER_SEMESTER
)

print(f"\nSchedule JSON exported to: {saved_path}")