from langchain_ollama import ChatOllama
from courses_rag.courses_agent import ask_agent
from faculty_agent.faculty_agent import ask
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
    "teaches", "taught", "who",
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

ROUTER_PROMPT = """
You route questions for a university academic advising assistant.
Reply with exactly one word:

course  - courses, prerequisites, credits, degree requirements, programs, policies,
          class schedules, sections, seats, meeting times, and who is teaching a section
faculty - professors, their research, publications, interests, background
both    - the question clearly needs both of the above, such as who teaches a course
          and what that person researches
unclear - you cannot tell what the question is about

Question: {question}
Answer:
"""

def llm_route(question):
    reply = router_llm.invoke(ROUTER_PROMPT.format(question=question))
    answer = reply.content.strip().lower()
    if answer in ["course", "faculty", "both", "unclear"]:
        return answer
    return "unclear"

# router
def route_question(question):
    choice = keyword_route(question)
    if choice is None:
        choice = llm_route(question)
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