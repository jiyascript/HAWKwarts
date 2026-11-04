from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from router_agent import route_question
from faculty_agent.faculty_panel import last_panel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8443", "http://127.0.0.1:8443"], allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel): 
    question: str

@app.post("/chat")
def chat(request: ChatRequest):
    last_panel.set(None)  # clear any panel left from a previous request
    answer = route_question(request.question)
    return {"answer": answer, "panel": last_panel.get()}