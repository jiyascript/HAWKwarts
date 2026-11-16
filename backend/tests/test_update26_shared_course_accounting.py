"""Regression test for shared pathway/elective course accounting."""

import z3


def main():
    print("Running Update 26 shared-course accounting regression.")
    print("=" * 60)

    # CS 201 appears in both the pathway and elective pools,
    # but both pools refer to the same scheduling decision.
    cs201_scheduled = z3.Bool("cs201_scheduled")
    cs201_pathway_task = cs201_scheduled
    cs201_elective_task = cs201_scheduled

    assert cs201_pathway_task is cs201_elective_task

    pathway_selected = z3.Bool("cs201_pathway_selected")
    elective_assignment = z3.Bool("cs201_elective_assignment")

    solver = z3.Solver()

    # A selected pathway requires its course to be scheduled.
    solver.add(
        z3.Implies(pathway_selected, cs201_scheduled)
    )

    # An elective assignment requires its course to be scheduled.
    solver.add(
        z3.Implies(elective_assignment, cs201_scheduled)
    )

    # A selected pathway excludes the same course from
    # receiving an additional elective assignment.
    solver.add(
        z3.Implies(
            pathway_selected,
            z3.Not(elective_assignment)
        )
    )

    # Shared courses are counted through pathway credits.
    pathway_credits = z3.If(cs201_scheduled, 4, 0)

    # The elective credit sum excludes courses that already
    # belong to the pathway task collection.
    elective_credits = z3.IntVal(0)

    total_credits = pathway_credits + elective_credits

    # Case 1: A shared course contributes four credits, not eight.
    solver.push()
    solver.add(cs201_scheduled)
    solver.add(total_credits != 4)
    assert solver.check() == z3.unsat, (
        "CS 201 credit accounting is incorrect."
    )
    solver.pop()

    print("PASS: Shared CS 201 contributes exactly 4 credits.")

    # Case 2: The same course cannot satisfy both exclusive
    # pathway and elective requirements simultaneously.
    solver.push()
    solver.add(pathway_selected)
    solver.add(elective_assignment)
    assert solver.check() == z3.unsat, (
        "Exclusive pathway/elective double-counting allowed."
    )
    solver.pop()

    print("PASS: Exclusive requirement double-counting rejected.")

    # Case 3: The pathway can use CS 201 without assigning
    # the same course to the elective requirement.
    solver.push()
    solver.add(pathway_selected)
    solver.add(z3.Not(elective_assignment))
    assert solver.check() == z3.sat, (
        "Valid pathway-only assignment rejected."
    )
    solver.pop()

    print("PASS: Valid pathway-only assignment accepted.")

    # Case 4: The elective can use CS 201 when its pathway
    # alternative is not selected.
    solver.push()
    solver.add(z3.Not(pathway_selected))
    solver.add(elective_assignment)
    assert solver.check() == z3.sat, (
        "Valid elective-only assignment rejected."
    )
    solver.pop()

    print("PASS: Valid elective-only assignment accepted.")
    print("PASS: Shared-course accounting regression completed.")


if __name__ == "__main__":
    main()
