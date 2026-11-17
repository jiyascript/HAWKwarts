import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache, wraps

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import os
import random
from google.genai import errors
from google import genai
from google.genai import types
from dotenv import load_dotenv

from .internship_search import find_internships
from .research_opportunities import MATCHES_PREFIX, NO_MATCH_PREFIX, find_research_opportunities
from .faculty_panel import (
    build_panel,
    has_directory_data,
    last_panel,
    last_panels,
    panel_from_directory_text,
    parse_directory,
    parse_research,
    panel_with_directory,
    people_matching_name,
    people_named_in,
    tool_names_this_turn,
)
from .faculty_plan import (
    MAX_PEOPLE,
    has_pronoun,
    instructors_from_course,
    question_about_people,
    wants_research,
)

from pathlib import Path
DIRECTORY_PATH = str(Path(__file__).resolve().parent / "iit_directory.json")

OPENALEX_BASE = "https://api.openalex.org"
# Illinois Institute of Technology's ROR (Research Organization Registry) ID.
IIT_ROR_ID = "https://ror.org/037t3ry66"

load_dotenv()
GEMINI_MODEL = "gemini-3.5-flash-lite"
USE_GEMINI = True # change here to false to stop using Gemini and switch back to Ollama

if USE_GEMINI:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

llm = ChatOllama(
    model="qwen3:8b",
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
    """Search OpenAlex for a SPECIFIC, NAMED IIT professor's publications and
    research areas. Use this only when the question names a professor. To find
    which professors work in a topic, use find_research_opportunities instead.
    Results are filtered by confirmed IIT institutional affiliation (via ROR
    ID), not just name matching.
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


TOOLS = [
    search_iit_faculty_directory,
    search_faculty_research,
    web_search,
    find_internships,
    find_research_opportunities,
]
_tool_results = []

def _plain(tool_obj):
    return getattr(tool_obj, "func", tool_obj)

def _logged(func):
    """Print each tool call and remember its result for this turn."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"\n[TOOL] {func.__name__}({kwargs or args})")
        result = func(*args, **kwargs)
        _tool_results.append((func.__name__, result if isinstance(result, str) else ""))
        return result
    return wrapper

GEMINI_TOOLS = [_logged(_plain(t)) for t in TOOLS]

SYSTEM_PROMPT = (
    "You are an academic advisor at Illinois Institute of Technology. Answer only using tool "
    "results — never your own prior knowledge about any person. "

    "For a professor's title, department, or contact info, call search_iit_faculty_directory. "
    "For a professor's research or publications, call search_faculty_research. "

    "Respond in English only. "

    "If the user names a professor, even by last name only, use search_iit_faculty_directory or "
    "search_faculty_research, never find_research_opportunities. "
    "If the student asks a broad question like tell me about Professor X or who"
    "is Professor X, call only search_iit_faculty_directory and not search_faculty_research,"
    "so the answer doesn't includes their research and publications unless specified." 

    "To find which professors work in a research area, or for research opportunities, call "
    "find_research_opportunities with the student's topic. Present the results as faculty who "
    "work in that area, never as having open positions or taking students, and suggest the "
    "student email the professor. Spell out abbreviations in the topic (for example "
    "'human-computer interaction', not 'HCI'). If it finds no close match, relay its message "
    "exactly, add nothing to it, and do not use web_search for this. "

    "For internship opportunities, call find_internships with the student's field of interest "
    "and location if given; mention that results come from The Muse and may not cover every "
    "employer or show an application deadline. "

    "Use web_search only if none of the above tools find anything relevant, and say so when you do. "
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

    "Be thorough, but only about what the tools returned. For a professor, give their title or "
    "position, department if listed, education and research interests if listed, email, up to 5 "
    "recent publications with years, total works and citation counts when available, and the "
    "profile URL. For faculty matches in a topic, call find_research_opportunities with "
    "max_results=5 and list each person with email, title, research topics and profile URL. "
    "For internships, list each with company, location and link. Use a short bullet list per "
    "person and never add anything a tool did not return. "

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

GENERATE_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=GEMINI_TOOLS,
    automatic_function_calling=types.AutomaticFunctionCallingConfig(
        maximum_remote_calls=8,
    ),
    temperature=0,
)

_chats = {}
def _get_chat(thread_id):
    if thread_id not in _chats:
        _chats[thread_id] = client.chats.create(
            model=GEMINI_MODEL,
            config=GENERATE_CONFIG,
        )
    return _chats[thread_id]

RESEARCH_REMINDER = (
    "Note: these matches reflect public research profiles and do not mean a professor has an "
    "open position or is taking students. Please email the professor directly."
)


def _research_tool_result(messages):
    """The find_research_opportunities result from THIS turn (the part of the
    history after the latest user message), or None if the tool wasn't called."""
    for msg in reversed(messages):
        kind = getattr(msg, "type", "")
        if kind == "human":
            break  # reached the start of this turn
        if kind == "tool" and getattr(msg, "name", "") == "find_research_opportunities":
            return msg.content if isinstance(msg.content, str) else ""
    return None


def _research_no_match_reply(messages):
    """If this turn's research search found no match, return the tool's own
    sentence. The 8B chat model tends to pad that sentence with invented
    suggestions (departments, fields), so we show the tool's text as-is.
    Returns None otherwise.
    """
    content = _research_tool_result(messages)
    return content if content and content.startswith(NO_MATCH_PREFIX) else None


def _with_research_reminder(messages, answer: str) -> str:
    """Append the fixed 'matches are not open positions' reminder when this turn's
    research search returned matches. The model often drops that caveat, so it is
    added in code. Skipped if the model already said 'open position'."""
    content = _research_tool_result(messages)
    if content and content.startswith(MATCHES_PREFIX) and "open position" not in answer.lower():
        return f"{answer.rstrip()}\n\n{RESEARCH_REMINDER}"
    return answer


# The 8B model sometimes answers "I cannot find any information on ..." without
# calling any tool (seen after a long conversation). The system prompt forbids
# answering from anything but tool results, so a not-found answer with no tool
# call this turn is a mistake worth one retry with a nudge.
_NOT_FOUND_PATTERN = re.compile(
    r"\b(cannot|can't|can not|couldn't|could not|unable to)\s+find\b|\bno information\b",
    re.IGNORECASE,
)
_TOOL_NUDGE = "\n\n(Use the appropriate tool to look this up before answering.)"


def _tool_called_this_turn(messages) -> bool:
    """True if a tool was called (or returned) after the latest user message."""
    for msg in reversed(messages):
        kind = getattr(msg, "type", "")
        if kind == "human":
            return False
        if kind == "tool" or getattr(msg, "tool_calls", None):
            return True
    return False


def _ask_ollama(question: str, config: dict, retries: int = 2, seed=None):
    """Run one question through the agent (within the conversation identified
    by config's thread_id) and return a guaranteed non-empty answer. Earlier
    turns in the same thread are automatically included as context, so a
    follow-up like "I meant Scott Dawson" will be understood in light of the
    prior disambiguation question.
    """
    result = None
    message_text = question
    nudged = False
    for attempt in range(retries + 1):
        _turn_start = time.monotonic()
        outgoing = [{"role": "user", "content": message_text}]
        if seed and attempt == 0:
            outgoing += list(seed)  # lookups already run in code (see ask_people)
        result = agent.invoke({"messages": outgoing}, config=config)
        _turn_elapsed = time.monotonic() - _turn_start
        print(f"[TIMING] agent.invoke() took {_turn_elapsed:.1f}s this turn")

        no_match_reply = _research_no_match_reply(result["messages"])
        if no_match_reply:
            return no_match_reply, result["messages"]

        final_content = result["messages"][-1].content

        if (
            final_content
            and not nudged
            and not _tool_called_this_turn(result["messages"])
            and _NOT_FOUND_PATTERN.search(final_content)
        ):
            # Refused without searching: retry once, asking it to use a tool.
            nudged = True
            message_text = question + _TOOL_NUDGE
            continue

        if final_content:
            final_content = _with_research_reminder(result["messages"], final_content)
            return final_content, result["messages"]

    return (
        "I wasn't able to generate a response for that after a few attempts. "
        "This may be a temporary issue — try asking again, or double-check the spelling "
        "of the professor's name.",
        result["messages"],
    )

def _send_with_retry(chat, message_text, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return chat.send_message(message_text)
        except errors.APIError as exc:
            if getattr(exc, "code", None) not in (503, 429):
                raise
            if attempt == max_attempts - 1:
                raise
            delay = min(2 ** attempt + random.uniform(0, 1), 10)
            print(f"\nGemini temporarily unavailable ({exc.code}). Retrying in {delay:.1f}s...")
            time.sleep(delay)

_gemini_history = {}
def _record_turn(thread_id, question, answer):
    """Add this turn to the thread's history as LangChain-style messages (the
    shape faculty_panel.py reads) and return the whole history."""
    history = _gemini_history.setdefault(thread_id, [])
    history.append(HumanMessage(content=question))
    for i, (name, result) in enumerate(_tool_results):
        history.append(
            ToolMessage(content=result, name=name, tool_call_id=f"gemini-{len(history)}-{i}")
        )
    history.append(AIMessage(content=answer))
    return history

def _ask_gemini(question: str, config: dict, retries: int = 2):
    thread_id = config["configurable"]["thread_id"]
    chat = _get_chat(thread_id)
    message_text = question
    nudged = False

    for attempt in range(retries + 1):
        _tool_results.clear()
        _turn_start = time.monotonic()
        response = _send_with_retry(chat, message_text)
        print(f"[TIMING] chat.send_message() took {time.monotonic() - _turn_start:.1f}s this turn")

        # This turn's find_research_opportunities result, if the tool ran
        research = None
        for name, result in reversed(_tool_results):
            if name == "find_research_opportunities":
                research = result
                break

        if research and research.startswith(NO_MATCH_PREFIX):
            return research, _record_turn(thread_id, question, research)

        final_content = response.text or ""

        if (
            final_content
            and not nudged
            and not _tool_results  # no tool was called this turn
            and _NOT_FOUND_PATTERN.search(final_content)
        ):
            nudged = True
            message_text = question + _TOOL_NUDGE
            continue

        if final_content:
            if (
                research
                and research.startswith(MATCHES_PREFIX)
                and "open position" not in final_content.lower()
            ):
                final_content = f"{final_content.rstrip()}\n\n{RESEARCH_REMINDER}"
            return final_content, _record_turn(thread_id, question, final_content)

    fallback =  (
        "I wasn't able to generate a response for that after a few attempts. "
        "This may be a temporary issue — try asking again, or double-check the spelling "
        "of the professor's name."
    )
    return fallback, _record_turn(thread_id, question, fallback)


# ── Multi-part questions ─────────────────────────────────────────────────────
# The 8B local model rarely calls several tools in one turn (asked for a professor's
# background AND publications it usually calls only the directory). So code runs the
# lookups the question needs and, with Ollama, hands the results to the agent as if it
# had called the tools; the model only has to write the answer from them. With Gemini
# (USE_GEMINI) the model plans its own tool calls, so only the cards are built here.

def _lookup(tool_fn, name):
    try:
        return tool_fn.invoke({"professor_name": name})
    except Exception as exc:
        return f"Lookup failed for '{name}': {exc}"


def _forced_lookups(people, want_research):
    """Run the directory (and optionally publications) lookup for each person in
    parallel. Returns (seed_messages, directory_texts_by_name): an AIMessage with
    the tool calls followed by one ToolMessage per result."""
    jobs = []
    for person in people:
        jobs.append((search_iit_faculty_directory, person["name"]))
        if want_research:
            jobs.append((search_faculty_research, person["name"]))
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        texts = list(pool.map(lambda job: _lookup(*job), jobs))
    print(f"[PLAN] {len(jobs)} lookups took {time.monotonic() - started:.1f}s", flush=True)

    calls, replies, directory_texts = [], [], {}
    for index, ((tool_fn, name), text) in enumerate(zip(jobs, texts)):
        call_id = f"plan-{index}"
        calls.append({"name": tool_fn.name, "args": {"professor_name": name}, "id": call_id, "type": "tool_call"})
        replies.append(ToolMessage(content=text, tool_call_id=call_id, name=tool_fn.name))
        if tool_fn is search_iit_faculty_directory:
            directory_texts[name] = text
    return [AIMessage(content="", tool_calls=calls), *replies], directory_texts


def ask_people(people, question, config, retries: int = 2):
    """Answer a question about specific directory people (at most MAX_PEOPLE) and
    store one card per person in `last_panels`."""
    people = people[:MAX_PEOPLE]
    seed, directory_texts = _forced_lookups(people, wants_research(question) and not USE_GEMINI)
    if USE_GEMINI:
        hint = "; ".join(p["name"] for p in people)
        answer, messages = _ask_gemini(
            f"{question}\n\n(The IIT directory lists: {hint}. Use these exact names with the lookup tools.)",
            config,
            retries,
        )
    else:
        answer, messages = _ask_ollama(question, config, retries, seed=seed)
    panels = []
    try:
        for person in people:
            panel = panel_from_directory_text(directory_texts.get(person["name"]), messages)
            if panel is not None:
                panels.append(panel)
    except Exception as exc:
        print(f"[PANEL] failed: {exc!r}", flush=True)
    last_panels.set(panels or None)
    last_panel.set(panels[0] if panels else None)
    print(f"[PANEL] planned lookup -> {[p['profile']['name'] for p in panels]}", flush=True)
    return answer, messages


def _thread_messages(config):
    try:
        if USE_GEMINI:
            return _gemini_history.get(config["configurable"]["thread_id"], [])
        return agent.get_state(config).values.get("messages", [])
    except Exception:
        return []


def _last_professor(config):
    """The directory person this thread most recently looked up (for "what has he
    published?" follow-ups), or None."""
    parsers = {
        search_iit_faculty_directory.name: parse_directory,
        search_faculty_research.name: parse_research,
    }
    for msg in reversed(_thread_messages(config)):
        parse = parsers.get(getattr(msg, "name", "")) if getattr(msg, "type", "") == "tool" else None
        if parse is None:
            continue
        content = msg.content if isinstance(msg.content, str) else ""
        parsed = parse(content)
        if parsed and parsed.get("name"):
            known = people_matching_name(parsed["name"], DIRECTORY)
            return known[0] if len(known) == 1 else None
    return None


def _plan_people(question, config):
    """The directory people to look up in code, or [] to let the agent handle it.
    Anyone named in the question goes through code: the model tends to look up only one
    person, and to pass "Dr. Jacek" to the directory as typed, find nothing, and tell the
    student the professor doesn't exist. Code passes the directory's full name instead.
    With no name, a pronoun follow-up about research ("what has he published?") uses the
    last professor in the thread."""
    named = people_named_in(question, DIRECTORY)
    if 1 <= len(named) <= MAX_PEOPLE:
        return named
    if not wants_research(question):
        return []
    if not named and has_pronoun(question):
        previous = _last_professor(config)
        if previous:
            return [previous]
    return []


def ask_about_instructors(question, course_answer, course_card, config):
    """Faculty half of a "course + its professor" question. Instructors come from the
    course answer and the course card's sections (no extra model calls), matched
    against the IIT directory. Returns the faculty answer, or None if none matched."""
    people, unmatched = instructors_from_course(course_card, course_answer, DIRECTORY)
    if not people:
        return None
    shown = people[:MAX_PEOPLE]
    answer, _ = ask_people(shown, question_about_people(shown, question), config)
    notes = []
    if len(people) > len(shown):
        notes.append(f"Showing {len(shown)} of {len(people)} instructors; ask about the others by name.")
    if unmatched:
        notes.append("Not in the IIT faculty directory: " + ", ".join(unmatched) + ".")
    return answer + ("\n\n" + " ".join(notes) if notes else "")


def ask(question: str, config: dict, retries: int = 2):
    """Same as _ask, and also stores structured tool results for the website's
    side panel in `last_panel` (read by the API after route_question())."""
   
    planned = _plan_people(question, config)
    if planned:
        try:
            return ask_people(planned, question, config, retries)
        except Exception as exc:
            print(f"[PLAN] failed, using the normal agent: {exc!r}", flush=True)
    last_panels.set(None)

    if USE_GEMINI:
        answer, messages = _ask_gemini(question, config, retries)
    else:
        answer, messages = _ask_ollama(question, config, retries)

    try:
        panel = build_panel(messages, question=question, answer=answer)
        tools = tool_names_this_turn(messages)
        if panel is None:
            named = people_named_in(question, DIRECTORY)
            if len(named) == 1:
                panel = panel_from_directory_text(
                    search_iit_faculty_directory.invoke({"professor_name": named[0]["name"]}),
                    messages,
                )
        if panel is not None and not has_directory_data(panel):
            # A card with research but no directory data (the directory result isn't in
            # this thread, e.g. the lookup above was ours). Fetch it so the card is complete.
            known = people_matching_name(panel["profile"]["name"], DIRECTORY)
            if len(known) == 1:
                panel = panel_with_directory(
                    panel,
                    search_iit_faculty_directory.invoke({"professor_name": known[0]["name"]}),
                )
        last_panel.set(panel)
        who = panel["profile"]["name"] if panel else None
        print(f"[PANEL] tools this turn: {tools} -> {who}", flush=True)
    except Exception as exc:
        last_panel.set(None)  # the panel is a bonus; never break the chat over it
        print(f"[PANEL] failed: {exc!r}", flush=True)
    return answer, messages


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
