# test: python3 -m school_web.live_search "what is the add add drop deadline?"

import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.parse import urlparse

import requests
import trafilatura
from ddgs import DDGS

MAX_PAGES = 3 # how many pages to read per search
CACHE_SECONDS = 86400 # reuse a cached page for a day so repeat questions are faster

_cache = {}

def current_term(today=None):
    # current semester
    today = today or date.today()

    if (today.month, today.day) <= (5, 15):
        season = "Spring"
    elif (today.month, today.day) <= (8, 15):
        season = "Summer"
    else:
        season = "Fall"
    return f"{season} {today.year}"

def _is_school_site(url):
    # only iit.edu and its subdomains count as official sources to search
    host = urlparse(url).netloc.lower()
    return host == "iit.edu" or host.endswith(".iit.edu")


def _fetch_text(url):
    # get a page's main text. returns '' for PDFs, errors, or empty pages
    cached = _cache.get(url)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]

    text = ""
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        response.raise_for_status()
        if "text/html" in response.headers.get("Content-Type", ""):
            text = trafilatura.extract(response.text, include_tables=True, output_format="markdown") or ""
    except requests.exceptions.RequestException:
        pass

    _cache[url] = (time.monotonic(), text)
    return text

def _term_section(text, term):
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.startswith("#") and term.lower() in line.lower():
            start = i
            break
    if start is None:
        return ""

    level = len(lines[start]) - len(lines[start].lstrip("#"))
    section = [lines[start]]
    for line in lines[start + 1:]:
        if line.startswith("#") and len(line) - len(line.lstrip("#")) <= level:
            break
        section.append(line)
    return "\n".join(section).strip()

def _excerpt(text, query, term, max_chars=3000):
    # paragraphs that share most words with question
    result = _term_section(text, term)[:max_chars]

    words = {w for w in re.findall(r"[a-z0-9]+", f"{query} {term}".lower()) if len(w) > 3}
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    candidates = [
        (i, line) for i, line in enumerate(lines)
        if len(line) > 40 or any(word in line.lower() for word in words)
    ]
    scored = [(sum(word in line.lower() for word in words), i, line) for i, line in candidates]
    best = sorted(scored, key=lambda item: (-item[0], item[1]))[:15]
    best.sort(key=lambda item: item[1])

    for _, _, line in best:
        if len(result) + len(line) + 1 > max_chars:
            break
        if line not in result:
            result += "\n" + line
    return result.strip()

# questions whose answer depends on semester
_TERM_SENSITIVE = re.compile(
    r"deadline|calendar|date|last day|tuition|fee|drop|withdraw|register|exam|finals|break|semester|term",
    re.IGNORECASE,
)

PREFERRED_PATH = "iit.edu/registrar"

def search_school_web(query: str, term: str = "") -> dict:
    """Search Illinois Tech's official websites (iit.edu) and read the top pages.
    Use this for campus services, procedures, policies, deadlines, fees, financial
    aid, housing, IT, the library, and other general student questions.
    Pass term as the semester the student is asking about, like 'Fall 2026'.
    Leave it empty for the current semester.
    Returns page URLs, titles, and relevant excerpts.
    """
    term = term.strip() or current_term()
    print(f"\n[TOOL] search_school_web(query={query}, term={term})")

    search_text = f"{query} {term}" if _TERM_SENSITIVE.search(query) else query

    try:
        with DDGS() as ddgs:
            registrar_results = list(ddgs.text(f"{search_text} site:iit.edu/registrar", max_results=5))
            general_results = list(ddgs.text(f"{search_text} site:iit.edu", max_results=8))
    except Exception as exc:
        return {"found": False, "error": f"The web search failed: {exc}"}

    seen_urls = set()
    ordered = []

    for result in registrar_results + general_results:
        if result["href"] not in seen_urls and _is_school_site(result["href"]):
            seen_urls.add(result["href"])
            ordered.append(result)
            
    results = ordered[:MAX_PAGES]  
    if not results:
        return {"found": False, "message": "No iit.edu pages found for this search."}

    with ThreadPoolExecutor(max_workers=MAX_PAGES) as pool:
        texts = list(pool.map(_fetch_text, [r["href"] for r in results]))

    pages = []
    for result, text in zip(results, texts):
        pages.append({
            "url": result["href"],
            "title": result["title"],
            "snippet": result["body"],
            "excerpt": _excerpt(text, query, term) if text else "",
            "mentions_term": term.lower() in text.lower(),
        })

    return {
        "found": True,
        "term": term,
        "retrieved_on": date.today().isoformat(),
        "pages": pages,
        "note": (
            f"Read live today. A page with mentions_term false may describe a different "
            f"semester than {term}. Always say which semester a date refers to."
        ),
    }

if __name__ == "__main__":
    result = search_school_web(" ".join(sys.argv[1:]) or "add drop deadline")
    print("term:", result.get("term"))
    for page in result.get("pages", []):
        print(f"\n{page['url']}\n  {page['title']}\n  mentions term: {page['mentions_term']}"
              f"\n  excerpt: {len(page['excerpt'])} chars")
        print("  " + page["excerpt"][:400].replace("\n", " "))
    if not result.get("found"):
        print(result)