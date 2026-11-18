import json
import os
import tempfile
import sys
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from router_agent import route_question
from faculty_agent.faculty_panel import last_panel, last_panels

import courses_rag.courses_agent as courses_agent
from courses_rag.course_panel import last_course_panel, last_course_panels
from courses_rag.schedule_session import last_schedule, take_update, show_sample_schedule as build_session_schedule
from courses_rag.transcript_lookup import load_student_transcript

from backend.transcript.transcript_parser import parse_transcript
from backend.scheduler.scheduler_poc import run_scheduler

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8443", "http://127.0.0.1:8443"], allow_methods=["*"], allow_headers=["*"])

PROJECT_ROOT = Path(__file__).resolve().parent
UPLOADED_HISTORY_PATH = PROJECT_ROOT / "transcript" / "uploaded_results.json"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_SEASON_ORDER = {"Winter": 0, "Spring": 1, "Summer": 2, "Fall": 3}

[sys.executable, "-m", "backend.scheduler.scheduler_poc",
 "--program-id", "computer-science:bs-bac-ba",
 "--academic-level", "undergraduate",
 "--enrollment-status", "full_time",
 "--history", str(UPLOADED_HISTORY_PATH)]

class ChatRequest(BaseModel): 
    question: str

@app.post("/chat")
def chat(request: ChatRequest):
    last_panel.set(None)
    last_panels.set(None)
    last_course_panel.set(None)
    last_course_panels.set(None)
    last_schedule.set(None)
    answer = route_question(request.question)
    professors = last_panels.get() or ([last_panel.get()] if last_panel.get() else [])
    courses = last_course_panels.get() or ([last_course_panel.get()] if last_course_panel.get() else [])
    panels = [p for p in [*courses, *professors] if p is not None]
    return {"answer": answer, "panel": last_panel.get(), "panels": panels, "schedule": last_schedule.get(),}

def _term_key(term):
    """Sort 'Fall 2025' style terms in calendar order."""
    parts = term.split()
    if len(parts) == 2 and parts[1].isdigit():
        return (int(parts[1]), _SEASON_ORDER.get(parts[0], 9))
    return (9999, 9)

def _page_semester(semester_id, label, courses):
    """One row of the Previous Coursework grid."""
    return {
        "id": semester_id,
        "label": label,
        "courses": [
            {
                "code": course["code"],
                "name": course.get("title") or course["code"],
                "credits": course.get("credits") or 0,
            }
            for course in courses
        ],
    }

@app.post("/transcript")
def upload_transcript(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="That file is too large (10 MB maximum).")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        history = parse_transcript(tmp_path)
    except (FileNotFoundError, ValueError) as exc:
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail=str(exc))

    agent_loaded = True
    try:
        courses_agent.student_history = history
    except Exception as exc:
        agent_loaded = False
        print(f"[TRANSCRIPT] the advisor could not load the history: {exc!r}")
    finally:
        os.remove(tmp_path)

    UPLOADED_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOADED_HISTORY_PATH.write_text(
        json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Group completed courses by semester for the page
    by_term = {}
    for course in history.get("completed_courses", []):
        by_term.setdefault(course.get("term") or "Other", []).append(course)

    semesters = []
    transfer = history.get("transfer_courses", [])
    if transfer:
        semesters.append(_page_semester("transfer", "Transfer", transfer))
    for term in sorted(by_term, key=_term_key):
        semesters.append(_page_semester(term, term, by_term[term]))

    print(f"[TRANSCRIPT] {len(history.get('completed_courses', []))} completed, "
          f"{len(transfer)} transfer, {len(history.get('in_progress_courses', []))} in progress")

    return {
        "semesters": semesters,
        "counts": {
            "completed": len(history.get("completed_courses", [])),
            "transfer": len(transfer),
            "in_progress": len(history.get("in_progress_courses", [])),
        },
        "warnings": history.get("warnings", []),
        "validation_errors": history.get("validation_errors", []),
        "agent_loaded": agent_loaded,
    }

class ScheduleRequest(BaseModel):
    program_id: str = "computer-science:bs-bac-ba"
    academic_level: str = "undergraduate"
    enrollment_status: str = "full_time"

@app.post("/schedule")
def generate_schedule(request: ScheduleRequest):
    history = courses_agent.student_history
    if history is None:
        raise HTTPException(status_code=400, detail="Upload a transcript first.")

    try:
        result = run_scheduler(
            raw_history=history,
            argv=[
                "--program-id", request.program_id,
                "--academic-level", request.academic_level,
                "--enrollment-status", request.enrollment_status,
            ],
            return_result=True,
        )
    except Exception as exc:
        print(f"[SCHEDULE] run_scheduler failed: {exc!r}")
        raise HTTPException(status_code=500, detail=str(exc))

    return result

class BuildWeeklyRequest(BaseModel):
    term: str
    course_ids: list[str]

@app.post("/weekly-schedule")
def build_weekly_schedule(request: BuildWeeklyRequest):
    result = build_session_schedule(request.term, request.course_ids)
    payload = take_update()

    if not result.get("schedule_changed"):
        raise HTTPException(status_code=400, detail=result.get("error", "Could not build a schedule."))

    return {"result": result, "schedule": payload}