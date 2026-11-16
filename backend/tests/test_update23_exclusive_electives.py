
from backend.scheduler.requirement_resolver import (
    allocate_exclusive_choice_courses,
)



def test_completed_and_in_progress_allocation():
    requirements = [
        {
            "requirement_id": "0:0",
            "required_count": 1,
            "options": ["CS 331", "CS 351"],
        },
        {
            "requirement_id": "1:0",
            "required_count": 1,
            "options": ["CS 331", "CS 401"],
        },
    ]

    completed = {"CS 331"}
    in_progress = {"CS 351"}

    # Allocate all eligible courses together to avoid
    # blocking valid assignments across requirements.
    allocations = allocate_exclusive_choice_courses(
        requirements,
        completed | in_progress,
    )

    allocated_codes = [
        code
        for codes in allocations.values()
        for code in codes
    ]

    # Both requirements should be covered.
    assert sum(map(len, allocations.values())) == 2

    # Each course must be allocated at most once.
    assert len(allocated_codes) == len(set(allocated_codes))

    # Verify the valid assignment.
    assert allocations["0:0"] == ["CS 351"]
    assert allocations["1:0"] == ["CS 331"]

    # Preserve completed versus in-progress status.
    completed_allocated = {
        code for code in allocated_codes
        if code in completed
    }

    pending_allocated = {
        code for code in allocated_codes
        if code in in_progress
    }

    assert completed_allocated == {"CS 331"}
    assert pending_allocated == {"CS 351"}


def test_z3_elective_exclusivity():
    import z3

    # Two requirements share CS 331.
    groups = [
        ["CS 331", "CS 351"],
        ["CS 331", "CS 401"],
    ]

    scheduled = {
        code: z3.Bool(f"scheduled_{code.replace(' ', '_')}")
        for group in groups
        for code in group
    }

    assignments = {}

    solver = z3.Solver()

    for group_index, options in enumerate(groups):
        group_assignments = []

        for code in options:
            assignment = z3.Bool(
                f"assignment_{group_index}_{code.replace(' ', '_')}"
            )

            assignments[(group_index, code)] = assignment
            group_assignments.append((assignment, 1))

            solver.add(
                z3.Implies(assignment, scheduled[code])
            )

        solver.add(z3.PbEq(group_assignments, 1))

    # Apply the same exclusivity rule as scheduler_poc.py.
    for code in scheduled:
        course_assignments = [
            assignment
            for (group_index, course_code), assignment
            in assignments.items()
            if course_code == code
        ]

        if len(course_assignments) > 1:
            solver.add(
                z3.PbLe(
                    [(assignment, 1) for assignment in course_assignments],
                    1
                )
            )

    # Both groups cannot receive credit for CS 331.
    solver.push()
    solver.add(assignments[(0, "CS 331")])
    solver.add(assignments[(1, "CS 331")])
    assert solver.check() == z3.unsat
    solver.pop()

    # Different courses can satisfy the two groups.
    solver.add(assignments[(0, "CS 351")])
    solver.add(assignments[(1, "CS 331")])
    assert solver.check() == z3.sat


def test_elective_pathway_task_reuse():
    import processscheduler as ps

    # Create an isolated scheduling problem.
    ps.SchedulingProblem(
        name="Update23_Shared_Task_Test",
        horizon=2
    )

    # Simulate an existing optional pathway task.
    pathway_courses = {
        "CS 201": ps.FixedDurationTask(
            name="CS_201",
            duration=1,
            optional=True
        )
    }

    remaining_courses = {}
    elective_courses = {}

    choice_groups = [
        {
            "remaining_count": 1,
            "available_options": ["CS 201", "CS 331"]
        }
    ]

    # Reproduce the elective task creation logic.
    for group in choice_groups:
        if group["remaining_count"] <= 0:
            continue

        for code in group["available_options"]:
            if code in remaining_courses:
                continue

            if code in elective_courses:
                continue

            if code in pathway_courses:
                elective_courses[code] = pathway_courses[code]
                continue

            elective_courses[code] = ps.FixedDurationTask(
                name=code.replace(" ", "_"),
                duration=1,
                optional=True
            )

    # Shared course must reference the same scheduling task.
    assert elective_courses["CS 201"] is pathway_courses["CS 201"]

    # No second CS 201 task should be created.
    assert len({
        id(elective_courses["CS 201"]),
        id(pathway_courses["CS 201"])
    }) == 1

    # Non-overlapping elective still receives its own task.
    assert "CS 331" in elective_courses
    assert elective_courses["CS 331"] is not pathway_courses["CS 201"]

def test_shared_course_credit_counting():
    import z3

    # Simulate a course shared by two requirement categories.
    scheduled = z3.Bool("CS_201_scheduled")
    semester = z3.Int("CS_201_semester")

    elective_courses = {"CS 201": scheduled}
    pathway_courses = {"CS 201": scheduled}

    ELECTIVE_CREDITS = {"CS 201": 4}
    PATHWAY_CREDITS = {"CS 201": 4}

    # Same filtering rule used in scheduler_poc.py.
    elective_credits = z3.Sum([
        z3.If(
            z3.And(task, semester == 0),
            ELECTIVE_CREDITS[code],
            0
        )
        for code, task in elective_courses.items()
        if code not in pathway_courses
    ])

    pathway_credits = z3.Sum([
        z3.If(
            z3.And(task, semester == 0),
            PATHWAY_CREDITS[code],
            0
        )
        for code, task in pathway_courses.items()
    ])

    total_credits = elective_credits + pathway_credits

    solver = z3.Solver()
    solver.add(scheduled)
    solver.add(semester == 0)

    # A shared 4-credit course must contribute exactly 4.
    solver.push()
    solver.add(total_credits != 4)
    assert solver.check() == z3.unsat
    solver.pop()

    # A 4-credit course fits within a 4-credit limit.
    solver.add(total_credits <= 4)
    assert solver.check() == z3.sat

def test_pathway_elective_exclusivity():
    import z3

    # Programming pathway alternatives:
    # Option A: CS 115 + CS 116
    # Option B: CS 201
    cs115 = z3.Bool("test23_cs115")
    cs116 = z3.Bool("test23_cs116")
    cs201 = z3.Bool("test23_cs201")
    cs331 = z3.Bool("test23_cs331")

    # Elective requirement assignments.
    assign_cs201 = z3.Bool("test23_assign_cs201")
    assign_cs331 = z3.Bool("test23_assign_cs331")

    # Explicit pathway-selection variables.
    select_a = z3.Bool("test23_select_pathway_a")
    select_b = z3.Bool("test23_select_pathway_b")

    option_a = z3.And(cs115, cs116)
    option_b = cs201

    solver = z3.Solver()

    # Exactly one pathway alternative is selected.
    solver.add(z3.PbEq([
        (select_a, 1),
        (select_b, 1)
    ], 1))

    # Selected alternatives require their courses to be scheduled.
    solver.add(z3.Implies(select_a, option_a))
    solver.add(z3.Implies(select_b, option_b))

    # Reproduce the new pathway/elective exclusivity rule.
    solver.add(z3.Implies(select_b, z3.Not(assign_cs201)))

    # Scenario 1: CS 201 cannot count toward both requirements.
    solver.push()
    solver.add(select_b, assign_cs201)
    assert solver.check() == z3.unsat
    solver.pop()

    # Scenario 2: CS 201 can be scheduled as an elective
    # while the CS 115 + CS 116 pathway is selected.
    solver.push()
    solver.add(select_a, assign_cs201)
    assert solver.check() == z3.sat
    solver.pop()

    # Scenario 3: CS 201 can satisfy the programming pathway
    # while CS 331 satisfies the elective requirement.
    solver.push()
    solver.add(select_b, assign_cs331)
    assert solver.check() == z3.sat
    solver.pop()

if __name__ == "__main__":
    test_completed_and_in_progress_allocation()
    print("PASS: Joint completed and in-progress allocation.")

    test_z3_elective_exclusivity()
    print("PASS: Z3 prevents elective double-counting.")

    test_elective_pathway_task_reuse()
    print("PASS: Elective and pathway courses reuse one task.")

    test_shared_course_credit_counting()
    print("PASS: Shared course credits counted exactly once.")

    test_pathway_elective_exclusivity()
    print("PASS: Pathway/elective exclusivity constraints.")