import json
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from .requirements_lookup import get_requirements
from .retrieval import search_catalog
from typing import Literal
from .banner_lookup import get_course_offering, get_course_offerings

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

When a question requires both degree requirements and semester
availability, consult both sources.

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
    
def ask_agent(question: str) -> str:
    """Answer a question using automatic function calling."""
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[
                search_catalog,
                lookup_requirements,
                get_course_offering,
                get_course_offerings
            ],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=12, # allows gemini to automatically call tools up to 12 times before returning the final answer
            ),
            temperature=0,
        ),
    )
    return response.text or "No response generated."


if __name__ == "__main__":
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
