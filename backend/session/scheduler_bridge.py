"""Connect an active advising session to the scheduling engine."""

from backend.scheduler.scheduler_poc import run_scheduler


def schedule_session(
    session_manager,
    session_id,
    *,
    academic_level,
    enrollment_status,
    program_id,
):
    """Generate an in-memory schedule from stored session history."""

    if not isinstance(academic_level, str) or academic_level not in {
        "undergraduate",
        "graduate",
        "coterminal",
    }:
        raise ValueError("Invalid academic level.")

    if not isinstance(enrollment_status, str) or enrollment_status not in {
        "full_time",
        "part_time",
    }:
        raise ValueError("Invalid enrollment status.")

    if not isinstance(program_id, str) or not program_id.strip():
        raise ValueError("A nonempty program ID is required.")

    history = session_manager.get_academic_history(session_id)

    if history is None:
        raise ValueError(
            "The advising session has no stored academic history."
        )

    return run_scheduler(
        raw_history=history,
        argv=[
            "--academic-level",
            academic_level,
            "--enrollment-status",
            enrollment_status,
            "--program-id",
            program_id,
        ],
        return_result=True,
    )
