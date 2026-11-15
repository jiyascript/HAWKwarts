import os
import time
from datetime import date

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from .live_search import current_term, search_school_web

load_dotenv()

GENERAL_MODEL = "gemini-3.1-flash-lite"
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SYSTEM_PROMPT = """
You are HAWKwarts, an assistant for Illinois Institute of Technology students.
Answer questions about campus services, procedures, policies, deadlines, fees,
and student resources using search_school_web only. Never answer from your own
knowledge.

Today's date is {today}. The current semester is {term}.
If the student does not name a semester, or says "this semester" or "now", use {term}.
For "next semester", use the next regular term (after Fall comes Spring of the
following year; after Spring comes Fall of the same year).
Always pass the semester you are asking about in the term argument, for example
"Fall 2026".

Use only what the tool returned. Give the actual dates and details when the pages
contain them; do not just send the student to a link. State which semester every
date or deadline refers to. If a page does not say which semester it covers
(mentions_term is false), or shows a different semester than the one asked about,
say so plainly and do not present it as the deadline for the asked semester.
If the excerpts do not contain the date, say you could not read it on the page and
give the URL. Even if a date has already gone by, don't say it has already passed.
List when that date happened as well.

Cite the URL of every page you rely on.

For deadlines, fees, and policies, tell the student to confirm on the page or with
the relevant office.
If nothing relevant came back, say you couldn't find it on the school's website
and suggest the office that likely handles it. Do not guess.
Keep answers short and practical; use a short numbered list for steps.
"""
_chat = None
_chat_day = None

def _get_chat():
    """One chat per day. It remembers earlier questions ("what about spring?"), and
    a new day gets a fresh prompt with the right date and semester."""
    global _chat, _chat_day
    today = date.today()
    if _chat is None or _chat_day != today:
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT.format(
                today=today.strftime("%A, %B %d, %Y"), term=current_term(today)
            ),
            tools=[search_school_web],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=4,
            ),
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        )
        _chat = client.chats.create(model=GENERAL_MODEL, config=config)
        _chat_day = today
    return _chat

def ask_general(question: str) -> str:
    chat = _get_chat()
    for attempt in range(3):
        try:
            response = chat.send_message(question)
            return response.text or "No response generated."
        except errors.APIError as exc:
            if getattr(exc, "code", None) not in (503, 429) or attempt == 2:
                raise
            time.sleep(2 ** attempt)

if __name__ == "__main__":
    while True:
        question = input("You: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if question:
            print(f"\nHAWKwarts: {answer if (answer := ask_general(question)) else ''}\n")