from langchain_ollama import ChatOllama
from courses_rag.courses_agent import ask_agent
from faculty_agent.faculty_agent import ask

import os, time, re
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors

from guardrails import (
    SENSITIVE_CATEGORIES,
    check_resources,
    detect_all,
    guardrail_reply,
    normalize_label,
)

load_dotenv()

_missing = check_resources()
if _missing:
    print("guardrails: no contact details set for:", ", ".join(_missing))

faculty_config = {"configurable": {"thread_id": "faculty-advisor-session"}}

def run_course_agent(question):
    return ask_agent(question)

def run_faculty_agent(question):
    answer, trace = ask(question, config=faculty_config)
    return answer

# main priority: obvious keywords
COURSE_WORDS = [
    # catalog/requirements
    "prerequisite", "prereq", "credit", "requirement", "elective", "course", "degree", "catalog", "section", "corequisite",
    # programs
    "program", "major", "minor", "concentration", "curriculum", "syllabus", "graduate", "undergrad", "gpa", "transcript",
    # banner scheduling
    "crn", "schedule", "semester", "spring", "summer", "fall", "offered", "meeting time", "class time", "what time", "meets", "monday", "tuesday", "wednesday", "thursday", "friday",
    # banner seats
    "seat", "capacity", "enroll", "waitlist", "register", "registration", "restriction", "full",
    # banner location
    "room", "building", "campus", "location", "online", "hybrid", "in-person", "in person",
    # banner prof
    "teaches", "taught",
]
FACULTY_WORDS = ["publication", "publish", "paper", "research", "interest", "internship"]

def keyword_route(question):
    question = question.lower()
    course_hit = any(word in question for word in COURSE_WORDS)
    faculty_hit = any(word in question for word in FACULTY_WORDS)

    if course_hit and not faculty_hit:
        return "course"
    if faculty_hit and not course_hit:
        return "faculty"
    return None

# secondary priority: classifier for more ambiguous questions
router_llm = ChatOllama(
    model="qwen3:8b", 
    temperature=0,
    reasoning=False,
    num_ctx=8192,
    keep_alive="30m",
    num_predict=10,
)

USE_GEMINI = True # change here to false to stop using Gemini and switch back to Ollama
ROUTER_MODEL = "gemini-3.1-flash-lite" 
ROUTER_THINKING_LEVEL = "minimal"

if USE_GEMINI:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

ROUTER_PROMPT = """
You route questions for a university academic advising assistant.
Reply with exactly one word:

course  - courses, prerequisites, credits, degree requirements, programs, policies,
          class schedules, sections, seats, meeting times, and who is teaching a section
faculty - professors, their research, publications, interests, background
both    - the question clearly needs both of the above, such as who teaches a course
          and what that person researches
unclear - you cannot tell what the question is about

If the message is about the person's own personal situation, reply with one of these instead:
self_harm           - suicide, self-harm, wanting to die
threats             - threats, weapons, immediate danger, feeling unsafe, emergencies
harassment          - harassment, sexual assault or misconduct, stalking, bullying, discrimination, abuse
student_welfare     - health, mental health, stress, basic needs (food, housing), well-being
visa_legal_status   - visas, OPT/CPT, I-20, work authorization, immigration or legal status
withdrawal          - withdrawing from a class or the university, dropping out, leave of absence
academic_probation  - academic probation, academic standing, failing, GPA problems, dismissal
financial_aid       - financial aid, FAFSA, scholarships, loans, tuition bills or payment
instructor_override - asking for an instructor or department override, permission number, or exception to a prerequisite or full class

Question: {question}
Answer:
"""

def _gemini_label(question):
     for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=ROUTER_MODEL,
                contents=ROUTER_PROMPT.format(question=question),
                config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level=ROUTER_THINKING_LEVEL)),
            )
            return response.text or ""
        except errors.APIError as err:
            if getattr(err, "code", None) not in (503, 429) or attempt == 2:
                raise
            time.sleep(1 + attempt)

def llm_route(question):
    if USE_GEMINI:
        reply = _gemini_label(question)
    else: 
        reply = router_llm.invoke(ROUTER_PROMPT.format(question=question)).content

    return normalize_label(reply)

# router
def route_question(question):
    # Guardrails first: sensitive topics get a specific reply, never an agent.
    sensitive = detect_all(question)
    if sensitive:
        return guardrail_reply(sensitive)

    choice = keyword_route(question)
    if choice is None:
        choice = llm_route(question)

    # The classifier can catch sensitive phrasings the patterns missed.
    if choice in SENSITIVE_CATEGORIES:
        return guardrail_reply([choice])
    if choice == "course":
        return run_course_agent(question)
    if choice == "faculty":
        return run_faculty_agent(question)
    if choice == "both":
        course_answer = run_course_agent(question)
        faculty_answer = run_faculty_agent(question)
        return "Course info:\n" + course_answer + "\n\nFaculty info:\n" + faculty_answer
    return "Not able to understand your request. Please try clarifying your request again."

if __name__ == "__main__":
    print("HAWKwarts: Academic Assistant")
    print("Type 'exit' to quit.\n")

    while True:
        user_question = input("You: ").strip()

        if user_question.lower() in {"exit", "quit"}:
            break

        if not user_question:
            continue

        try:
            answer = route_question(user_question)
            print(f"\nHAWKwarts: {answer}\n")
        except Exception as exc:
            print(f"\nError: {exc}\n")