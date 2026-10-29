"""Internship search via The Muse public jobs API (v2).

Kept separate from faculty_agent.py so it can be tested on its own first:

    python internship_search.py software --location "Chicago, IL"
    python internship_search.py "data science" --location remote
    python internship_search.py --discover        # list real category names
    python internship_search.py --check           # show raw status + rate-limit headers

Notes on the data source:
- No API key is required (500 requests/hour). Setting the MUSE_API_KEY
  environment variable with a free registered key raises that to 3,600.
- Using the API requires agreeing to The Muse's API terms:
  https://www.themuse.com/developers/api/v2/terms  (read them, including any
  attribution/linking requirements, before shipping this in a demo.)
- The /jobs endpoint filters by category, level, company, and location, but
  has NO free-text keyword search. So we map the student's interest to likely
  categories, fetch a few pages of Internship-level jobs, and then filter and
  rank by keyword on our side.
- Listings carry a publication date but no application deadline, and The Muse
  only covers employers that appear on its platform, so results are a sample
  of what's out there, not everything.
"""

import argparse
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

MUSE_JOBS_URL = "https://www.themuse.com/api/public/jobs"

# Optional. Works without it, just with a lower hourly rate limit.
MUSE_API_KEY = os.environ.get("MUSE_API_KEY")

CACHE_TTL_SECONDS = 60 * 60   # reuse identical requests for an hour
MIN_REQUEST_INTERVAL = 0.3    # polite pacing between live requests
DEFAULT_MAX_PAGES = 3         # 20 jobs per page -> up to 60 jobs per category


class InternshipSearchError(Exception):
    """The search couldn't be completed (network problem, rate limit, etc.)."""


class InvalidFilterError(InternshipSearchError):
    """The API rejected a filter value (e.g. a category name it doesn't know)."""


@dataclass
class Internship:
    title: str
    company: str
    locations: list = field(default_factory=list)
    categories: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    posted: str = ""          # YYYY-MM-DD
    url: str = ""
    description: str = ""     # plain text, HTML stripped
    source: str = "The Muse"


# A descriptive User-Agent. Some servers reject requests that look anonymous.
REQUEST_HEADERS = {"User-Agent": "IIT-student-advisor-internship-search/0.1 (class project)"}


def _rate_limit_info(resp) -> dict:
    """The Muse sends these headers with every response (per its docs)."""
    return {
        name: resp.headers.get(name)
        for name in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset")
    }


# ----- HTTP with caching, pacing, and rate-limit handling -----

_cache: dict = {}
_last_request_time = 0.0


def _muse_get(params: list, retries: int = 2, backoff: float = 2.0) -> dict:
    """GET /jobs with a 1-hour cache, request pacing, and retries on rate limits.
    `params` is a list of (key, value) tuples because The Muse expects repeated
    keys for multiple values.
    """
    global _last_request_time

    cache_key = tuple(params)
    cached = _cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    request_params = list(params)
    if MUSE_API_KEY:
        request_params.append(("api_key", MUSE_API_KEY))

    for attempt in range(retries + 1):
        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_time)
        if wait > 0:
            time.sleep(wait)

        try:
            resp = requests.get(MUSE_JOBS_URL, params=request_params, headers=REQUEST_HEADERS, timeout=10)
        except requests.exceptions.RequestException as e:
            raise InternshipSearchError(f"Could not reach The Muse API: {e}") from e
        _last_request_time = time.monotonic()

        # The Muse says 403 is "usually" a rate limit, so check the rate-limit
        # headers instead of assuming. Remaining == 0 means a real rate limit.
        if resp.status_code in (403, 429):
            info = _rate_limit_info(resp)
            remaining, reset = info["X-RateLimit-Remaining"], info["X-RateLimit-Reset"]
            is_rate_limit = resp.status_code == 429 or str(remaining) == "0"

            if is_rate_limit:
                try:
                    reset_seconds = int(float(reset))
                except (TypeError, ValueError):
                    reset_seconds = None
                # Only worth waiting if the window is about to reset.
                if reset_seconds is not None and reset_seconds <= 10 and attempt < retries:
                    time.sleep(reset_seconds + 1)
                    continue
                when = (
                    f"The limit resets in about {max(1, round(reset_seconds / 60))} minute(s). "
                    if reset_seconds is not None else ""
                )
                raise InternshipSearchError(
                    f"The Muse API rate limit was reached ({info['X-RateLimit-Limit'] or '500'} "
                    f"requests/hour without an API key). {when}"
                    "Set MUSE_API_KEY (free registration raises the limit to 3,600/hour)."
                )

            raise InternshipSearchError(
                f"The Muse API returned HTTP {resp.status_code} (forbidden), but the "
                f"rate-limit headers don't show an exhausted limit: {info}. "
                f"Response body: {resp.text[:200]!r}"
            )

        if resp.status_code == 400:
            raise InvalidFilterError(f"The Muse rejected the request: {resp.text[:200]}")

        try:
            resp.raise_for_status()
            data = resp.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            raise InternshipSearchError(f"Unexpected response from The Muse API: {e}") from e

        _cache[cache_key] = (time.monotonic(), data)
        return data

    raise InternshipSearchError("The Muse API request failed after retries.")


# ----- Parsing -----

def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    return BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)


def _parse_job(job: dict) -> Internship:
    return Internship(
        title=job.get("name") or "Untitled",
        company=(job.get("company") or {}).get("name") or "Unknown company",
        locations=[l["name"] for l in job.get("locations", []) if l.get("name")],
        categories=[c["name"] for c in job.get("categories", []) if c.get("name")],
        tags=[t["name"] for t in job.get("tags", []) if t.get("name")],
        posted=(job.get("publication_date") or "")[:10],
        url=(job.get("refs") or {}).get("landing_page") or "",
        description=_strip_html(job.get("contents") or ""),
    )


# ----- Keyword handling -----

_STOPWORDS = {
    "a", "an", "the", "for", "in", "at", "and", "or", "of", "to", "with", "me", "any",
    "internship", "internships", "intern", "interns", "summer", "fall", "spring",
    "opportunity", "opportunities", "job", "jobs", "position", "positions", "role",
    "roles", "find", "looking", "related", "about", "some",
}


def _tokenize(text: str) -> list:
    tokens = re.findall(r"[a-z0-9+#]+", (text or "").lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _contains(haystack: str, token: str) -> bool:
    """Word-ish match that tolerates simple plurals ('developers' ~ 'developer')."""
    if not token.isalnum():           # e.g. 'c++', 'c#'
        return token in haystack
    stem = token[:-1] if len(token) > 4 and token.endswith("s") else token
    pattern = rf"\b{re.escape(stem)}" if len(stem) > 3 else rf"\b{re.escape(stem)}\b"
    return re.search(pattern, haystack) is not None


def _score(job: Internship, tokens: list) -> int:
    """Title matches count most, then categories/tags, then the description."""
    if not tokens:
        return 0
    title = job.title.lower()
    meta = " ".join(job.categories + job.tags).lower()
    body = job.description.lower()
    score = 0
    for tok in tokens:
        if _contains(title, tok):
            score += 3
        elif _contains(meta, tok):
            score += 2
        elif _contains(body, tok):
            score += 1
    return score


# Best-effort mapping from a student's interest to The Muse category names.
# The Muse publishes no category list endpoint, so these names may not all be
# exact. Run `python internship_search.py --discover` to see the real ones and
# edit this table. Unknown categories are skipped safely.
_CATEGORY_HINTS = {
    "Software Engineering": {
        "software", "developer", "programming", "coding", "web", "frontend", "backend",
        "fullstack", "mobile", "app", "java", "python", "javascript", "react", "swe",
    },
    "Data Science": {"data", "machine", "learning", "ml", "ai", "artificial", "intelligence", "statistics"},
    "Data and Analytics": {"data", "analytics", "analyst", "analysis", "statistics", "bi"},
    "Computer and IT": {"it", "cybersecurity", "security", "network", "networking", "cloud", "devops", "systems", "infrastructure"},
    "Product Management": {"product", "pm"},
    "Design and UX": {"design", "ux", "ui", "designer"},
    "Science and Engineering": {
        "mechanical", "electrical", "civil", "chemical", "aerospace", "biomedical",
        "engineering", "hardware", "embedded", "robotics", "manufacturing",
    },
    "Accounting and Finance": {"finance", "accounting", "financial", "fintech", "banking", "investment"},
    "Marketing": {"marketing"},
}


def _guess_categories(tokens: list, limit: int = 3) -> list:
    token_set = set(tokens)
    ranked = sorted(
        ((len(token_set & hints), cat) for cat, hints in _CATEGORY_HINTS.items()),
        reverse=True,
    )
    return [cat for overlap, cat in ranked if overlap > 0][:limit]


_LOCATION_ALIASES = {
    "chicago": "Chicago, IL",
    "new york": "New York, NY",
    "nyc": "New York, NY",
    "san francisco": "San Francisco, CA",
    "boston": "Boston, MA",
    "seattle": "Seattle, WA",
    "austin": "Austin, TX",
}


def _normalize_location(location: str):
    """The Muse spells locations as 'City, ST' or 'Flexible / Remote'."""
    loc = (location or "").strip()
    if not loc:
        return None
    lowered = loc.lower()
    if "remote" in lowered:
        return "Flexible / Remote"
    return _LOCATION_ALIASES.get(lowered, loc)


# ----- Search -----

def search_internships(
    keywords: str = "",
    location: str = "",
    category: str = "",
    max_results: int = 5,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list:
    """Return up to `max_results` internships, best keyword matches first
    (ties broken by newest posting). Raises InternshipSearchError on failure.
    """
    tokens = _tokenize(keywords)
    loc = _normalize_location(location)
    categories = [category] if category else _guess_categories(tokens)

    def collect(category_list: list) -> dict:
        found: dict = {}
        for cat in category_list:
            for page in range(max_pages):
                params = [("level", "Internship"), ("page", str(page))]
                if cat:
                    params.append(("category", cat))
                if loc:
                    params.append(("location", loc))

                try:
                    data = _muse_get(params)
                except InvalidFilterError:
                    break  # unknown category/location value: skip this one

                results = data.get("results", [])
                for raw in results:
                    job = _parse_job(raw)
                    score = _score(job, tokens)
                    if tokens and score == 0:
                        continue
                    key = job.url or (job.title, job.company)
                    if key not in found or score > found[key][0]:
                        found[key] = (score, job)

                if not results or page + 1 >= data.get("page_count", 0):
                    break
        return found

    found = collect(categories or [None])
    if not found and categories:
        # Guessed categories may not exist or may be too narrow: retry with
        # just the Internship level and rely on keyword filtering.
        found = collect([None])

    ranked = sorted(found.values(), key=lambda sj: (sj[0], sj[1].posted), reverse=True)
    return [job for _, job in ranked[:max_results]]


def discover_categories(pages: int = 3) -> list:
    """Category names actually carried by Internship-level jobs right now,
    with counts. Use this to check/fix _CATEGORY_HINTS.
    """
    counts: Counter = Counter()
    for page in range(pages):
        data = _muse_get([("level", "Internship"), ("page", str(page))])
        results = data.get("results", [])
        for raw in results:
            counts.update(c["name"] for c in raw.get("categories", []) if c.get("name"))
        if not results or page + 1 >= data.get("page_count", 0):
            break
    return counts.most_common()


def check_api() -> str:
    """Make ONE live request and report exactly what came back (status code,
    rate-limit headers, start of the body). Run this when something looks off.
    """
    params = [("level", "Internship"), ("page", "0")]
    if MUSE_API_KEY:
        params.append(("api_key", MUSE_API_KEY))
    resp = requests.get(MUSE_JOBS_URL, params=params, headers=REQUEST_HEADERS, timeout=10)
    return (
        f"HTTP {resp.status_code}\n"
        f"API key in use: {'yes' if MUSE_API_KEY else 'no'}\n"
        f"Rate-limit headers: {_rate_limit_info(resp)}\n"
        f"Body (first 200 chars): {resp.text[:200]!r}"
    )


# ----- Formatting for the LLM / for people -----

def format_internships(results: list, keywords: str = "", location: str = "", notes: list = None) -> str:
    """Compact, structured text. Short on purpose (small local models handle
    short tool output better), and it only contains facts from the API.
    `notes` (optional) lists any source that failed or was skipped.
    """
    notes = notes or []
    note_lines = [f"Note: {n}" for n in notes]

    if not results:
        parts = [f"'{keywords}'" if keywords else "that search"]
        if location:
            parts.append(f"in {location}")
        base = (
            f"No internship listings found for {' '.join(parts)}. "
            "These sources do not cover every employer; suggest broader keywords, "
            "a different location, or checking company career pages directly."
        )
        return "\n".join([base] + note_lines)

    sources = sorted({job.source for job in results})
    lines = [
        f"Found {len(results)} internship listing(s) from {', '.join(sources)}. Listings can "
        "be out of date and may not show an application deadline; the link has current details."
    ] + note_lines
    for i, job in enumerate(results, 1):
        where = "; ".join(job.locations[:2]) if job.locations else "Location not listed"
        summary = job.description[:160].rsplit(" ", 1)[0] + "..." if len(job.description) > 160 else job.description
        lines.append(
            f"{i}. {job.title} - {job.company} [{job.source}]\n"
            f"   Location: {where} | Posted: {job.posted or 'unknown'}\n"
            f"   Link: {job.url or 'not provided'}\n"
            f"   Summary: {summary or 'not provided'}"
        )
    return "\n".join(lines)


# ----- LangChain tool (not wired into faculty_agent.py yet) -----

@tool
def find_internships(interest: str, location: str = "") -> str:
    """Find current internship listings matching a student's field of
    interest. Use this when a student asks about internships. `interest` is
    the field or skills, e.g. 'software engineering' or 'data science'.
    `location` is optional, e.g. 'Chicago, IL' or 'remote'. Searches The Muse,
    up to 5 listings with links. Does not list application deadlines and does
    not cover every employer -- only companies that post on The Muse.
    """
    try:
        results = search_internships(interest, location)
    except InternshipSearchError as e:
        return f"Internship search failed: {e}"
    return format_internships(results, interest, location)


# ----- Command-line test harness -----

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test internship search without the LLM.")
    parser.add_argument("keywords", nargs="*", help="field or skills, e.g. software")
    parser.add_argument("--location", default="", help='e.g. "Chicago, IL" or remote')
    parser.add_argument("--category", default="", help="exact Muse category name")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--discover", action="store_true", help="list real category names")
    parser.add_argument("--check", action="store_true", help="make one request and show the raw status/headers")
    parser.add_argument("--source", choices=["muse", "adzuna", "all"], default="all",
                         help="which source(s) to query (default: all)")
    args = parser.parse_args()

    try:
        if args.check:
            print(check_api())
        elif args.discover:
            for name, count in discover_categories():
                print(f"{count:4d}  {name}")
        else:
            kw = " ".join(args.keywords)
            if args.source == "muse":
                hits = search_internships(kw, args.location, args.category, args.max_results)
                print(format_internships(hits, kw, args.location))
            elif args.source == "adzuna":
                hits = search_adzuna(kw, args.location, args.max_results)
                print(format_internships(hits, kw, args.location))
            else:
                hits, notes = search_internships_all_sources(kw, args.location, args.max_results)
                print(format_internships(hits, kw, args.location, notes))
    except InternshipSearchError as e:
        print(f"Error: {e}")
