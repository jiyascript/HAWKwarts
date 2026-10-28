"""Find IIT faculty whose research matches a student's interest.

This is a TWO-STEP module, unlike internship_search.py:

STEP 1 (run occasionally, not every session -- this hits OpenAlex and the IIT
directory for every faculty member, so it's slow):

    python research_opportunities.py --build

For each Faculty-tagged person in iit_directory.json this fetches their
directory page and their OpenAlex research topics, caches the raw results in
research_cache.json (so an interrupted or partly failed build can resume, and
so profile-cleaning changes don't require re-fetching anything), then embeds a
cleaned profile with a local Ollama model (nomic-embed-text) and writes
research_index.json.

STEP 2 (every session): import find_research_opportunities as a tool.
At query time it only embeds the student's one question and compares it
against the pre-built index -- no network calls to OpenAlex or the directory.

Requirements:
    ollama pull nomic-embed-text
    research_index.json must exist in the working directory (run --build once,
    then keep/re-upload that file across sessions).

Strongly recommended: get a FREE OpenAlex API key (make an account at
openalex.org, copy the key from openalex.org/settings/api) and set it:
    export OPENALEX_API_KEY=your_key_here
Since February 2026 OpenAlex meters usage against a daily budget (resets at
midnight UTC). Keyless use gets a very small budget; a free key gets about 10x
that. The old "mailto" trick no longer does anything.

Commands:
    python research_opportunities.py --build                 # build; resumes from cache
    python research_opportunities.py --build --refresh-topics  # also retry OpenAlex
                                                              # lookups that found nothing
    python research_opportunities.py --build --fresh         # ignore cache, refetch all
    python research_opportunities.py "machine learning for healthcare"
    python research_opportunities.py --scores "machine learning for healthcare"
                                                             # top 10 with raw scores,
                                                             # for tuning the threshold
    python research_opportunities.py --stats
"""

import argparse
import collections
import datetime
import json
import os
import re
import time

import numpy as np
import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings

DIRECTORY_PATH = "iit_directory.json"
INDEX_PATH = "research_index.json"
CACHE_PATH = "research_cache.json"

OPENALEX_BASE = "https://api.openalex.org"
# Same ROR ID used in faculty_agent.py, confirmed independently earlier in
# this project (INSPIRE-HEP, HAL archive records, RRID).
IIT_ROR_ID = "https://ror.org/037t3ry66"
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY")  # free key; raises the daily budget
OPENALEX_MIN_INTERVAL = 0.4  # seconds between OpenAlex requests

# Used both to build the index and to embed a student's query at runtime.
# Requires: ollama pull nomic-embed-text
# keep_alive (seconds) keeps the embedding model loaded between questions, so
# only the first search of a session pays the model-load delay.
embeddings_model = OllamaEmbeddings(model="nomic-embed-text", keep_alive=1800)

# nomic-embed-text is trained with task prefixes; using them noticeably helps
# retrieval. The index records whether it was built with them (see meta) so an
# older index without prefixes still gets queried the old way.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

# Calibrated on a handful of queries against the rebuilt index: real queries
# scored 0.60-0.73 at the top, while a nonsense query ("medieval basket
# weaving") topped out at 0.54. Re-check with --scores if you change the
# embedding model or the profile text.
SIMILARITY_THRESHOLD = 0.58

# Queries with no real match (e.g. "football") still produce a flat band of
# ~0.58-0.60 scores that look like matches, but some legitimate niche queries
# also land in that band (e.g. "sustainable architecture" best = 0.628). So:
#   - if the best score reaches MIN_BEST_SCORE, results are returned as usual;
#   - if it falls between SIMILARITY_THRESHOLD and MIN_BEST_SCORE, results are
#     returned only if at least one of the top few profiles shares a content
#     word with the query (see _shares_query_word) -- a nonsense query like
#     "football" never does. The semantic ranking itself is left unchanged.
MIN_BEST_SCORE = 0.63
LOW_CONFIDENCE_SCAN = 10  # in the low-confidence band, look this deep for word matches

# Start of the user-facing sentence returned when nothing matches. faculty_agent.py
# looks for this prefix so it can show that sentence as-is instead of letting the
# chat model embellish it.
NO_MATCH_PREFIX = "I couldn't find IIT faculty whose research closely matches"
# Start of the header line returned when there ARE matches (also used by faculty_agent.py).
MATCHES_PREFIX = "Faculty whose research may relate to"

# Profiles built only from projects/patents/professional activities (typically
# industry adjuncts) or publication titles are weaker evidence of a research
# area than a Research Interests section, a bio, or OpenAlex topics. Entries
# with such a profile AND no OpenAlex topics have this subtracted from their
# score so they don't outrank people with real research descriptions.
WEAK_PROFILE_PENALTY = 0.04
WEAK_PROFILE_SOURCES = {"fallback", "publications"}
TOPICS_PER_PERSON = 6        # how many of a person's top OpenAlex topics to use
MAX_PROFILE_CHARS = 1200     # cap on cleaned directory text fed to the embedder
CACHE_SAVE_EVERY = 25        # checkpoint the cache after this many fetched people

# Topic-lookup statuses that mean "the request failed", so a plain --build
# retries them. Statuses like "no_results" are final unless --refresh-topics.
RETRYABLE_TOPIC_STATUSES = {None, "rate_limited", "error"}


class ResearchIndexError(Exception):
    """Something went wrong building or using the research index."""


class OpenAlexBudgetExhausted(ResearchIndexError):
    """OpenAlex says the daily usage budget is spent (retrying won't help)."""


def _names_likely_match(name_a: str, name_b: str) -> bool:
    """Same token-based match used in faculty_agent.py -- compares only the
    first and last token of each name, so 'Scott Morris' matches
    'Scott B. Morris'.
    """
    def _first_last(name: str):
        tokens = [t.strip(".") for t in name.lower().split() if t.strip(".")]
        return (tokens[0], tokens[-1]) if tokens else (None, None)

    a_first, a_last = _first_last(name_a)
    b_first, b_last = _first_last(name_b)
    return a_first is not None and a_first == b_first and a_last == b_last


def _cosine_similarity(a, b) -> float:
    a_arr, b_arr = np.array(a), np.array(b)
    denom = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    return float(np.dot(a_arr, b_arr) / denom) if denom else 0.0


def _clean_url(url: str) -> str:
    """Fix doubled-up URLs like 'https://www.iit.eduhttps://kentlaw.iit.edu/...'
    (a relative-link join gone wrong) by keeping only the last absolute URL.
    """
    if not url:
        return url
    idx = max(url.rfind("https://"), url.rfind("http://"))
    return url[idx:] if idx > 0 else url


def _atomic_json_dump(obj, path: str):
    """Write JSON via a temp file so a crash mid-write can't corrupt `path`."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


# ----- Build-time only: fetching data to build the index -----

_last_openalex_request = 0.0


def _retry_delay(resp, default: float) -> float:
    try:
        return min(float(resp.headers.get("Retry-After", default)), 20.0)
    except (TypeError, ValueError):
        return default


def _looks_like_daily_limit(resp) -> bool:
    """429 caused by the daily budget (not a brief burst): waiting a few
    seconds won't fix it, so don't burn minutes retrying."""
    try:
        if float(resp.headers.get("X-RateLimit-Remaining", "1")) <= 0:
            return True
    except (TypeError, ValueError):
        pass
    try:
        return float(resp.headers.get("Retry-After", "0")) > 60
    except (TypeError, ValueError):
        return False


def _openalex_get(params: dict, retries: int = 3, backoff: float = 3.0) -> dict:
    """GET /authors with spacing, retry on 429/5xx, and Retry-After support.
    Raises ResearchIndexError if still rate-limited after all retries, and
    requests exceptions (HTTPError, Timeout, ...) for other failures.
    """
    global _last_openalex_request
    headers = {"Authorization": f"Bearer {OPENALEX_API_KEY}"} if OPENALEX_API_KEY else {}

    for attempt in range(retries + 1):
        wait = OPENALEX_MIN_INTERVAL - (time.monotonic() - _last_openalex_request)
        if wait > 0:
            time.sleep(wait)
        resp = requests.get(f"{OPENALEX_BASE}/authors", params=params, headers=headers, timeout=(5, 15))
        _last_openalex_request = time.monotonic()

        if resp.status_code == 429 and _looks_like_daily_limit(resp):
            raise OpenAlexBudgetExhausted("OpenAlex daily usage budget is spent.")
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < retries:
                delay = _retry_delay(resp, backoff * (attempt + 1))
                print(f"      OpenAlex returned {resp.status_code}; waiting {delay:.0f}s "
                      f"(retry {attempt + 1}/{retries})...")
                time.sleep(delay)
                continue
            if resp.status_code == 429:
                raise ResearchIndexError("OpenAlex rate-limited during index build.")
        resp.raise_for_status()
        return resp.json()
    raise ResearchIndexError("OpenAlex request failed after retries.")


_openalex_stopped = False         # set once OpenAlex looks out of budget this run
_consecutive_rate_limited = 0


def _stop_openalex(reason: str):
    global _openalex_stopped
    if not _openalex_stopped:
        _openalex_stopped = True
        print(f"\n  !! {reason}\n  !! Skipping OpenAlex for the rest of this run (directory pages "
              "will still be fetched). Get a free key (openalex.org/settings/api), set "
              "OPENALEX_API_KEY, and/or rerun --build after midnight UTC -- it retries only these.\n")


def _openalex_lookup(name: str):
    """Look up a confirmed IIT-affiliated author's top research topics.
    Returns (topics, status) where status says WHY the list is empty:
      ok | no_results | no_name_match | no_topics | rate_limited | error
    """
    global _consecutive_rate_limited
    if _openalex_stopped:
        return [], "rate_limited"
    try:
        data = _openalex_get({
            "search": name,
            "filter": f"last_known_institutions.ror:{IIT_ROR_ID}",
            "per_page": 5,
        })
    except OpenAlexBudgetExhausted:
        _stop_openalex("OpenAlex says the daily usage budget is spent.")
        return [], "rate_limited"
    except ResearchIndexError:
        _consecutive_rate_limited += 1
        if _consecutive_rate_limited >= 3:
            _stop_openalex("OpenAlex keeps returning 429 (probably out of daily budget).")
        return [], "rate_limited"
    except (requests.exceptions.RequestException, ValueError):
        return [], "error"
    _consecutive_rate_limited = 0

    results = data.get("results", [])
    if not results:
        return [], "no_results"

    matches = [r for r in results if _names_likely_match(r.get("display_name", ""), name)]
    if not matches:
        return [], "no_name_match"

    # If several authors share a first/last name, prefer the most prolific.
    author = max(matches, key=lambda r: r.get("works_count") or 0)
    topics = [
        t.get("display_name")
        for t in (author.get("topics") or [])[:TOPICS_PER_PERSON]
        if t.get("display_name")
    ]
    return (topics, "ok") if topics else ([], "no_topics")


def _get_openalex_topics(name: str) -> list:
    """Best-effort topics list (see _openalex_lookup for the reason behind an
    empty result). Kept for quick manual checks in a notebook."""
    return _openalex_lookup(name)[0]


def _fetch_directory_page(profile_url: str, max_chars: int = 6000):
    """Fetch a directory page and return (text, ok). Text keeps one line per
    page element so section headings ('Research Interests', 'Education', ...)
    can be found later by exact line match.
    """
    try:
        resp = requests.get(profile_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=(5, 15))
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        return "", False

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer"]):
        tag.decompose()
    main = soup.select_one("main") or soup.body
    if not main:
        return "", True  # page loaded but had nothing usable -- don't keep retrying
    return main.get_text(separator="\n", strip=True)[:max_chars], True


# Section headings seen on IIT directory pages. Matched case-insensitively as
# a WHOLE LINE, so the word "Education" inside a sentence doesn't count.
_PREFERRED_SECTIONS = ["research interests", "research areas", "research", "areas of expertise", "expertise"]
_BIO_SECTIONS = {"biography", "about"}
# Weaker signals, used only when a page has no research section or prose bio
# (typical for industry adjuncts): what they build, practice or teach.
_FALLBACK_SECTIONS = [
    "projects", "professional activities", "patents", "experience",
    "professional experience", "teaching", "courses",
]
_OTHER_SECTIONS = {
    "education", "contact information", "publications", "selected publications",
    "awards", "honors and awards", "grants",
} | set(_FALLBACK_SECTIONS)
_ALL_SECTIONS = set(_PREFERRED_SECTIONS) | _BIO_SECTIONS | _OTHER_SECTIONS


def _extract_profile(raw_text: str):
    """Turn raw directory-page text into (title, profile_text)."""
    title, profile, _source = _extract_profile_with_source(raw_text)
    return title, profile


def _extract_profile_with_source(raw_text: str):
    """Turn raw directory-page text into (title, profile_text, source), where
    source is research | bio | fallback | publications | "" (nothing found).

    Drops the shared page chrome (tags, 'Home Office and Department Directory'),
    contact details and education, which otherwise make every faculty
    embedding look alike. Prefers the Research Interests / Expertise sections,
    then a prose bio, then (as a last resort) publication titles.
    """
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

    # Title = lines before the "Tags:" line, minus the person's name line.
    title = ""
    for i, ln in enumerate(lines):
        if ln.lower().startswith("tags"):
            head = lines[1:i] if i > 1 else []
            title = ", ".join(head)[:150]
            break

    sections = collections.defaultdict(list)
    current = "_intro"
    for ln in lines:
        key = ln.lower().rstrip(":")
        if key in _ALL_SECTIONS:
            current = key
            continue
        sections[current].append(ln)

    source = ""
    parts = [" ".join(sections[k]) for k in _PREFERRED_SECTIONS if sections.get(k)]
    if parts:
        source = "research"

    if not parts:
        bio_lines = sections.get("_intro", []) + sections.get("biography", []) + sections.get("about", [])
        prose = [ln for ln in bio_lines if len(ln) >= 80]  # skips short nav/chrome lines
        if prose:
            parts.append(" ".join(prose))
            source = "bio"

    if not parts:
        fallback = [" ".join(sections[k]) for k in _FALLBACK_SECTIONS if sections.get(k)]
        if fallback:
            parts.append(" ".join(fallback))
            source = "fallback"

    if not parts:
        pubs = sections.get("publications") or sections.get("selected publications")
        if pubs:
            parts.append("Publications: " + " ".join(pubs))
            source = "publications"

    profile = " ".join(parts)
    return title, profile[:MAX_PROFILE_CHARS], source


def _load_cache(cache_path: str) -> dict:
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                return json.load(f)
        except (OSError, ValueError):
            print(f"Warning: could not read {cache_path}; starting with an empty cache.")
    return {}


def build_research_index(
    directory_path: str = DIRECTORY_PATH,
    index_path: str = INDEX_PATH,
    cache_path: str = CACHE_PATH,
    fresh: bool = False,
    refresh_topics: bool = False,
):
    """Build research_index.json.

    Raw fetched data (directory text + OpenAlex topics + the reason a topic
    lookup came back empty) is cached in cache_path and checkpointed as it
    goes, so rerunning after a crash or a rate-limit problem only redoes what
    failed. fresh=True ignores the cache; refresh_topics=True also retries
    OpenAlex lookups that previously found nothing.
    """
    with open(directory_path) as f:
        directory = json.load(f)

    faculty = []
    for p in directory:
        if "Faculty" in p.get("tags", []) and p.get("profile_url"):
            faculty.append({**p, "profile_url": _clean_url(p["profile_url"])})
    print(f"Building research index for {len(faculty)} faculty entries...")

    cache = {} if fresh else _load_cache(cache_path)

    global _openalex_stopped, _consecutive_rate_limited
    _openalex_stopped, _consecutive_rate_limited = False, 0
    if not OPENALEX_API_KEY:
        print("Note: OPENALEX_API_KEY is not set. OpenAlex's keyless daily budget is very small; "
              "a free key (openalex.org/settings/api) is strongly recommended.")

    # ---- Phase 1: fetch (resumable) ----
    fetched_since_save = 0
    try:
        for i, person in enumerate(faculty, 1):
            name, url = person["name"], person["profile_url"]
            rec = cache.setdefault(url, {"name": name})
            did_fetch = False
            if i % 50 == 0:
                print(f"  ... at {i}/{len(faculty)} ({name})")

            if not rec.get("dir_ok"):
                text, ok = _fetch_directory_page(url)
                rec["directory_text"], rec["dir_ok"] = text, ok
                did_fetch = True
                time.sleep(0.3)  # politeness delay for the directory site

            status = rec.get("topics_status")
            if status in RETRYABLE_TOPIC_STATUSES or (refresh_topics and status != "ok"):
                rec["topics"], rec["topics_status"] = _openalex_lookup(name)
                did_fetch = True

            if did_fetch:
                fetched_since_save += 1
                print(f"  [{i}/{len(faculty)}] {name}: directory={'ok' if rec['dir_ok'] else 'FAILED'}, "
                      f"topics={rec['topics_status']}")
                if fetched_since_save >= CACHE_SAVE_EVERY:
                    _atomic_json_dump(cache, cache_path)
                    fetched_since_save = 0
    finally:
        _atomic_json_dump(cache, cache_path)  # also on Ctrl-C or an unexpected error

    status_counts = collections.Counter(cache[p["profile_url"]].get("topics_status") for p in faculty)
    print("OpenAlex topic lookups:", dict(status_counts))
    dir_failed = sum(1 for p in faculty if not cache[p["profile_url"]].get("dir_ok"))
    if dir_failed:
        print(f"Directory pages that failed to load: {dir_failed} (rerun --build to retry them)")
    if status_counts.get("rate_limited") or status_counts.get("error"):
        print("Some topic lookups were rate-limited or errored -- rerun --build to retry just those.")

    # ---- Phase 2: clean profiles and embed ----
    index = []
    skipped = 0
    consecutive_embed_failures = 0
    embed_failures = 0
    print("Embedding profiles...")
    for i, person in enumerate(faculty, 1):
        name, url = person["name"], person["profile_url"]
        rec = cache[url]
        topics = rec.get("topics", [])
        title, profile, profile_source = _extract_profile_with_source(rec.get("directory_text", ""))

        if not profile and not topics:
            skipped += 1
            reason = "directory page failed to load" if not rec.get("dir_ok") else "no research content"
            print(f"  [{i}/{len(faculty)}] {name}: {reason} -- skipped")
            continue

        parts = []
        if title:
            parts.append(title + ".")
        if topics:
            parts.append("Research topics: " + ", ".join(topics) + ".")
        if profile:
            parts.append(profile)
        profile_text = " ".join(parts)

        try:
            embedding = embeddings_model.embed_query(DOC_PREFIX + profile_text)
            consecutive_embed_failures = 0
        except Exception as exc:  # embedding backend (Ollama) errors vary
            consecutive_embed_failures += 1
            embed_failures += 1
            print(f"  [{i}/{len(faculty)}] {name}: embedding failed ({exc})")
            if consecutive_embed_failures >= 5:
                raise ResearchIndexError(
                    "Embedding failed 5 times in a row. Is Ollama running and "
                    "`nomic-embed-text` pulled? Your fetched data is safe in "
                    f"{cache_path}; fix Ollama and rerun --build."
                ) from exc
            continue

        index.append({
            "name": name,
            "profile_url": url,
            "email": person.get("email", "N/A"),
            "title": title,
            "topics": topics,
            "profile_source": profile_source,
            "summary": profile_text[:400],
            "embedding": embedding,
        })

    if not index:
        # Never overwrite a working index with an empty one.
        raise ResearchIndexError(
            f"No entries were embedded, so {index_path} was NOT written. "
            f"Your fetched data is safe in {cache_path}; fix the cause above and rerun --build."
        )
    if embed_failures:
        print(f"Warning: {embed_failures} profile(s) failed to embed and are missing from the index; "
              "rerun --build to retry them (nothing needs to be refetched).")

    payload = {
        "meta": {
            "version": 2,
            "embedding_model": "nomic-embed-text",
            "prefixes": True,
            "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        "entries": index,
    }
    _atomic_json_dump(payload, index_path)

    with_topics = sum(1 for e in index if e["topics"])
    print(f"Wrote {len(index)} entries to {index_path} "
          f"({with_topics} with OpenAlex topics, {skipped} skipped for no content).")
    return index


# ----- Runtime: load the pre-built index, no network needed here -----

RESEARCH_INDEX: list = []
_INDEX_META: dict = {}
_EMBEDDING_MATRIX = None  # row-normalized, one row per entry in RESEARCH_INDEX
_PENALTIES = None         # per-entry score penalty (weak profiles); same order


def _read_index_file(index_path: str = INDEX_PATH):
    """Return (entries, meta). Accepts both the current format
    ({"meta":..., "entries":[...]}) and the older bare-list format.
    """
    if not os.path.exists(index_path):
        return [], {}
    with open(index_path) as f:
        data = json.load(f)

    if isinstance(data, list):  # older index: no prefixes were used
        entries, meta = data, {"version": 1, "prefixes": False}
    else:
        entries, meta = data.get("entries", []), data.get("meta", {})

    cleaned = []
    for e in entries:
        if not e.get("embedding"):
            continue
        e["profile_url"] = _clean_url(e.get("profile_url", ""))
        e.setdefault("topics", [])
        e.setdefault("email", "N/A")
        e.setdefault("title", "")
        cleaned.append(e)
    return cleaned, meta


def _load_index(index_path: str = INDEX_PATH) -> list:
    return _read_index_file(index_path)[0]


def reload_index(index_path: str = INDEX_PATH):
    """(Re)load the index from disk into memory."""
    global RESEARCH_INDEX, _INDEX_META, _EMBEDDING_MATRIX, _PENALTIES
    RESEARCH_INDEX, _INDEX_META = _read_index_file(index_path)
    if RESEARCH_INDEX:
        matrix = np.array([e["embedding"] for e in RESEARCH_INDEX], dtype=float)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        _EMBEDDING_MATRIX = matrix / norms
        _PENALTIES = np.array([WEAK_PROFILE_PENALTY if _is_weak(e) else 0.0 for e in RESEARCH_INDEX])
    else:
        _EMBEDDING_MATRIX = None
        _PENALTIES = None


_STOPWORDS = {
    "a", "an", "and", "or", "the", "of", "in", "on", "for", "to", "with", "at", "by", "from",
    "about", "into", "is", "are", "who", "what", "which", "does", "do", "how", "i", "me", "my",
    "research", "researcher", "researchers", "professor", "professors", "faculty", "study",
    "studies", "work", "works", "working", "interested", "interest", "interests", "undergraduate",
    "opportunities", "opportunity", "topic", "area", "areas", "field",
}


def _content_tokens(text: str) -> list:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 2 and t not in _STOPWORDS]


def _word_key(token: str) -> str:
    """First 5 letters for longer words, so 'sustainable' matches 'sustainability'
    and 'architecture' matches 'architectural'; short words must match exactly."""
    return token[:5] if len(token) >= 5 else token


def _shares_query_word(interest: str, entry: dict) -> bool:
    """True if the entry's title/topics/profile text shares a content word with the query."""
    query_keys = {_word_key(t) for t in _content_tokens(interest)}
    if not query_keys:
        return False
    text = " ".join([entry.get("title", ""), " ".join(entry.get("topics", [])), entry.get("summary", "")])
    return bool(query_keys & {_word_key(t) for t in _content_tokens(text)})


def _select_matches(interest: str, ranked: list, max_results: int) -> list:
    """Apply the score thresholds (and the low-confidence word-match gate) to a
    ranked list of (entry, score). Returns at most max_results (entry, score)."""
    if not ranked:
        return []
    if ranked[0][1] >= MIN_BEST_SCORE:
        return [(e, s) for e, s in ranked[:max_results] if s >= SIMILARITY_THRESHOLD]
    scanned = [(e, s) for e, s in ranked[:LOW_CONFIDENCE_SCAN] if s >= SIMILARITY_THRESHOLD]
    if not any(_shares_query_word(interest, e) for e, _ in scanned):
        return []
    return [(e, s) for e, s in ranked[:max_results] if s >= SIMILARITY_THRESHOLD]


_DIRECTORY_NAME_KEYS = None


def _directory_name_keys() -> set:
    """Lowercase full names, 'first last' pairs and bare surnames from the
    faculty directory (loaded once). Empty if iit_directory.json isn't found."""
    global _DIRECTORY_NAME_KEYS
    if _DIRECTORY_NAME_KEYS is None:
        keys = set()
        if os.path.exists(DIRECTORY_PATH):
            try:
                with open(DIRECTORY_PATH) as f:
                    people = json.load(f)
            except (OSError, ValueError):
                people = []
            for person in people:
                tokens = [t.strip(".") for t in person.get("name", "").lower().split() if t.strip(".")]
                if tokens:
                    keys.add(" ".join(tokens))
                    keys.add(tokens[-1])
                    if len(tokens) >= 2:
                        keys.add(f"{tokens[0]} {tokens[-1]}")
        _DIRECTORY_NAME_KEYS = keys
    return _DIRECTORY_NAME_KEYS


def _looks_like_person_name(text: str) -> bool:
    """True if text is a faculty member's full name, 'first last', or surname
    (a leading 'Prof.'/'Dr.' is ignored)."""
    cleaned = re.sub(r"\b(prof|professor|dr)\b\.?", " ", text.lower())
    tokens = [t.strip(".") for t in cleaned.split() if t.strip(".")]
    return 0 < len(tokens) <= 4 and " ".join(tokens) in _directory_name_keys()


def _is_weak(entry: dict) -> bool:
    """Profile built only from projects/patents/publications, with no OpenAlex topics.
    (Entries from an older index have no profile_source and are never penalized.)"""
    return entry.get("profile_source") in WEAK_PROFILE_SOURCES and not entry.get("topics")


reload_index()


def _rank(interest: str) -> list:
    """All index entries as (entry, score), best first. The score is cosine
    similarity minus WEAK_PROFILE_PENALTY for weak profiles (see _is_weak)."""
    if _EMBEDDING_MATRIX is None:
        return []
    text = (QUERY_PREFIX + interest) if _INDEX_META.get("prefixes") else interest
    query = np.array(embeddings_model.embed_query(text), dtype=float)
    if query.shape[0] != _EMBEDDING_MATRIX.shape[1]:
        raise ResearchIndexError(
            f"Query embedding has {query.shape[0]} dimensions but the index has "
            f"{_EMBEDDING_MATRIX.shape[1]} -- was it built with a different model?"
        )
    norm = np.linalg.norm(query)
    if norm == 0:
        return []
    scores = _EMBEDDING_MATRIX @ (query / norm) - _PENALTIES
    return [(RESEARCH_INDEX[i], float(scores[i])) for i in np.argsort(-scores)]


@tool
def find_research_opportunities(interest: str, max_results: int = 3) -> str:
    """Find IIT faculty whose research matches a student's stated interest.
    Use this when a student asks about research opportunities, undergraduate
    research, or which professors work in a given field. Results show who
    WORKS in that area based on their public profile and publications -- this
    does NOT mean they currently have an open position or are taking
    students. Suggest the student email the professor directly or check
    IIT's official undergraduate research resources. Write `interest` as a
    full descriptive phrase and spell out any abbreviation (for example
    'human-computer interaction', not 'HCI'). Never use this for a person's
    name: for a named professor, use search_iit_faculty_directory or
    search_faculty_research instead.
    """
    if not RESEARCH_INDEX:
        return (
            "The research opportunities index hasn't been built yet. "
            "Run `python research_opportunities.py --build` first."
        )
    if not interest or not interest.strip():
        return "Please tell me what research area or topic you're interested in."

    max_results = max(1, min(int(max_results), 10))
    try:
        ranked = _rank(interest.strip())
    except ResearchIndexError as exc:
        return f"Research search is unavailable: {exc}"

    top = _select_matches(interest.strip(), ranked, max_results)
    if not top:
        if _looks_like_person_name(interest):
            # The chat model sometimes sends a surname here. Point it to the
            # right tools instead of reporting a (misleading) topic no-match.
            return (
                f"'{interest}' looks like a professor's name, not a research topic. "
                "Call search_iit_faculty_directory or search_faculty_research with the name instead."
            )
        return (
            f"{NO_MATCH_PREFIX} '{interest}'. "
            "You could try rephrasing your topic, or check IIT's department pages directly."
        )

    lines = [
        f"{MATCHES_PREFIX} '{interest}' (based on public profile/publication "
        "data -- NOT confirmation they have open positions or are accepting students):"
    ]
    for entry, _score in top:
        title_note = f" {entry['title']}." if entry.get("title") else ""
        topic_note = f" Topics: {', '.join(entry['topics'][:3])}." if entry["topics"] else ""
        lines.append(
            f"- {entry['name']} ({entry['email']}).{title_note}{topic_note}\n"
            f"  Profile: {entry['profile_url']}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build or test the research opportunities index.")
    parser.add_argument("interest", nargs="*", help="interest to search for, e.g. 'machine learning'")
    parser.add_argument("--build", action="store_true", help="(re)build research_index.json (resumes from cache)")
    parser.add_argument("--fresh", action="store_true", help="with --build: ignore the cache and refetch everything")
    parser.add_argument("--refresh-topics", action="store_true",
                        help="with --build: also retry OpenAlex lookups that found nothing")
    parser.add_argument("--stats", action="store_true", help="show index size and a few entries")
    parser.add_argument("--scores", action="store_true",
                        help="show the top 10 matches with raw similarity scores (for tuning the threshold)")
    args = parser.parse_args()

    if args.build:
        build_research_index(fresh=args.fresh, refresh_topics=args.refresh_topics)
    elif args.stats:
        print(f"{len(RESEARCH_INDEX)} entries in {INDEX_PATH} (meta: {_INDEX_META or 'none'})")
        print(f"{sum(1 for e in RESEARCH_INDEX if e['topics'])} have OpenAlex topics")
        for entry in RESEARCH_INDEX[:5]:
            print(f"- {entry['name']}: {entry['summary'][:100]}...")
    else:
        query = " ".join(args.interest)
        if not query:
            parser.print_help()
        elif args.scores:
            ranked = _rank(query)
            for entry, score in ranked[:10]:
                mark = " (weak profile, penalized)" if _is_weak(entry) else ""
                print(f"{score:.3f}  {entry['name']}  {entry['topics'][:2]}{mark}")
            best = ranked[0][1] if ranked else 0.0
            selected = _select_matches(query, ranked, 5)
            band = "confident" if best >= MIN_BEST_SCORE else "low-confidence (needs a shared word)"
            print(f"(thresholds: per-result {SIMILARITY_THRESHOLD}, confident best >= {MIN_BEST_SCORE}; "
                  f"best here is {best:.3f} = {band})")
            print("Tool would return:", [e["name"] for e, _ in selected] or "NO MATCH")
        else:
            print(find_research_opportunities.invoke({"interest": query}))
