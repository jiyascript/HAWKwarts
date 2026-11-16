
import z3

from backend.scheduler.prerequisite_constraints import (
    build_prerequisite_constraint,
)


class MockTask:
    def __init__(self, name, optional=False):
        self._start = z3.Int(f"{name}_start")
        self._scheduled = z3.Bool(f"{name}_scheduled")
        self.optional = optional


def is_satisfiable(constraint, assignments):
    solver = z3.Solver()
    solver.add(constraint)

    for variable, value in assignments:
        solver.add(variable == value)

    return solver.check() == z3.sat


def main():
    print("Running Update 25 prerequisite ordering regression.")
    print("=" * 55)

    prerequisite = MockTask("CS_115")
    target = MockTask("CS_116")

    history = {
        "completed_courses": [],
        "transfer_courses": [],
        "in_progress_courses": [],
    }

    expression = {
        "type": "course",
        "code": "CS 115",
    }

    constraint = build_prerequisite_constraint(
        expression=expression,
        history=history,
        target_start=target._start,
        scheduled_tasks={
            "CS 115": prerequisite,
            "CS 116": target,
        },
        detail_lookup={
            "CS 115": {
                "code": "CS 115",
                "minimum_grade": None,
                "concurrent_allowed": False,
            }
        },
    )

    # Valid: prerequisite in Fall, target in Spring.
    assert is_satisfiable(
        constraint,
        [
            (prerequisite._start, 0),
            (target._start, 1),
        ],
    ), "Valid prerequisite ordering was rejected."

    print("PASS: Fall prerequisite -> Spring target accepted.")

    # Invalid: both courses in Fall.
    assert not is_satisfiable(
        constraint,
        [
            (prerequisite._start, 0),
            (target._start, 0),
        ],
    ), "Same-semester enrollment incorrectly accepted."

    print("PASS: Same-semester enrollment rejected.")

    # Invalid: target before prerequisite.
    assert not is_satisfiable(
        constraint,
        [
            (prerequisite._start, 1),
            (target._start, 0),
        ],
    ), "Reversed prerequisite ordering incorrectly accepted."

    print("PASS: Reversed prerequisite ordering rejected.")

    # ---------------------------------------------------------
    # Update 25.4: Concurrent prerequisite enrollment
    # ---------------------------------------------------------

    concurrent_constraint = build_prerequisite_constraint(
        expression=expression,
        history=history,
        target_start=target._start,
        scheduled_tasks={
            "CS 115": prerequisite,
            "CS 116": target,
        },
        detail_lookup={
            "CS 115": {
                "code": "CS 115",
                "minimum_grade": None,
                "concurrent_allowed": True,
            }
        },
    )

    # Valid: prerequisite completed in an earlier semester.
    assert is_satisfiable(
        concurrent_constraint,
        [
            (prerequisite._start, 0),
            (target._start, 1),
        ],
    ), "Earlier prerequisite incorrectly rejected."

    print("PASS: Earlier prerequisite accepted with concurrency enabled.")

    # Valid: both courses taken during the same semester.
    assert is_satisfiable(
        concurrent_constraint,
        [
            (prerequisite._start, 0),
            (target._start, 0),
        ],
    ), "Allowed concurrent enrollment was rejected."

    print("PASS: Same-semester enrollment accepted when permitted.")

    # Invalid: target course taken before its prerequisite.
    assert not is_satisfiable(
        concurrent_constraint,
        [
            (prerequisite._start, 1),
            (target._start, 0),
        ],
    ), "Reversed ordering accepted with concurrency enabled."

    print("PASS: Reversed ordering rejected even with concurrency enabled.")


    # ---------------------------------------------------------
    # Update 25.5: Completed prerequisite validation
    # ---------------------------------------------------------

    def completed_prerequisite_constraint(grade, minimum_grade):
        completed_history = {
            "completed_courses": [
                {
                    "code": "CS 115",
                    "grade": grade,
                }
            ],
            "transfer_courses": [],
            "in_progress_courses": [],
        }

        return build_prerequisite_constraint(
            expression={
                "type": "course",
                "code": "CS 115",
            },
            history=completed_history,
            target_start=target._start,
            scheduled_tasks={
                "CS 116": target,
            },
            detail_lookup={
                "CS 115": {
                    "code": "CS 115",
                    "minimum_grade": minimum_grade,
                    "concurrent_allowed": False,
                }
            },
        )

    # Test 1: Completed prerequisite meets minimum grade.
    assert is_satisfiable(
        completed_prerequisite_constraint("B", "C"),
        [(target._start, 0)],
    ), "Completed prerequisite with sufficient grade was rejected."

    print("PASS: Completed prerequisite with B satisfies minimum C.")

    # Test 2: Completed prerequisite does not meet minimum grade.
    assert not is_satisfiable(
        completed_prerequisite_constraint("D", "C"),
        [(target._start, 0)],
    ), "Insufficient prerequisite grade was accepted."

    print("PASS: Completed prerequisite with D fails minimum C.")

    # Test 3: Passing prerequisite without explicit minimum.
    assert is_satisfiable(
        completed_prerequisite_constraint("D", None),
        [(target._start, 0)],
    ), "Passing prerequisite without minimum grade was rejected."

    print("PASS: Passing prerequisite accepted without minimum grade.")

    # Test 4: Failed prerequisite must not satisfy requirement.
    assert not is_satisfiable(
        completed_prerequisite_constraint("F", None),
        [(target._start, 0)],
    ), "Failed prerequisite was incorrectly accepted."

    print("PASS: Failed prerequisite does not satisfy requirement.")

    # ---------------------------------------------------------
    # Update 25.6: In-progress prerequisite validation
    # ---------------------------------------------------------

    in_progress_history = {
        "completed_courses": [],
        "transfer_courses": [],
        "in_progress_courses": [
            {
                "code": "CS 115",
                "term": "Fall 2026",
            }
        ],
    }

    def in_progress_constraint(
        concurrent_allowed=False,
        term_mapping=None,
    ):
        return build_prerequisite_constraint(
            expression=expression,
            history=in_progress_history,
            target_start=target._start,
            scheduled_tasks={
                "CS 116": target,
            },
            detail_lookup={
                "CS 115": {
                    "code": "CS 115",
                    "minimum_grade": None,
                    "concurrent_allowed": concurrent_allowed,
                }
            },
            in_progress_terms=term_mapping,
        )

    # Test 1: Fall in-progress prerequisite -> Spring target.
    assert is_satisfiable(
        in_progress_constraint(
            term_mapping={"CS 115": 0},
        ),
        [(target._start, 1)],
    ), "Valid in-progress prerequisite ordering rejected."

    print("PASS: Fall in-progress prerequisite allows Spring target.")

    # Test 2: Same-semester enrollment without concurrency.
    assert not is_satisfiable(
        in_progress_constraint(
            term_mapping={"CS 115": 0},
        ),
        [(target._start, 0)],
    ), "Invalid same-semester enrollment accepted."

    print("PASS: In-progress prerequisite blocks same-semester target.")

    # Test 3: Same-semester enrollment with concurrency.
    assert is_satisfiable(
        in_progress_constraint(
            concurrent_allowed=True,
            term_mapping={"CS 115": 0},
        ),
        [(target._start, 0)],
    ), "Permitted concurrent enrollment was rejected."

    print("PASS: In-progress prerequisite permits explicit concurrency.")

    # Test 4: Missing semester mapping.
    assert not is_satisfiable(
        in_progress_constraint(
            term_mapping={},
        ),
        [(target._start, 1)],
    ), "Unverified in-progress semester was accepted."

    print("PASS: Missing in-progress semester mapping rejected.")

    # ---------------------------------------------------------
    # Update 25.7: Optional prerequisite selection
    # ---------------------------------------------------------

    optional_prerequisite = MockTask(
        "CS_115_optional",
        optional=True,
    )

    optional_constraint = build_prerequisite_constraint(
        expression=expression,
        history=history,
        target_start=target._start,
        scheduled_tasks={
            "CS 115": optional_prerequisite,
            "CS 116": target,
        },
        detail_lookup={
            "CS 115": {
                "code": "CS 115",
                "minimum_grade": None,
                "concurrent_allowed": False,
            }
        },
    )

    # Test 1: Selected optional prerequisite in an earlier term.
    assert is_satisfiable(
        optional_constraint,
        [
            (optional_prerequisite._scheduled, True),
            (optional_prerequisite._start, 0),
            (target._start, 1),
        ],
    ), "Valid selected optional prerequisite was rejected."

    print("PASS: Selected optional prerequisite satisfies ordering.")

    # Test 2: Unselected optional prerequisite.
    assert not is_satisfiable(
        optional_constraint,
        [
            (optional_prerequisite._scheduled, False),
            (optional_prerequisite._start, 0),
            (target._start, 1),
        ],
    ), "Unselected optional prerequisite was accepted."

    print("PASS: Unselected optional prerequisite rejected.")

    # Test 3: Selected optional prerequisite scheduled too late.
    assert not is_satisfiable(
        optional_constraint,
        [
            (optional_prerequisite._scheduled, True),
            (optional_prerequisite._start, 1),
            (target._start, 0),
        ],
    ), "Reversed optional prerequisite ordering accepted."

    print("PASS: Reversed optional prerequisite ordering rejected.")

    # Test 4: Selected optional prerequisite in the same term.
    assert not is_satisfiable(
        optional_constraint,
        [
            (optional_prerequisite._scheduled, True),
            (optional_prerequisite._start, 0),
            (target._start, 0),
        ],
    ), "Invalid optional prerequisite concurrency accepted."

    print("PASS: Same-semester optional prerequisite rejected.")

    print("\nPASS: All prerequisite ordering checks completed.")


if __name__ == "__main__":
    main()
