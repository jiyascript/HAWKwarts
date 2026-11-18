"""Internship search for the student advisor, using the public job-board APIs of
Greenhouse and Lever. No API keys and no accounts are needed.

How it works
- Neither service can search across companies, so we keep a list of employers in
  internship_companies.json (next to this file) and read each employer's open jobs.
- We keep only internships / co-ops (title or "Intern" commitment), rank them by how
  well they match the student's interest, and narrow by location if one is given.
- Results only cover the listed employers, and postings can be out of date or closed.
  Edit internship_companies.json to add or remove employers:
    {"name": "Stripe", "ats": "greenhouse", "token": "stripe"}   # boards.greenhouse.io/<token>
    {"name": "Palantir", "ats": "lever", "token": "palantir"}    # jobs.lever.co/<token>

Test from the command line (no LLM needed):
    python internship_search.py --check                   # which employers in the list respond
    python internship_search.py software --location Chicago
"""

import argparse
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

COMPANIES_FILE = Path(__file__).with_name("internship_companies.json")
GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{token}"

CACHE_TTL_SECONDS = 60 * 60   # reuse an employer's job list for an hour
MAX_WORKERS = 8               # employers fetched in parallel
REQUEST_HEADERS = {"User-Agent": "IIT-student-advisor-internship-search/0.2 (class project)"}

_INTERN_PATTERN = re.compile(r"\bintern(s|ship|ships)?\b|\bco-?op\b", re.I)


class InternshipSearchError(Exception):
    """The search couldn't be completed (no employer list, every employer failed, etc.)."""


@dataclass
class Internship:
    title: str
    company: str
    locations: list = field(default_factory=list)
    categories: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    posted: str = ""          # YYYY-MM-DD (Greenhouse: last updated)
    url: str = ""
    description: str = ""     # plain text
    source: str = ""



# ----- Text helpers -----

def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    return BeautifulSoup(html.unescape(raw), "html.parser").get_text(" ", strip=True)



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

_LOCATION_ALIASES = {
    "chicago": "Chicago, IL",
    "new york": "New York, NY",
    "nyc": "New York, NY",
    "san francisco": "San Francisco, CA",
    "boston": "Boston, MA",
    "seattle": "Seattle, WA",
    "austin": "Austin, TX",
}



def _location_matches(wanted: str, locations: list) -> bool:
    """True if any of the job's locations fits the student's wish ('Chicago', 'remote')."""
    wanted = (wanted or "").strip().lower()
    if not wanted:
        return True
    wanted = _LOCATION_ALIASES.get(wanted, wanted).lower()
    city = wanted.split(",")[0].strip()
    blob = " | ".join(locations).lower()
    if "remote" in wanted:
        return "remote" in blob
    return bool(city) and city in blob



# Words a major's internships usually use in their titles. These only ADD match terms
# (a search for "mechanical" also looks for "manufacturing", "hardware", ...), they never
# remove any. Edit freely; unknown fields just search the words the student typed.
_RELATED_TERMS = {
    "mechanical": ["manufacturing", "hardware", "thermal", "propulsion"],
    "electrical": ["hardware", "embedded", "firmware", "circuit", "power", "rf", "signal"],
    "computer": ["software", "developer", "backend", "frontend"],
    "software": ["developer", "backend", "frontend", "full-stack"],
    "civil": ["construction", "structural"],
    "architecture": ["architect", "construction", "building", "urban"],
    "chemical": ["process", "materials", "chemistry", "manufacturing"],
    "materials": ["chemistry", "manufacturing", "process"],
    "aerospace": ["propulsion", "avionics", "flight", "guidance", "structures", "space"],
    "biomedical": ["bioinformatics", "clinical", "biology", "lab", "genomics"],
    "biology": ["lab", "clinical", "genomics"],
    "data": ["analytics", "analyst", "machine", "learning", "science"],
    "math": ["quantitative", "quant", "analyst", "data"],
    "mathematics": ["quantitative", "quant", "analyst", "data"],
    "physics": ["quantitative", "quant", "hardware"],
    "finance": ["analyst", "investment", "risk", "banking", "accounting", "audit", "treasury"],
    "business": ["analyst", "operations", "strategy", "marketing", "product"],
    "psychology": ["clinical", "user", "health"],
    "cybersecurity": ["security", "threat", "infosec"],
    "robotics": ["autonomy", "controls", "perception", "hardware"],
}


# Words that fit almost every job title ("Software Engineering Intern" is not a civil or
# chemical internship). They count only when a student's search has nothing more specific.
_GENERIC_TERMS = {"engineering", "engineer", "engineers", "science", "sciences", "technology", "technical"}


def _specific(tokens: list) -> list:
    """The search terms that say something about the field. Falls back to all terms when
    every term is generic (a plain 'engineering' search)."""
    specific = [t for t in tokens if t not in _GENERIC_TERMS]
    return specific or tokens


def _search_groups(keywords: str) -> list:
    """One group per word the student typed: that word first, then its related title words.
    A role is scored once per group (the best match in it), so "software developer backend"
    counts once for the word "software" and a direct match outranks a related one."""
    raw = _tokenize(keywords)
    groups = [[t] + [x for x in _RELATED_TERMS.get(t, []) if x not in _GENERIC_TERMS] for t in raw]
    specific = [g for g in groups if g[0] not in _GENERIC_TERMS]
    return specific or groups


_RELATED_WEIGHT = 2 / 3     # a related word is worth two thirds of the student's own word


def _group_score(job: Internship, groups: list) -> float:
    total = 0.0
    for group in groups:
        best = _score(job, [group[0]])
        for extra in group[1:]:
            best = max(best, _RELATED_WEIGHT * _score(job, [extra]))
        total += best
    return total


def _expand(tokens: list) -> list:
    out = list(tokens)
    for t in tokens:
        for extra in _RELATED_TERMS.get(t, []):
            if extra not in out:
                out.append(extra)
    return out

# ----- Ranking: Chicago first, then the US, then elsewhere; graduate-level roles last -----

_FOREIGN = re.compile(
    r"\b(canada|mexico|hong kong|netherlands|germany|denmark|serbia|united kingdom|uk|england|london|"
    r"singapore|australia|india|japan|china|france|spain|ireland|poland|brazil|israel|switzerland|"
    r"sweden|taiwan|korea|europe|emea|apac|toronto|vancouver|montreal|amsterdam|berlin)\b", re.I)
_US_STATE_CODES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR".split())
# Two-letter country codes some boards use after a city ("Dublin, IE"). Codes that are also
# US states (IN, ID, CA, ...) are left out on purpose.
_FOREIGN_CODES = set("IE CH FR DE GB NL SG HK JP AU BR MX PL ES IT SE DK NO FI AT BE PT CZ RO RS TR AE ZA NZ KR TW CN PH VN TH MY UA GR HU BG HR".split())
_US_STATE = re.compile(r",\s*([A-Z]{2})\b")
_US_WORD = re.compile(r"\b(united states|usa|us|u\.s\.)\b", re.I)
_GRADUATE_ONLY = re.compile(r"\b(ph\.?d\.?|mba|doctoral|doctorate|graduate)\b", re.I)


def _place_tier(place: str) -> int:
    """0 Chicago / Illinois, 1 clearly US, 2 unclear (e.g. 'San Francisco'), 3 outside the US."""
    low = place.lower()
    if "chicago" in low or "illinois" in low or re.search(r",\s*il\b", low):
        return 0
    if _FOREIGN.search(place) or any(m.group(1) in _FOREIGN_CODES for m in _US_STATE.finditer(place)):
        return 3
    if any(m.group(1) in _US_STATE_CODES for m in _US_STATE.finditer(place)) or _US_WORD.search(place):
        return 1
    return 2


def _location_tier(job: Internship) -> int:
    """The best tier among a job's locations (a role open in Chicago and London counts as Chicago)."""
    return min((_place_tier(l) for l in job.locations), default=2)


_TIER_BONUS = {0: 2, 1: 1, 2: 1, 3: 0}   # added to the keyword score; title matches are worth 3 each


def _is_graduate_only(job: Internship) -> bool:
    """PhD / MBA / graduate-student roles, which most undergraduates cannot apply to."""
    return bool(_GRADUATE_ONLY.search(job.title))


# ----- Employer list -----

def load_companies() -> list:
    try:
        companies = json.loads(COMPANIES_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise InternshipSearchError(f"The employer list {COMPANIES_FILE.name} is missing.") from e
    except ValueError as e:
        raise InternshipSearchError(f"{COMPANIES_FILE.name} is not valid JSON: {e}") from e
    good = [c for c in companies if c.get("ats") in ("greenhouse", "lever") and c.get("token")]
    if not good:
        raise InternshipSearchError(f"{COMPANIES_FILE.name} lists no usable employers.")
    return good


# ----- Fetching one employer -----

_cache: dict = {}


def _get_json(url: str):
    """(status, json or None). Raises requests exceptions on network trouble."""
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=25)
    if resp.status_code != 200:
        return resp.status_code, None
    try:
        return 200, resp.json()
    except ValueError:
        return 502, None   # 200 but not JSON (e.g. a block page)


def _parse_greenhouse(company: dict, data) -> list:
    jobs = []
    for j in (data or {}).get("jobs", []):
        jobs.append(Internship(
            title=(j.get("title") or "Untitled").strip(),
            company=company["name"],
            locations=[(j.get("location") or {}).get("name") or ""] if (j.get("location") or {}).get("name") else [],
            categories=[d["name"] for d in j.get("departments", []) if d.get("name")],
            posted=(j.get("updated_at") or "")[:10],
            url=j.get("absolute_url") or "",
            source="Greenhouse",
        ))
    return jobs


def _parse_lever(company: dict, data) -> list:
    jobs = []
    for j in data if isinstance(data, list) else []:
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or ([cat["location"]] if cat.get("location") else [])
        created = j.get("createdAt")
        try:
            posted = datetime.fromtimestamp(created / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if created else ""
        except (TypeError, ValueError, OverflowError, OSError):
            posted = ""
        title = (j.get("text") or "Untitled").strip()
        if cat.get("commitment") and _INTERN_PATTERN.search(cat["commitment"]) and not _INTERN_PATTERN.search(title):
            title = f"{title} ({cat['commitment']})"   # keep the 'Intern' marker visible
        jobs.append(Internship(
            title=title,
            company=company["name"],
            locations=[l for l in locs if l],
            categories=[c for c in (cat.get("team"), cat.get("department")) if c],
            posted=posted,
            url=j.get("hostedUrl") or "",
            description=_strip_html(j.get("descriptionPlain") or "")[:400],
            source="Lever",
        ))
    return jobs


def _fetch_company(company: dict):
    """All open jobs for one employer: (jobs, error_text or None). Cached for an hour."""
    key = (company["ats"], company["token"])
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_SECONDS:
        return hit[1], None
    if company["ats"] == "greenhouse":
        url, parse = GREENHOUSE_URL.format(token=company["token"]), _parse_greenhouse
    else:
        url, parse = LEVER_URL.format(token=company["token"]) + "?mode=json", _parse_lever
    for attempt in range(2):          # big boards occasionally time out: try once more
        try:
            status, data = _get_json(url)
            break
        except requests.exceptions.RequestException as e:
            if attempt == 1:
                return [], f"{company['name']}: could not connect ({type(e).__name__})"
    if status == 404:
        return [], f"{company['name']}: board '{company['token']}' not found"
    if status != 200:
        return [], f"{company['name']}: HTTP {status}"
    jobs = parse(company, data)
    _cache[key] = (time.monotonic(), jobs)
    return jobs, None


def _is_internship(job: Internship) -> bool:
    return bool(_INTERN_PATTERN.search(job.title))


# ----- Search -----

MAX_POSTING_AGE_DAYS = 365


def _too_old(job: Internship) -> bool:
    """True for postings last updated more than a year ago. A missing/unreadable date is kept."""
    try:
        posted = datetime.strptime(job.posted, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return posted < datetime.now(timezone.utc) - timedelta(days=MAX_POSTING_AGE_DAYS)


def search_internships(keywords: str = "", location: str = "", max_results: int = 5):
    """(listings, notes). Best keyword matches first, newest first on ties.
    `notes` says how many employers could not be read. Raises InternshipSearchError
    only if the list is unusable or every employer failed."""
    companies = load_companies()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        fetched = list(pool.map(_fetch_company, companies))

    failures = [err for _, err in fetched if err]
    if len(failures) == len(companies):
        raise InternshipSearchError(
            "None of the employer job boards could be reached. " + "; ".join(failures[:3])
        )

    groups = _search_groups(keywords)
    ranked = []
    for jobs, _ in fetched:
        for job in jobs:
            if not _is_internship(job):
                continue
            if _too_old(job):
                continue
            if not _location_matches(location, job.locations):
                continue
            score = _group_score(job, groups)
            if groups and score == 0:
                continue
            score += _TIER_BONUS[_location_tier(job)]
            ranked.append((not _is_graduate_only(job), score, job.posted, job))
    # undergraduate-friendly roles first, then best match (Chicago and US roles get a boost), newest first
    ranked.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)

    notes = []
    if failures:
        notes.append(f"{len(failures)} of {len(companies)} employer boards could not be read, so results may be incomplete.")
    return [j for _, _, _, j in ranked[:max_results]], notes


def check_api() -> str:
    """Read every employer once and report which boards respond. Short on purpose."""
    companies = load_companies()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        fetched = list(pool.map(_fetch_company, companies))
    lines, ok = [], 0
    for company, (jobs, err) in zip(companies, fetched):
        if err:
            lines.append(f"FAIL  {err}")
        else:
            ok += 1
            n = sum(1 for j in jobs if _is_internship(j))
            lines.append(f"ok    {company['name']} ({company['ats']}): {len(jobs)} jobs, {n} internships")
    lines.append(f"\n{ok} of {len(companies)} boards responded. Fix or remove FAIL rows in {COMPANIES_FILE.name}.")
    return "\n".join(lines)


# ----- Formatting for the LLM / for people -----

def _where(job: Internship, show: int = 3, for_model: bool = True) -> str:
    """A role's locations for the model: Chicago/Illinois first, then the rest, with a count of
    any left out. Showing only two made the model guess the others ("including Chicago")."""
    if not job.locations:
        return "Location not listed"
    ordered = sorted(job.locations, key=_place_tier)
    text = "; ".join(ordered[:show])
    if len(ordered) > show:
        text += f" (+{len(ordered) - show} more" + ("; do not guess them)" if for_model else ")")
    return text


def format_internships(results: list, keywords: str = "", location: str = "", notes: list = None) -> str:
    notes = notes or []
    note_lines = [f"Note: {n}" for n in notes]
    if not results:
        parts = [f"'{keywords}'" if keywords else "that search"]
        if location:
            parts.append(f"in {location}")
        base = (
            f"No internship listings found for {' '.join(parts)} among the employers we check. "
            "Suggest broader keywords, a different location, Handshake / career services, "
            "or the career pages of companies the student likes."
        )
        return "\n".join([base] + note_lines)
    lines = [
        f"Found {len(results)} internship listing(s) from a fixed list of employers (not every employer). "
        "Postings can be out of date and may not show a deadline; the link has current details."
    ] + note_lines
    for i, job in enumerate(results, 1):
        where = _where(job)
        team = f" | Team: {', '.join(job.categories[:2])}" if job.categories else ""
        label = " (graduate-level)" if _is_graduate_only(job) else ""
        lines.append(
            f"{i}. {job.title}{label} - {job.company}\n"
            f"   Location: {where}{team} | Listed: {job.posted or 'unknown'}\n"
            f"   Link: {job.url or 'not provided'}"
        )
    return "\n".join(lines)


# ----- Keeping links honest -----

_URL = re.compile(r"https?://[^\s)\]>\"']+")
_BARE_DOMAIN = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:edu|com|org|gov|net|io|ai|co)\b(?:/[^\s)\]]*)?", re.I)


_LOCATION_LINE = re.compile(r"(?im)^(?P<head>[ \t]*(?:[-*][ \t]+)?\**Locations?\**:\**[ \t]*)(?P<value>[^\n]*)$")
_ITEM_START = re.compile(r"(?m)^(?=[ \t]*\d+\.[ \t])")


def _fix_locations(answer: str) -> str:
    """Rewrite each listing's Location line from the posting's real locations. The local model
    summarises long lists and sometimes adds a place ("including Chicago") that is not there."""
    by_url = {job.url: job for _, jobs in _cache.values() for job in jobs if job.url}
    blocks = _ITEM_START.split(answer)
    out = []
    for block in blocks:
        job = next((by_url[m.group(0).rstrip(".,;:!?")] for m in _URL.finditer(block)
                    if m.group(0).rstrip(".,;:!?") in by_url), None)
        if job is not None and job.locations:
            def fix(m):
                value = m.group("value")
                rest = value.split(" | ", 1)[1] if " | " in value else ""
                return m.group("head") + _where(job, for_model=False) + (f" | {rest}" if rest else "")
            block = _LOCATION_LINE.sub(fix, block, count=1)
        out.append(block)
    return "".join(out)


def _drop_bare_domains(text: str, keep_inside: set) -> str:
    """Remove web addresses written without http (e.g. 'careers.iit.edu'), except inside a
    real posting link."""
    spans = [m.span() for m in _URL.finditer(text) if m.group(0).rstrip(".,;:!?") in keep_inside]

    def drop(m):
        if any(a <= m.start() and m.end() <= b for a, b in spans):
            return m.group(0)
        return ""
    out = _BARE_DOMAIN.sub(drop, text)
    return re.sub(r"\b(at|on|via|from|visit)\s*([.,;])", r"\2", out)


_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")


def _known_urls() -> set:
    return {job.url for _, jobs in _cache.values() for job in jobs if job.url}


def _fix_url(url: str, known: set):
    """The real posting URL this one is, or a very close misspelling of (the 8B model
    sometimes types '.greenhouse/io/' for '.greenhouse.io/'), else None."""
    bare = url.rstrip(".,;:!?")
    if bare in known:
        return bare
    import difflib
    close = difflib.get_close_matches(bare, list(known), n=1, cutoff=0.9)
    return close[0] if close else None


def clean_internship_links(answer: str, strict: bool = False) -> str:
    """Use only links that came from the job boards: repair near-miss spellings and remove
    any other link (the model sometimes adds a Career Services or company link of its own,
    which the tool never returned). Link text is kept."""
    known = _known_urls()
    if not answer:
        return answer
    if not known:
        # No search ran, so no link in an internship answer can be checked. strict removes
        # them all (the model made them up); otherwise the answer is left alone.
        if not strict:
            return answer
        out = _MD_LINK.sub(lambda m: _URL.sub("", m.group(1)).strip(), answer)
        out = _drop_bare_domains(_URL.sub("", out), set())
        return re.sub(r"[ \t]+\n", "\n", out)

    def fix_text(text: str) -> str:
        return _URL.sub(lambda m: _fix_url(m.group(0), known) or "", text)

    def md(m):
        text, target = m.group(1), _fix_url(m.group(2), known)
        if target is None:
            text = fix_text(text).strip()
            return text
        return f"[{fix_text(text) or target}]({target})"

    out = _MD_LINK.sub(md, answer)
    out = _URL.sub(lambda m: _fix_url(m.group(0), known) or "", out)   # bare links
    out = _drop_bare_domains(out, known)
    out = _fix_locations(out)
    return re.sub(r"[ \t]+\n", "\n", out)


# ----- The student's own words -----
# The local model sometimes adds a place the student never mentioned ("in Chicago"), which
# hides valid results elsewhere. faculty_agent.ask() records the question, and the tool
# drops a location that does not appear in it.

_current_question = ""


def set_question(question: str) -> None:
    global _current_question
    _current_question = (question or "").lower()


def _location_in_question(location: str, question: str) -> bool:
    loc = (location or "").strip().lower()
    if not loc:
        return False
    city = loc.split(",")[0].strip()
    if city and city in question:
        return True
    return any(alias in question for alias, full in _LOCATION_ALIASES.items() if full.lower() == loc or alias == city)


# ----- LangChain tool -----

@tool
def find_internships(interest: str, location: str = "") -> str:
    """Find current internship listings matching a student's field of
    interest. Use this when a student asks about internships. `interest` is
    the field or skills, e.g. 'software engineering', 'mechanical engineering', 'civil', 'biomedical' or 'finance'. Pass the student's major or field as they said it.
    `location` is optional: pass it ONLY if the student named a place, e.g. 'Chicago' or 'remote'; never assume one. Searches the job boards
    of a fixed list of employers (Greenhouse and Lever), up to 5 listings with
    links. Does not list application deadlines and does not cover every employer.
    """
    if location and _current_question and not _location_in_question(location, _current_question):
        location = ""                  # the student did not name a place; do not narrow the search
    try:
        results, notes = search_internships(interest, location)
    except InternshipSearchError as e:
        return (
            f"Internship search is unavailable right now: {e} "
            "Tell the student live internship listings can't be searched at the moment and suggest "
            "Handshake / the university's career services office or a job board directly. "
            "Do not invent or guess any listings."
        )
    return format_internships(results, interest, location, notes)


# ----- Command-line test harness -----

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test internship search without the LLM.")
    parser.add_argument("keywords", nargs="*", help="field or skills, e.g. software")
    parser.add_argument("--location", default="", help='e.g. "Chicago" or remote')
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--check", action="store_true", help="test every employer in the list")
    args = parser.parse_args()
    try:
        if args.check:
            print(check_api())
        else:
            kw = " ".join(args.keywords)
            hits, notes = search_internships(kw, args.location, args.max_results)
            print(format_internships(hits, kw, args.location, notes))
    except InternshipSearchError as e:
        print(f"Error: {e}")
