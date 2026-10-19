import json
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from requirements_lookup import get_requirements
from retrieval import search_catalog
from requirements_lookup import get_requirements
from typing import Literal

load_dotenv()
SYSTEM_PROMPT = """
Act like an academic catalog assistant for Illinois Institute of Technology. Answer questions about courses and programs using the avaialble tools

Use search_catalog to discover relevant records.
Use get_requirements when exact academic requirements
are needed.

Never invent course requirements, prerequisites,
credit totals, or academic policies.

Distinguish required courses from optional electives.
Cite official catalog URLs when available.

If the retrieved information is insufficient,
say what you could not verify."""

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
            ],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=6,
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
