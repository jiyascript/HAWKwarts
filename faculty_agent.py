import json
import time
from functools import lru_cache

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver

OPENALEX_BASE = "https://api.openalex.org"
DIRECTORY_PATH = "iit_directory.json"

# Illinois Institute of Technology's ROR (Research Organization Registry) ID.
IIT_ROR_ID = "https://ror.org/037t3ry66"

llm = ChatOllama(
    model="qwen3-vl:8b",
    temperature=0,
    reasoning=False,
    num_ctx=8192,
    repeat_penalty=1.3,
    # Ollama unloads an idle model after 5 minutes by default — if you pause
    # between questions longer than that, the next question pays the cost of
    # reloading the whole 8B model before it can even start generating.
    # "30m" keeps it resident for the whole session instead.
    keep_alive="30m",
)

with open(DIRECTORY_PATH) as f:
    DIRECTORY = json.load(f)

_DIRECTORY_NAMES_LOWER = {p["name"].lower() for p in DIRECTORY}


def _names_likely_match(name_a: str, name_b: str) -> bool:
    """Compare two names by first and last token only, ignoring middle
    initials/names and case. Plain substring matching fails on cases like
    'Scott Morris' vs 'Scott B. Morris' — neither contains the other as a
    substring even though they're the same person. Comparing just the
    first and last tokens sidesteps that.
    """
    def _first_last(name: str):
        tokens = [t.strip(".") for t in name.lower().split() if t.strip(".")]
        if not tokens:
            return None, None
        return tokens[0], tokens[-1]

    a_first, a_last = _first_last(name_a)
    b_first, b_last = _first_last(name_b)
    return a_first is not None and a_first == b_first and a_last == b_last


def _find_directory_matches(name_query: str):
    """Return all directory entries matching name_query. Uses substring
    matching for partial/surname-only queries (e.g. 'Bauer' matching both
    'Matt Bauer' and 'Matthew Bauer' — intentional, surfaces real ambiguity),
    plus a first/last-token match for fuller name queries, so a name that
    includes a middle initial (e.g. 'Scott B. Morris', as the model might
    pass after seeing it from another source) still matches a directory
    entry listed without one ('Scott Morris').
    """
    q = name_query.lower()
    q_tokens = q.split()
    matches = []
    seen_urls = set()

    for p in DIRECTORY:
        name_lower = p["name"].lower()
        is_match = q in name_lower
        if not is_match and len(q_tokens) >= 2:
            is_match = _names_likely_match(name_query, p["name"])

        if is_match and p["profile_url"] not in seen_urls:
            matches.append(p)
            seen_urls.add(p["profile_url"])

    return matches


# ----- Rate-limited GET helper for OpenAlex -----
# OpenAlex's public rate limits are generous (especially in the "polite pool"
# with a contact email), but we still pace requests defensively and retry on
# 429s so a brief burst of testing doesn't cause avoidable failures.
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 0.2  # OpenAlex allows much faster pacing than Semantic Scholar's 1 req/sec


def _openalex_get(url: str, params: dict, retries: int = 2, backoff: float = 2.0):
    global _last_request_time

    params = dict(params)

    for attempt in range(retries + 1):
        elapsed = time.monotonic() - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)

        resp = requests.get(url, params=params, timeout=10)
        _last_request_time = time.monotonic()

        if resp.status_code != 429:
            return resp

        if attempt < retries:
            time.sleep(backoff * (attempt + 1))

    return resp  # exhausted retries — return the last (429) response, caller handles it


# ----- Tools -----

@lru_cache(maxsize=256)
def _fetch_profile_detail_text(profile_url: str) -> str:
    """Fetch and extract a directory profile page's text, cached per URL so
    repeated questions about the same professor in one session don't re-fetch
    over the network each time. Cache lives only for this process's lifetime.
    """
    _fetch_start = time.monotonic()
    try:
        resp = requests.get(
            profile_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        main = soup.select_one("main") or soup.body
        if main:
            return main.get_text(separator=" ", strip=True)[:600]
    except requests.exceptions.RequestException:
        pass
    finally:
        print(f"[TIMING] profile page fetch took {time.monotonic() - _fetch_start:.1f}s")
    return ""


@tool
def search_iit_faculty_directory(professor_name: str) -> str:
    """Search the official IIT faculty directory by name and return their
    title, department, and profile info. Use this for any question about
    an IIT professor's official role, title, department, or contact info.
    """
    matches = _find_directory_matches(professor_name)

    if not matches:
        return f"No IIT directory entry found for '{professor_name}'."

    if len(matches) > 1:
        names = "; ".join(m["name"] for m in matches[:5])
        return (
            f"Multiple possible matches for '{professor_name}' in the IIT directory: {names}. "
            f"Ask the user which specific person they mean before answering."
        )

    person = matches[0]
    detail_text = _fetch_profile_detail_text(person["profile_url"])

    titles = person.get("tags", [])
    summary = (
        f"Name: {person['name']}\n"
        f"Titles: {', '.join(titles) if titles else 'N/A'}\n"
        f"Email: {person.get('email', 'N/A')}\n"
        f"Profile: {person['profile_url']}"
    )
    if detail_text:
        summary += f"\n\nFull profile text: {detail_text}"
    return summary


@tool
def search_faculty_research(professor_name: str) -> str:
    """Search OpenAlex for an IIT professor's publications and research
    areas. Use this when the question involves a professor's research,
    papers, or academic interests. Results are filtered by confirmed
    IIT institutional affiliation (via ROR ID), not just name matching.
    """
    try:
        # Filter directly by confirmed IIT affiliation — this is the key
        # advantage over name-only matching. A candidate only comes back
        # here if OpenAlex has them on record as affiliated with IIT.
        #
        # NOTE: last_known_institutions.ror (not affiliations.institution.id)
        # is the correct filter here. OpenAlex's own filter reference lists
        # affiliations.institution.id as valid on /works (via
        # authorships.institutions.id), but the supported author-level
        # institution filter is last_known_institutions — and since we're
        # filtering by a ROR *URL* (not OpenAlex's internal "I..." ID format),
        # we need the .ror sub-field specifically, not .id. Using the wrong
        # field name or ID format returns a 400 "Unknown filter field" error.
        resp = _openalex_get(
            f"{OPENALEX_BASE}/authors",
            params={
                "search": professor_name,
                "filter": f"last_known_institutions.ror:{IIT_ROR_ID}",
                "per_page": 5,
            },
        )
        if resp.status_code == 429:
            return (
                "OpenAlex rate-limited this request (429) even after retrying. "
                "Try search_iit_faculty_directory instead for this professor."
            )
        resp.raise_for_status()
        results = resp.json().get("results", [])

        if not results:
            # No IIT-affiliated match on OpenAlex. Don't give up immediately —
            # check whether this person is confirmed in our own directory, so
            # we can at least point to their official info even if OpenAlex
            # doesn't have (or doesn't attribute) their research to IIT.
            directory_matches = _find_directory_matches(professor_name)
            if len(directory_matches) == 1:
                person = directory_matches[0]
                return (
                    f"No OpenAlex publications found with a confirmed IIT affiliation for "
                    f"'{professor_name}'. However, '{person['name']}' is listed in the official "
                    f"IIT faculty directory ({person['profile_url']}) — call "
                    f"search_iit_faculty_directory for their official info. OpenAlex may not have "
                    f"indexed their work, or may not have IIT listed as their affiliation."
                )
            return f"No OpenAlex author profile with a confirmed IIT affiliation found for '{professor_name}'."

        # IMPORTANT: "IIT-affiliated" per OpenAlex's last_known_institutions
        # filter is broader than "IIT faculty" — it also catches grad
        # students, postdocs, visiting researchers, research staff, and
        # alumni who've since left, none of whom are in our faculty
        # directory. Narrow the candidate list down to names that actually
        # appear there, so we don't present a non-faculty researcher as a
        # possible match for a faculty question.
        faculty_results = [
            r for r in results
            if any(
                _names_likely_match(r.get("display_name", ""), dn)
                for dn in _DIRECTORY_NAMES_LOWER
            )
        ]

        # Prefer the faculty-confirmed subset when we have it; otherwise fall
        # back to the full OpenAlex result set (still IIT-affiliated, just
        # not confirmed as current faculty specifically).
        candidate_results = faculty_results if faculty_results else results

        if len(candidate_results) > 1:
            names = "; ".join(r.get("display_name", "Unknown") for r in candidate_results[:5])
            qualifier = "IIT faculty" if faculty_results else "IIT-affiliated researchers (not confirmed as current faculty)"
            return (
                f"Multiple {qualifier} matched '{professor_name}' on OpenAlex: "
                f"{names}. Ask the user to confirm which person they mean."
            )

        results = candidate_results

        author = results[0]
        author_id = author["id"]

        works_resp = _openalex_get(
            f"{OPENALEX_BASE}/works",
            params={
                "filter": f"authorships.author.id:{author_id}",
                "sort": "publication_date:desc",
                "per_page": 5,
            },
        )
        if works_resp.status_code == 429:
            return (
                f"Name: {author.get('display_name')}\n"
                f"Works count: {author.get('works_count', 'N/A')}\n"
                f"Citations: {author.get('cited_by_count', 'N/A')}\n"
                f"(Could not fetch individual publications — OpenAlex rate-limited this request.)\n"
                f"Source: {author.get('id')}"
            )
        works_resp.raise_for_status()
        works = works_resp.json().get("results", [])

        if not works:
            return (
                f"{author.get('display_name')} has a confirmed IIT-affiliated OpenAlex profile "
                f"(works count: {author.get('works_count', 'N/A')}) but no listed publications.\n"
                f"Source: {author.get('id')}"
            )

        paper_summaries = [
            f"- {w.get('title', 'Untitled')} ({w.get('publication_year', 'n.d.')})"
            for w in works
        ]

        return (
            f"Name: {author.get('display_name')}\n"
            f"Works count: {author.get('works_count', 'N/A')}\n"
            f"Citations: {author.get('cited_by_count', 'N/A')}\n"
            f"Recent publications (confirmed IIT affiliation):\n" + "\n".join(paper_summaries) +
            f"\n\nSource: {author.get('id')}"
        )

    except requests.exceptions.RequestException as e:
        return f"An error occurred while searching OpenAlex: {str(e)}"


@tool
def web_search(query: str) -> str:
    """Search the web for current events, live facts, and recent news updates."""
    scoped_query = f"{query} Illinois Institute of Technology Chicago"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(scoped_query, max_results=3))

        if not results:
            return "No relevant search results found."

        formatted = [
            f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n---"
            for r in results
        ]
        return "\n".join(formatted)

    except Exception as e:
        return f"An error occurred while searching the web: {str(e)}"


TOOLS = [search_iit_faculty_directory, search_faculty_research, web_search]

SYSTEM_PROMPT = (
    "You are an academic advisor at Illinois Institute of Technology. Answer only using tool "
    "results — never your own prior knowledge about any person. "
    "For a professor's title, department, or contact info, call search_iit_faculty_directory. "
    "For a professor's research or publications, call search_faculty_research. "
    "Use web_search only if neither tool finds anything relevant, and say so when you do. "
    "When searching, use only the key terms from the question — never add a year or your own "
    "assumption of what 'recent' means. "
    "If a tool returns multiple matches or nothing found, ask the user one short clarifying "
    "question — do not guess, speculate, or describe people from other universities. "
    "Cite only URLs that appeared in a tool result; never invent one. "
    "When relaying a tool result, state only what the tool actually returned — do not add "
    "departments, titles, or any other detail that wasn't in the tool's output, even if you "
    "believe you know it. If a tool result is just a list of names, present only those names. "
    "If every relevant tool reports 'not found', tell the user plainly and ask them to check the "
    "spelling — never leave your response empty. "
    "Keep answers short: 2-4 sentences, or a brief bullet list for publications. "
    "If the question isn't about IIT academic advising, say so and decline."
)

# InMemorySaver keeps conversation history in memory, keyed by thread_id, so
# the agent remembers earlier turns (e.g. "did you mean Scott Morris or Scott
# Dawson?") when the user replies with a follow-up. History is lost when the
# process exits — this is short-term, in-session memory only.
checkpointer = InMemorySaver()

agent = create_agent(
    model=llm,
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)


def ask(question: str, config: dict, retries: int = 2):
    """Run one question through the agent (within the conversation identified
    by config's thread_id) and return a guaranteed non-empty answer. Earlier
    turns in the same thread are automatically included as context, so a
    follow-up like "I meant Scott Dawson" will be understood in light of the
    prior disambiguation question.
    """
    result = None
    for attempt in range(retries + 1):
        _turn_start = time.monotonic()
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config=config,
        )
        _turn_elapsed = time.monotonic() - _turn_start
        print(f"[TIMING] agent.invoke() took {_turn_elapsed:.1f}s this turn")

        final_content = result["messages"][-1].content
        if final_content:
            return final_content, result["messages"]

    return (
        "I wasn't able to generate a response for that after a few attempts. "
        "This may be a temporary issue — try asking again, or double-check the spelling "
        "of the professor's name.",
        result["messages"],
    )


if __name__ == "__main__":
    # One thread_id per run of the program — every question asked in this
    # session shares the same conversation history until the process exits.
    config = {"configurable": {"thread_id": "faculty-advisor-session"}}

    print("IIT Faculty Advisor — ask about a professor. Type 'exit' to quit.\n")

    # Tracks how many messages existed before the current turn, so we only
    # print what's new (tool calls + final answer) rather than the whole
    # growing history every time.
    prev_message_count = 0

    while True:
        question = input("You: ").strip()
        if not question or question.lower() == "exit":
            break

        answer, trace = ask(question, config=config)

        new_messages = trace[prev_message_count:]
        for msg in new_messages:
            if getattr(msg, "tool_calls", None):
                for call in msg.tool_calls:
                    print(f"[tool call] {call['name']}({call['args']})")

        print(f"\nAdvisor: {answer}\n")

        prev_message_count = len(trace)
