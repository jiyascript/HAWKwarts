from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from router_agent import route_question
from faculty_agent.faculty_panel import last_panel, last_panels
from courses_rag.course_panel import last_course_panel, last_course_panels
from courses_rag.schedule_session import last_schedule

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8443", "http://127.0.0.1:8443"], allow_methods=["*"], allow_headers=["*"])

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