import json
import os
import time

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
DIRECTORY_PATH = "iit_directory.json"

# Optional: set this environment variable once Semantic Scholar API key
# is approved. The code works with or without it (just rate-limited harder
# without one).
SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")

llm = ChatOllama(
    model="qwen3-vl:8b",
    temperature=0,      # small nonzero value — helps avoid deterministic repetition/runaway loops
    reasoning=False,
    num_ctx=8192,
    #num_predict=300,      # hard cap — forces short answers instead of open-ended elaboration
    repeat_penalty=1.3,
)

with open(DIRECTORY_PATH) as f:
    DIRECTORY = json.load(f)

# Precompute a lowercase name set once, so other tools can cheaply confirm
# "is this person actually an IIT faculty member?" without re-reading the file.
_DIRECTORY_NAMES_LOWER = {p["name"].lower() for p in DIRECTORY}


def _find_directory_matches(name_query: str):
    """Return all directory entries whose name contains name_query (case-insensitive)."""
    q = name_query.lower()
    return [p for p in DIRECTORY if q in p["name"].lower()]


# ----- Rate-limited, retrying HTTP helper for Semantic Scholar -----
# Semantic Scholar's introductory tier is capped at 1 request/second across
# ALL endpoints. This tracks the last request time globally (module-level)
# and sleeps as needed before every call, then retries with backoff on 429s
# as a safety net in case we still get rate-limited (e.g. from other traffic
# sharing the same unauthenticated pool, if no API key is set).
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 1.05  # slightly over 1 req/sec to leave margin


def _semantic_scholar_get(url: str, params: dict, retries: int = 2, backoff: float = 2.0):
    global _last_request_time

    headers = {"x-api-key": SEMANTIC_SCHOLAR_API_KEY} if SEMANTIC_SCHOLAR_API_KEY else {}

    for attempt in range(retries + 1):
        elapsed = time.monotonic() - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)

        resp = requests.get(url, params=params, headers=headers, timeout=10)
        _last_request_time = time.monotonic()

        if resp.status_code != 429:
            return resp

        if attempt < retries:
            time.sleep(backoff * (attempt + 1))

    return resp  # exhausted retries — return the last (429) response, caller handles it


# ----- Tools -----

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

    # Fetch the individual profile page for fuller detail (bio, office, etc.)
    detail_text = ""
    try:
        resp = requests.get(
            person["profile_url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        main = soup.select_one("main") or soup.body
        if main:
            detail_text = main.get_text(separator=" ", strip=True)[:1500]
    except requests.exceptions.RequestException:
        pass  # directory-listing data below is still useful even if the profile page fetch fails

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
    """Search Semantic Scholar for an IIT professor's publications and
    research areas. Use this when the question involves a professor's
    research, papers, or academic interests.
    """
    try:
        # NOTE: query is the name ONLY. Semantic Scholar's author-search does
        # fuzzy name matching on the whole query string — appending institution
        # words here causes it to search for a *name* containing those words
        # and silently returns zero candidates. Institution confirmation
        # happens afterward, against the returned candidates' affiliation
        # field and our own directory JSON (see the "author = next(...)"
        # fallback chain below), not by polluting the search query.
        resp = _semantic_scholar_get(
            f"{SEMANTIC_SCHOLAR_BASE}/author/search",
            params={
                "query": professor_name,
                "fields": "name,affiliations,paperCount,hIndex",
            },
        )
        if resp.status_code == 429:
            return (
                "Semantic Scholar rate-limited this request (429) even after retrying. "
                "Try search_iit_faculty_directory instead for this professor."
            )
        resp.raise_for_status()
        candidates = resp.json().get("data", [])

        if not candidates:
            return f"No Semantic Scholar author profile found for '{professor_name}'."

        # Preference order for picking the right candidate:
        # 1. Semantic Scholar's own affiliation field explicitly mentions IIT.
        # 2. The candidate's name also appears in our own IIT directory —
        #    this is a strong, independent confirmation even when Semantic
        #    Scholar's affiliation metadata is missing (which is common).
        # 3. There's only one candidate at all returned for this name, so
        #    even with no affiliation data either way, it's reasonable to
        #    treat it as the person being asked about.
        author = next(
            (
                c for c in candidates
                if any(
                    "Illinois Institute of Technology" in (aff or "") or "IIT" in (aff or "")
                    for aff in c.get("affiliations", [])
                )
            ),
            None,
        )

        if author is None:
            author = next(
                (c for c in candidates if c["name"].lower() in _DIRECTORY_NAMES_LOWER),
                None,
            )

        if author is None and len(candidates) == 1:
            author = candidates[0]

        if author is None:
            # Don't rely on the model to decide to call the directory tool
            # next — do the cross-check here directly. If exactly one
            # candidate's name matches our own IIT directory, that's a
            # confident resolution even without Semantic Scholar affiliation
            # data.
            directory_matches = _find_directory_matches(professor_name)
            if len(directory_matches) == 1:
                person = directory_matches[0]
                return (
                    f"Semantic Scholar's affiliation data was inconclusive, but '{person['name']}' "
                    f"was confirmed in the official IIT faculty directory ({person['profile_url']}). "
                    f"Semantic Scholar candidates considered: "
                    + "; ".join(c["name"] for c in candidates[:5])
                    + ". Call search_iit_faculty_directory for this person's official info; "
                    "research/publication details from Semantic Scholar could not be confidently "
                    "matched to them."
                )

            names = "; ".join(
                f"{c['name']} ({', '.join(c.get('affiliations') or ['no listed affiliation'])})"
                for c in candidates[:5]
            )
            return (
                f"Found possible matches for '{professor_name}' but could not confirm IIT "
                f"affiliation: {names}. Ask the user to confirm which person they mean."
            )

        author_id = author["authorId"]
        profile_link = f"https://www.semanticscholar.org/author/{author['name'].replace(' ', '-')}/{author_id}"

        papers_resp = _semantic_scholar_get(
            f"{SEMANTIC_SCHOLAR_BASE}/author/{author_id}/papers",
            params={"fields": "title,abstract,year,venue", "limit": 5},
        )
        if papers_resp.status_code == 429:
            return (
                f"Name: {author['name']}\n"
                f"h-index: {author.get('hIndex', 'N/A')}\n"
                f"Total papers: {author.get('paperCount', 'N/A')}\n"
                f"(Could not fetch individual publications — Semantic Scholar rate-limited this "
                f"request.)\nSource: {profile_link}"
            )
        papers_resp.raise_for_status()
        papers = papers_resp.json().get("data", [])

        if not papers:
            return (
                f"{author['name']} has a Semantic Scholar profile "
                f"(h-index: {author.get('hIndex', 'N/A')}) but no listed papers.\n"
                f"Source: {profile_link}"
            )

        papers = sorted(papers, key=lambda p: p.get("year") or 0, reverse=True)
        paper_summaries = []
        for p in papers:
            venue = p.get("venue")
            line = f"- {p.get('title', 'Untitled')} ({p.get('year', 'n.d.')})"
            if venue:
                line += f", {venue}"
            paper_summaries.append(line)

        return (
            f"Name: {author['name']}\n"
            f"h-index: {author.get('hIndex', 'N/A')}\n"
            f"Total papers: {author.get('paperCount', 'N/A')}\n"
            f"Recent publications:\n" + "\n".join(paper_summaries) +
            f"\n\nSource: {profile_link}"
        )

    except requests.exceptions.RequestException as e:
        return f"An error occurred while searching Semantic Scholar: {str(e)}"


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
    "If every relevant tool reports 'not found', tell the user plainly and ask them to check the "
    "spelling — never leave your response empty. "
    "Keep answers short: 2-4 sentences, or a brief bullet list for publications. "
    "If the question isn't about IIT academic advising, say so and decline."
)

agent = create_agent(
    model=llm,
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
)


def ask(question: str, retries: int = 2):
    """Run one question through the agent and return a guaranteed non-empty answer.
    Retries the whole agent call if the model produces a blank final response
    (observed occasionally as local-model flakiness, unrelated to tool logic).
    """
    result = None
    for attempt in range(retries + 1):
        result = agent.invoke({"messages": [{"role": "user", "content": question}]})
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
    question = "What research has Prof. Saniie done?"
    answer, trace = ask(question)

    # Debug trace — comment this block out once things are working reliably
    for msg in trace:
        print("---")
        print(type(msg).__name__)
        print("content:", repr(getattr(msg, "content", None)))
        if getattr(msg, "tool_calls", None):
            print("tool_calls:", msg.tool_calls)

    print("\nAnswer:", answer)
