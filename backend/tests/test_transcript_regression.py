"""Permanent regression tests for HAWKwarts transcript processing."""

import pytest

from backend.transcript.transcript_validator import normalize_course


def make_course(**overrides):
    """Create a valid institutional course for regression testing."""
    course = {
        "code": "CS 100",
        "title": "Introduction to Computer Science",
        "grade": "A",
        "credits": 3.0,
        "term": "Fall 2025",
        "level": "UG",
        "status": "institution",
    }
    course.update(overrides)
    return course


def test_normalize_institutional_course():
    course = make_course(
        code=" cs 100 ",
        title="  Introduction to Computer Science  ",
    )

    result = normalize_course(course)

    assert result["code"] == "CS 100"
    assert result["title"] == "Introduction to Computer Science"
    assert result["credits"] == 3.0
    assert result["status"] == "institution"


def test_normalize_unverified_transfer():
    course = make_course(
        code="CS 200",
        title="Transfer Computer Science",
        grade="TR",
        status="transfer",
        equivalency_verified=False,
    )

    result = normalize_course(course)

    assert result["code"] == "CS 200"
    assert result["status"] == "transfer"
    assert result["equivalency_verified"] is False


def test_reject_invalid_course_code():
    course = make_course(code="INVALID")

    with pytest.raises(ValueError):
        normalize_course(course)


def test_reject_invalid_credits():
    course = make_course(credits=-3)

    with pytest.raises(ValueError):
        normalize_course(course)


def test_reject_nonboolean_transfer_verification():
    course = make_course(
        grade="TR",
        status="transfer",
        equivalency_verified="yes",
    )

    with pytest.raises(ValueError):
        normalize_course(course)


def test_passing_institutional_course_is_scheduler_eligible():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    history = build_academic_history([
        make_course(code="CS 100", grade="A"),
    ])

    assert len(history["all_institution_records"]) == 1
    assert len(history["completed_courses"]) == 1
    assert "CS 100" in history["scheduler_course_codes"]
    assert history["validation_errors"] == []


def test_unverified_transfer_is_not_scheduler_eligible():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    history = build_academic_history([
        make_course(
            code="CS 200",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    assert len(history["transfer_courses"]) == 1
    assert history["transfer_courses"][0][
        "equivalency_verified"
    ] is False
    assert "CS 200" not in history["scheduler_course_codes"]
    assert history["validation_errors"] == []


def test_in_progress_course_is_not_completed():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    history = build_academic_history([
        make_course(
            code="CS 300",
            grade="IP",
            status="in_progress",
        ),
    ])

    assert len(history["in_progress_courses"]) == 1
    assert len(history["completed_courses"]) == 0
    assert "CS 300" not in history["scheduler_course_codes"]
    assert history["validation_errors"] == []


def test_academic_history_reconstruction_preserves_records():
    from backend.transcript.transcript_validator import (
        build_academic_history,
        validate_academic_history,
    )

    original = build_academic_history([
        make_course(code="CS 100", grade="A"),
        make_course(
            code="CS 200",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
        make_course(
            code="CS 300",
            grade="IP",
            status="in_progress",
        ),
    ])

    reconstructed = validate_academic_history(original)

    assert reconstructed["validation_errors"] == []
    assert len(reconstructed["all_institution_records"]) == 1
    assert len(reconstructed["transfer_courses"]) == 1
    assert len(reconstructed["in_progress_courses"]) == 1
    assert len(reconstructed["completed_courses"]) == 1


def test_reconstructed_history_excludes_unverified_transfers():
    from backend.transcript.transcript_validator import (
        build_academic_history,
        validate_academic_history,
    )

    original = build_academic_history([
        make_course(code="CS 100", grade="A"),
        make_course(
            code="CS 200",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    reconstructed = validate_academic_history(original)

    assert "CS 100" in reconstructed["scheduler_course_codes"]
    assert "CS 200" not in reconstructed["scheduler_course_codes"]


def test_academic_history_reconstruction_does_not_mutate_input():
    from copy import deepcopy

    from backend.transcript.transcript_validator import (
        build_academic_history,
        validate_academic_history,
    )

    original = build_academic_history([
        make_course(code="CS 100", grade="A"),
    ])

    snapshot = deepcopy(original)

    reconstructed = validate_academic_history(original)

    assert original == snapshot

    reconstructed["all_institution_records"][0]["title"] = (
        "Modified Title"
    )

    assert original == snapshot


def test_academic_history_reconstruction_preserves_records():
    from backend.transcript.transcript_validator import (
        build_academic_history,
        validate_academic_history,
    )

    original = build_academic_history([
        make_course(code="CS 100", grade="A"),
        make_course(
            code="CS 200",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
        make_course(
            code="CS 300",
            grade="IP",
            status="in_progress",
        ),
    ])

    reconstructed = validate_academic_history(original)

    assert reconstructed["validation_errors"] == []
    assert len(reconstructed["all_institution_records"]) == 1
    assert len(reconstructed["transfer_courses"]) == 1
    assert len(reconstructed["in_progress_courses"]) == 1
    assert len(reconstructed["completed_courses"]) == 1


def test_reconstructed_history_excludes_unverified_transfers():
    from backend.transcript.transcript_validator import (
        build_academic_history,
        validate_academic_history,
    )

    original = build_academic_history([
        make_course(code="CS 100", grade="A"),
        make_course(
            code="CS 200",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    reconstructed = validate_academic_history(original)

    assert "CS 100" in reconstructed["scheduler_course_codes"]
    assert "CS 200" not in reconstructed["scheduler_course_codes"]


def test_academic_history_reconstruction_does_not_mutate_input():
    from copy import deepcopy

    from backend.transcript.transcript_validator import (
        build_academic_history,
        validate_academic_history,
    )

    original = build_academic_history([
        make_course(code="CS 100", grade="A"),
    ])

    snapshot = deepcopy(original)

    reconstructed = validate_academic_history(original)

    assert original == snapshot

    reconstructed["all_institution_records"][0]["title"] = (
        "Modified Title"
    )

    assert original == snapshot


def test_course_correction_updates_selected_record():
    from backend.transcript.transcript_editor import (
        apply_course_correction,
    )
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    history = build_academic_history([
        make_course(code="CS 100"),
        make_course(code="CS 200"),
    ])

    corrected = apply_course_correction(
        history,
        "all_institution_records",
        0,
        {"title": "Corrected Course Title"},
    )

    assert (
        corrected["all_institution_records"][0]["title"]
        == "Corrected Course Title"
    )
    assert (
        corrected["all_institution_records"][1]["title"]
        == "Introduction to Computer Science"
    )
    assert corrected["validation_errors"] == []


def test_course_correction_does_not_mutate_original_history():
    from copy import deepcopy

    from backend.transcript.transcript_editor import (
        apply_course_correction,
    )
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    original = build_academic_history([
        make_course(code="CS 100"),
    ])

    snapshot = deepcopy(original)

    corrected = apply_course_correction(
        original,
        "all_institution_records",
        0,
        {"title": "Updated Title"},
    )

    assert original == snapshot
    assert (
        corrected["all_institution_records"][0]["title"]
        == "Updated Title"
    )
    assert (
        original["all_institution_records"][0]["title"]
        != "Updated Title"
    )


def test_course_correction_rejects_invalid_credits():
    from backend.transcript.transcript_editor import (
        apply_course_correction,
    )
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    history = build_academic_history([
        make_course(code="CS 100"),
    ])

    with pytest.raises(ValueError):
        apply_course_correction(
            history,
            "all_institution_records",
            0,
            {"credits": -3},
        )

    assert history["all_institution_records"][0]["credits"] == 3.0


def test_repeated_course_attempts_are_preserved():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    history = build_academic_history([
        make_course(
            code="CS 100",
            grade="F",
            term="Fall 2024",
        ),
        make_course(
            code="CS 100",
            grade="A",
            term="Spring 2025",
        ),
    ])

    records = history["all_institution_records"]

    assert len(records) == 2
    assert records[0]["grade"] == "F"
    assert records[1]["grade"] == "A"
    assert records[0]["term"] == "Fall 2024"
    assert records[1]["term"] == "Spring 2025"
    assert history["validation_errors"] == []


def test_passing_repeated_attempt_is_scheduler_eligible():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    history = build_academic_history([
        make_course(
            code="CS 100",
            grade="F",
            term="Fall 2024",
        ),
        make_course(
            code="CS 100",
            grade="A",
            term="Spring 2025",
        ),
    ])

    assert "CS 100" in history["scheduler_course_codes"]
    assert history["scheduler_course_codes"].count("CS 100") == 1


def test_correcting_repeated_attempt_preserves_other_attempt():
    from backend.transcript.transcript_editor import (
        apply_course_correction,
    )
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    history = build_academic_history([
        make_course(
            code="CS 100",
            grade="F",
            term="Fall 2024",
        ),
        make_course(
            code="CS 100",
            grade="A",
            term="Spring 2025",
        ),
    ])

    corrected = apply_course_correction(
        history,
        "all_institution_records",
        0,
        {"title": "Corrected First Attempt"},
    )

    records = corrected["all_institution_records"]

    assert records[0]["title"] == "Corrected First Attempt"
    assert records[0]["grade"] == "F"
    assert records[1]["title"] == "Introduction to Computer Science"
    assert records[1]["grade"] == "A"
    assert "CS 100" in corrected["scheduler_course_codes"]


def test_unverified_transfer_remains_scheduler_ineligible():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    history = build_academic_history([
        make_course(
            code="CS 991",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    assert len(history["transfer_courses"]) == 1
    assert history["transfer_courses"][0][
        "equivalency_verified"
    ] is False
    assert "CS 991" not in history["scheduler_course_codes"]


def test_confirmed_transfer_verification_enables_eligibility():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )
    from backend.transcript.transfer_verification import (
        apply_transfer_verification,
    )

    history = build_academic_history([
        make_course(
            code="CS 991",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    verified = apply_transfer_verification(
        history,
        0,
        True,
        institutional_confirmation=True,
    )

    assert verified["transfer_courses"][0][
        "equivalency_verified"
    ] is True
    assert "CS 991" in verified["scheduler_course_codes"]
    assert history["transfer_courses"][0][
        "equivalency_verified"
    ] is False


def test_revoked_transfer_verification_removes_eligibility():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )
    from backend.transcript.transfer_verification import (
        apply_transfer_verification,
    )

    history = build_academic_history([
        make_course(
            code="CS 991",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    verified = apply_transfer_verification(
        history,
        0,
        True,
        institutional_confirmation=True,
    )

    revoked = apply_transfer_verification(
        verified,
        0,
        False,
        institutional_confirmation=True,
    )

    assert revoked["transfer_courses"][0][
        "equivalency_verified"
    ] is False
    assert "CS 991" not in revoked["scheduler_course_codes"]
    assert verified["transfer_courses"][0][
        "equivalency_verified"
    ] is True


def test_unverified_transfer_remains_scheduler_ineligible():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    history = build_academic_history([
        make_course(
            code="CS 991",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    assert len(history["transfer_courses"]) == 1
    assert history["transfer_courses"][0][
        "equivalency_verified"
    ] is False
    assert "CS 991" not in history["scheduler_course_codes"]


def test_confirmed_transfer_verification_enables_eligibility():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )
    from backend.transcript.transfer_verification import (
        apply_transfer_verification,
    )

    history = build_academic_history([
        make_course(
            code="CS 991",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    verified = apply_transfer_verification(
        history,
        0,
        True,
        institutional_confirmation=True,
    )

    assert verified["transfer_courses"][0][
        "equivalency_verified"
    ] is True
    assert "CS 991" in verified["scheduler_course_codes"]
    assert history["transfer_courses"][0][
        "equivalency_verified"
    ] is False


def test_revoked_transfer_verification_removes_eligibility():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )
    from backend.transcript.transfer_verification import (
        apply_transfer_verification,
    )

    history = build_academic_history([
        make_course(
            code="CS 991",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    verified = apply_transfer_verification(
        history,
        0,
        True,
        institutional_confirmation=True,
    )

    revoked = apply_transfer_verification(
        verified,
        0,
        False,
        institutional_confirmation=True,
    )

    assert revoked["transfer_courses"][0][
        "equivalency_verified"
    ] is False
    assert "CS 991" not in revoked["scheduler_course_codes"]
    assert verified["transfer_courses"][0][
        "equivalency_verified"
    ] is True


def test_transfer_verification_requires_confirmation():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )
    from backend.transcript.transfer_verification import (
        apply_transfer_verification,
    )

    history = build_academic_history([
        make_course(
            code="CS 991",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    with pytest.raises(PermissionError):
        apply_transfer_verification(
            history,
            0,
            True,
        )

    assert history["transfer_courses"][0][
        "equivalency_verified"
    ] is False
    assert "CS 991" not in history["scheduler_course_codes"]


def test_transfer_verification_rejects_nonboolean_status():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )
    from backend.transcript.transfer_verification import (
        apply_transfer_verification,
    )

    history = build_academic_history([
        make_course(
            code="CS 991",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    with pytest.raises(ValueError):
        apply_transfer_verification(
            history,
            0,
            "yes",
            institutional_confirmation=True,
        )

    assert history["transfer_courses"][0][
        "equivalency_verified"
    ] is False


def test_transfer_verification_rejects_invalid_index():
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )
    from backend.transcript.transfer_verification import (
        apply_transfer_verification,
    )

    history = build_academic_history([
        make_course(
            code="CS 991",
            grade="TR",
            status="transfer",
            equivalency_verified=False,
        ),
    ])

    with pytest.raises(IndexError):
        apply_transfer_verification(
            history,
            99,
            True,
            institutional_confirmation=True,
        )

    assert len(history["transfer_courses"]) == 1
    assert history["transfer_courses"][0][
        "equivalency_verified"
    ] is False
    assert "CS 991" not in history["scheduler_course_codes"]


def test_session_stores_and_retrieves_academic_history():
    from backend.session.session_manager import SessionManager
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    manager = SessionManager()
    session_id = manager.create_session()

    history = build_academic_history([
        make_course(code="CS 100", grade="A"),
    ])

    manager.store_academic_history(session_id, history)
    stored = manager.get_academic_history(session_id)

    assert stored["validation_errors"] == []
    assert len(stored["all_institution_records"]) == 1
    assert "CS 100" in stored["scheduler_course_codes"]

    manager.delete_session(session_id)

    assert session_id not in manager._sessions


def test_student_sessions_remain_isolated():
    from backend.session.session_manager import SessionManager
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    manager = SessionManager()

    student_a = manager.create_session()
    student_b = manager.create_session()

    manager.store_academic_history(
        student_a,
        build_academic_history([
            make_course(code="CS 100", grade="A"),
        ]),
    )

    manager.store_academic_history(
        student_b,
        build_academic_history([
            make_course(code="CS 200", grade="A"),
        ]),
    )

    history_a = manager.get_academic_history(student_a)
    history_b = manager.get_academic_history(student_b)

    assert "CS 100" in history_a["scheduler_course_codes"]
    assert "CS 200" not in history_a["scheduler_course_codes"]

    assert "CS 200" in history_b["scheduler_course_codes"]
    assert "CS 100" not in history_b["scheduler_course_codes"]

    manager.delete_session(student_a)
    manager.delete_session(student_b)

    assert len(manager._sessions) == 0


def test_retrieved_session_history_is_independent_copy():
    from backend.session.session_manager import SessionManager
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    manager = SessionManager()
    session_id = manager.create_session()

    manager.store_academic_history(
        session_id,
        build_academic_history([
            make_course(code="CS 100", grade="A"),
        ]),
    )

    retrieved = manager.get_academic_history(session_id)

    retrieved["all_institution_records"][0]["title"] = (
        "Unauthorized Local Modification"
    )
    retrieved["scheduler_course_codes"].clear()

    stored = manager.get_academic_history(session_id)

    assert (
        stored["all_institution_records"][0]["title"]
        == "Introduction to Computer Science"
    )
    assert "CS 100" in stored["scheduler_course_codes"]

    manager.delete_session(session_id)


def test_session_stores_and_retrieves_academic_history():
    from backend.session.session_manager import SessionManager
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    manager = SessionManager()
    session_id = manager.create_session()

    history = build_academic_history([
        make_course(code="CS 100", grade="A"),
    ])

    manager.store_academic_history(session_id, history)
    stored = manager.get_academic_history(session_id)

    assert stored["validation_errors"] == []
    assert len(stored["all_institution_records"]) == 1
    assert "CS 100" in stored["scheduler_course_codes"]

    manager.delete_session(session_id)

    assert session_id not in manager._sessions


def test_student_sessions_remain_isolated():
    from backend.session.session_manager import SessionManager
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    manager = SessionManager()

    student_a = manager.create_session()
    student_b = manager.create_session()

    manager.store_academic_history(
        student_a,
        build_academic_history([
            make_course(code="CS 100", grade="A"),
        ]),
    )

    manager.store_academic_history(
        student_b,
        build_academic_history([
            make_course(code="CS 200", grade="A"),
        ]),
    )

    history_a = manager.get_academic_history(student_a)
    history_b = manager.get_academic_history(student_b)

    assert "CS 100" in history_a["scheduler_course_codes"]
    assert "CS 200" not in history_a["scheduler_course_codes"]

    assert "CS 200" in history_b["scheduler_course_codes"]
    assert "CS 100" not in history_b["scheduler_course_codes"]

    manager.delete_session(student_a)
    manager.delete_session(student_b)

    assert len(manager._sessions) == 0


def test_retrieved_session_history_is_independent_copy():
    from backend.session.session_manager import SessionManager
    from backend.transcript.transcript_validator import (
        build_academic_history,
    )

    manager = SessionManager()
    session_id = manager.create_session()

    manager.store_academic_history(
        session_id,
        build_academic_history([
            make_course(code="CS 100", grade="A"),
        ]),
    )

    retrieved = manager.get_academic_history(session_id)

    retrieved["all_institution_records"][0]["title"] = (
        "Unauthorized Local Modification"
    )
    retrieved["scheduler_course_codes"].clear()

    stored = manager.get_academic_history(session_id)

    assert (
        stored["all_institution_records"][0]["title"]
        == "Introduction to Computer Science"
    )
    assert "CS 100" in stored["scheduler_course_codes"]

    manager.delete_session(session_id)


def test_session_expires_after_inactivity():
    from datetime import datetime, timedelta, timezone

    from backend.session.session_manager import SessionManager

    manager = SessionManager()
    session_id = manager.create_session()

    manager._sessions[session_id]["last_activity"] = (
        datetime.now(timezone.utc) - timedelta(minutes=31)
    )

    with pytest.raises(KeyError):
        manager.get_academic_history(session_id)

    assert session_id not in manager._sessions


def test_deleted_session_cannot_be_accessed():
    from backend.session.session_manager import SessionManager

    manager = SessionManager()
    session_id = manager.create_session()

    manager.delete_session(session_id)

    assert session_id not in manager._sessions

    with pytest.raises(KeyError):
        manager.get_academic_history(session_id)


def test_cleanup_removes_only_expired_sessions():
    from datetime import datetime, timedelta, timezone

    from backend.session.session_manager import SessionManager

    manager = SessionManager()

    expired_session = manager.create_session()
    active_session = manager.create_session()

    now = datetime.now(timezone.utc)

    manager._sessions[expired_session]["last_activity"] = (
        now - timedelta(minutes=31)
    )
    manager._sessions[active_session]["last_activity"] = now

    removed_count = manager.cleanup_expired_sessions(now=now)

    assert removed_count == 1
    assert expired_session not in manager._sessions
    assert active_session in manager._sessions

    manager.delete_session(active_session)

    assert len(manager._sessions) == 0


def test_sample_pdf_transcript_parses_successfully():
    from pathlib import Path

    from backend.transcript.transcript_parser import (
        parse_transcript,
    )

    pdf_path = (
        Path(__file__).resolve().parents[1]
        / "Sample Unofficial Transcript.pdf"
    )

    history = parse_transcript(pdf_path)

    assert history["validation_errors"] == []
    assert len(history["all_institution_records"]) > 0
    assert len(history["transfer_courses"]) > 0
    assert len(history["in_progress_courses"]) > 0
    assert len(history["scheduler_course_codes"]) > 0


def test_missing_transcript_pdf_is_rejected(tmp_path):
    from backend.transcript.transcript_parser import (
        parse_transcript,
    )

    missing_pdf = tmp_path / "missing_transcript.pdf"

    with pytest.raises(FileNotFoundError):
        parse_transcript(missing_pdf)


def test_unrecognized_transcript_pdf_is_rejected(tmp_path):
    import pymupdf

    from backend.transcript.transcript_parser import (
        parse_transcript,
    )

    pdf_path = tmp_path / "unrecognized_transcript.pdf"

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "This document is not an Illinois Tech transcript.",
    )
    document.save(pdf_path)
    document.close()

    with pytest.raises(
        ValueError,
        match="Not a recognized Illinois Tech unofficial transcript",
    ):
        parse_transcript(pdf_path)
