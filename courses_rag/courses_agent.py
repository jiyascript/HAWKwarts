import json
import os
import random
import time
from google.genai import errors
from google import genai
from google.genai import types
from dotenv import load_dotenv
from .requirements_lookup import get_requirements
from .retrieval import search_catalog
from typing import Literal
from .banner_lookup import get_course_offering, get_course_offerings
from .transcript_lookup import load_student_transcript, summarize_transcript
from .specialization_lookup import list_specializations
from .degree_progress import get_degree_progress_context


load_dotenv()
SYSTEM_PROMPT = """
You are HAWKwarts, an academic catalog assistant for
Illinois Institute of Technology.

You must use the available tools before answering any
question about courses, programs, minors, or specializations.

Use search_catalog to discover relevant records.
Use lookup_requirements to retrieve complete program,
minor, or specialization requirements.

For comparisons involving multiple programs:
1. Retrieve the complete requirements for each program.
2. Compare only information supported by those records.
3. Distinguish mandatory courses from elective options.
4. Identify courses that appear in both programs.
5. Do not assume overlapping courses can double-count.

When search_catalog returns a program record, use its program_id
with lookup_requirements(kind="program", record_id=program_id).
Do not search repeatedly for a program ID once you have found it.
Use get_course_offering for semester-specific Banner information,
including course offerings, sections, instructors, meeting times,
prerequisites, restrictions, and seat availability.

Use search_catalog and lookup_requirements for academic catalog
information, degree requirements, minors, and specializations.
When asked which specializations are available for a degree
program, use list_specializations with the exact parent_program_id. Do not infer that no specializations exist from semantic
search results alone.
Use lookup_requirements when the student asks about the
requirements of a specific specialization.
When a question requires both degree requirements and semester
availability, consult both sources.
REQUIREMENTS RETRIEVAL RULES:

When answering questions about degree progress, graduation
requirements, or missing courses:
1. Identify the student's degree program.
2. If the exact program_id is known, call lookup_requirements
   directly. Do not call search_catalog first.
3. If the program_id is unknown, use search_catalog once
   to discover it, then call lookup_requirements.
4. Never use semantic search results as a substitute for
   complete program requirements.
5. Interpret requirement item types correctly:
   - course: mandatory course
   - one_of: satisfy one listed option
   - choose: satisfy the specified number of options
   - free_text: credit-based requirement; check eligibility
   - external_requirement: requires additional policy data
6. If a requirement cannot be verified from the available
   records, label it unresolved rather than missing.


Preserve prerequisite AND/OR logic, minimum grades, and
concurrency restrictions. Do not infer eligibility without
the student's completed-course information. Banner data is a snapshot. Do not guarantee that a course
or seat will remain available.

When a student asks about multiple courese in a semester, use get_course_offerings to retrieve all relevant Banner offerings together. 
When asked about required courses for a degree, first rettrieve the exact program requirements using lookup_requirements. DO NOT assume every course mentiioned in a requirement section is individually mandtory. 

For questions combining degree requirements and semester
offerings, use both catalog and Banner tools.

Do not claim that courses have no scheduling conflicts
without checking their section meeting days and times.

If meeting times are TBA, mark conflicts as unknown.
If meeting times are TBA, do not assume there is no conflict.
Never invent academic requirements or policies.
If a lookup fails, do not substitute general knowledge.
Cite official catalog URLs when available.

Use get_student_academic_history for questions about
completed, attempted, transferred, or in-progress courses.

DO NOT assume that in-progress courses are completed.

Preserve course grades, terms, and repeat history when
evaluating academic requirements. Use lookup_requirements for official degree requirements
and Banner tools for course prerequisites and offerings. Transcript records are a historical snapshot and do not
constitute an official degree audit. If transcript data is incomplete, explain what information
is missing rather than assuming a requirement is unmet.
"""

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
def lookup_requirements(kind: Literal["program","minor","specialization"], record_id: str) -> str:
    """Retrieve a complete requirement record by its exact ID."""
    print(f"\n[TOOL] lookup_requirements(kind={kind}, record_id={record_id})")

    record = get_requirements(kind, record_id)
    if record is None:
        return json.dumps({
            "error": "Record not found",
            "kind": kind,
            "record_id": record_id
        })
    return json.dumps(record, indent=2, ensure_ascii=False)
def search_acadmic_catalog(query: str) -> str:
    """Search the catalog for relevant courses, minors, programs, or specializations."""
    print(f"\n[TOOL] search_academic_catalog(query={query})")

    results = search_catalog(query, top_k=8)

    print(f"[TOOL] Retrieved {len(results)} matches")

    return json.dumps(results, ensure_ascii=False)
def resolve_degree_progress_program(question: str) -> str | None:
    """Identify supported degree-progress requests."""
    q = question.lower()

    progress_terms = (
        "completed",
        "missing",
        "remaining",
        "degree progress",
        "requirements remain",
        "requirements unsatisfied",
    )

    cs_program_terms = (
        "computer science",
        "cs degree",
        "cs major",
    )

    if (
        any(term in q for term in progress_terms)
        and any(term in q for term in cs_program_terms)
    ):
        return "computer-science:bs-bac-ba"

    return None

def ask_agent(question: str) -> str:
    """Answer questions using structured context when appropriate."""
    use_structured_context = False
    program_id = resolve_degree_progress_program(question)

    if program_id and student_history is not None:
        context = get_degree_progress_context(
            program_id,
            student_history,
        )

        if "error" in context:
            return context["error"]
        use_structured_context = True
        question = (
            "Answer the student's degree-progress question using "
            "the complete structured records below.\n"
            "Do not search for program requirements again.\n"
            "Distinguish mandatory courses, one-of choices, electives, "
            "and external requirements.\n"
            "Treat transfer equivalencies and substitutions as "
            "unverified unless explicitly supported.\n"
            "A course absent from this historical transcript is not "
            "necessarily missing today.\n\n"
            f"STRUCTURED CONTEXT:\n{json.dumps(context, ensure_ascii=False)}\n\n"
            f"STUDENT QUESTION:\n{question}"
        )
    """Answer a question using automatic function calling."""
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=question,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=[] if use_structured_context else [
                        search_catalog,
                        lookup_requirements,
                        list_specializations,
                        get_course_offering,
                        get_course_offerings,
                        get_student_academic_history,
                    ],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=12,
                    ),
                    temperature=0,
                ),
            )
            return response.text or "No response generated."

        except errors.ServerError as exc:
            if getattr(exc, "code", None) not in (503, 429):
                raise

            if attempt == max_attempts - 1:
                raise

            delay = min(2 ** attempt + random.uniform(0, 1), 10)
            print(
                f"\nGemini temporarily unavailable "
                f"({exc.code}). Retrying in {delay:.1f}s..."
            )
            time.sleep(delay)
student_history = None


def get_student_academic_history() -> dict:
    """Retrieve the current student's transcript course history.

    Includes completed, transfer, in-progress, and attempted courses.
    Use this tool to answer questions about a student's academic history.
    """
    print("\n[TOOL] get_student_academic_history()")

    if student_history is None:
        return {"error": "No student transcript loaded for this session."}

    return summarize_transcript(student_history)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        student_history = load_student_transcript(sys.argv[1])
        print("Student transcript loaded.")
    else:
        print("No transcript provided. Student-specific advising unavailable.")

    print("HAWKwarts: Academic Assistant")
    print("Type 'exit' to quit.\n")

    while True:
        question = input("You: ").strip()

        if question.lower() in {"exit", "quit"}:
            break

        if not question:
            continue

        try:
            answer = ask_agent(question)
            print(f"\nHAWKwarts: {answer}\n")
        except Exception as exc:
            print(f"\nError: {exc}\n")
