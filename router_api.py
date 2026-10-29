from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from router_agent import route_question

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel): 
    question: str

@app.post("/chat")
def chat(request: ChatRequest):
    answer = route_question(request.question)
    return {"answer": answer}