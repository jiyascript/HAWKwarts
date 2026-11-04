"""Turns the course agent's tool results into a card for the website's side panel.

The course agent calls tools (catalog search, Banner offerings) through Gemini's
automatic function calling, and the SDK keeps every call and result on the
response object. We read those results back, ask Gemini once more to arrange the
single course in focus into a small fixed shape, and then CHECK every field
against the raw tool results: URLs must appear verbatim, and descriptions,
names, numbers and times must be found in the records. Anything that can't be
found is dropped, so the card can't show text the tools never returned.
"""
import json
import re
from contextvars import ContextVar

last_course_panel: ContextVar = ContextVar("last_course_panel", default=None)

CARD_TOOLS = {"search_catalog", "get_course_offering"}
MAX_SECTIONS = 12
_PER_TOOL_CHARS = 15_000
_TOTAL_CHARS = 45_000
_CODE_IN_TEXT = re.compile(r"\b[A-Za-z]{2,5}\s?-?\s?\d{3}[A-Za-z]?\b")


def _log(message):
    print(f"[COURSE PANEL] {message}", flush=True)


# ── reading the tool results back from the Gemini response ──

def _unwrap(payload):
    """The SDK wraps a function's return value as {"result": value}; some tools
    return their data as a JSON string. Hand back plain Python data."""
    try:
        payload = dict(payload)
    except (TypeError, ValueError):
        pass
    if isinstance(payload, dict) and set(payload) == {"result"}:
        payload = payload["result"]
    if isinstance(payload, str) and payload.strip()[:1] in ("[", "{"):
        try:
            return json.loads(payload)
        except ValueError:
            pass
    return payload


def collect_tool_results(response):
    """[{"name": ..., "result": ...}] for every tool the model called, in order."""
    results = []
    for content in getattr(response, "automatic_function_calling_history", None) or []:
        for part in getattr(content, "parts", None) or []:
            fr = getattr(part, "function_response", None)
            if fr is not None and getattr(fr, "name", None):
                results.append({"name": fr.name, "result": _unwrap(fr.response)})
    return results


# ── building the prompt ──

_PROMPT = """You prepare ONE course card for a university advising side panel.

Student question:
{question}

Assistant answer:
{answer}

Tool results (JSON from the course catalog and Banner):
{tools}

Reply with JSON only, in exactly this shape, or {{"course": null}}:
{{"course": {{
  "code": "MATH 100",
  "title": null,
  "credits": null,
  "description": null,
  "prerequisites": null,
  "corequisites": null,
  "satisfies": null,
  "catalog_url": null,
  "term": null,
  "sections": [
    {{"crn": null, "section": null, "instructor": null, "meeting": null, "seats": null}}
  ]
}}}}

Rules:
- Describe the single specific course the student asked about. If the question is about a
  program, a degree plan, a schedule analysis, several courses at once, or anything else
  that is not one course, reply {{"course": null}}.
- Use only information found in the tool results. Copy wording exactly (titles,
  descriptions, prerequisites, URLs). Use null for anything not present. Never guess.
- Keep prerequisite AND/OR logic and minimum grades as written.
- "meeting" is the days and times of one section, for example "Mon, Wed 11:25 AM-12:40 PM".
  "seats" is what the record shows about seats, for example "12 of 30 open", only if present.
- Include sections only for the term the student asked about (or the one in the answer),
  at most {max_sections}. "term" is that term, for example "Fall 2026".
- "catalog_url" must be a URL that appears in the tool results.
"""


def _render(tool_result):
    return json.dumps(tool_result["result"], ensure_ascii=False, default=str)


def _build_prompt(question, answer, relevant):
    chunks, used = [], 0
    for item in relevant:
        text = _render(item)[:_PER_TOOL_CHARS]
        text = text[: max(0, _TOTAL_CHARS - used)]
        used += len(text)
        chunks.append(f"[{item['name']}]\n{text}")
    return _PROMPT.format(
        question=question, answer=answer, tools="\n\n".join(chunks), max_sections=MAX_SECTIONS
    )


# ── cleaning what the model returned ──

def _parse_json(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[A-Za-z]*\s*|\s*```$", "", t).strip()
    candidates = [t]
    braces = re.search(r"\{.*\}", t, re.S)
    if braces:
        candidates.append(braces.group(0))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except ValueError:
            continue
    return None


def _s(value, multiline=False):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not multiline:
        value = " ".join(value.split())
    if not value or value.lower() in ("null", "n/a", "undefined"):
        return None
    return value


def normalize_code(code):
    """'math100', 'Math-100' -> 'MATH 100'. None if it isn't a course code."""
    c = re.sub(r"[^A-Za-z0-9]+", " ", str(code or "")).strip().upper()
    c = re.sub(r"([A-Z])(\d)", r"\1 \2", c)
    m = re.search(r"\b[A-Z]{2,5} \d{3}[A-Z]?\b", c)
    return m.group(0) if m else None


def _clean_card(raw):
    if not isinstance(raw, dict):
        return None
    code = normalize_code(raw.get("code"))
    if not code:
        return None
    sections = []
    for sec in (raw.get("sections") or [])[:MAX_SECTIONS]:
        if isinstance(sec, dict):
            cleaned = {k: _s(sec.get(k)) for k in ("crn", "section", "instructor", "meeting", "seats")}
            if any(cleaned[k] for k in ("crn", "section", "instructor", "meeting")):
                sections.append(cleaned)
    return {
        "code": code,
        "title": _s(raw.get("title")),
        "credits": _s(raw.get("credits")),
        "description": _s(raw.get("description"), multiline=True),
        "prerequisites": _s(raw.get("prerequisites"), multiline=True),
        "corequisites": _s(raw.get("corequisites"), multiline=True),
        "satisfies": _s(raw.get("satisfies")),
        "catalog_url": _s(raw.get("catalog_url")),
        "term": _s(raw.get("term")),
        "sections": sections,
    }


# ── checking every field against the raw tool results ──

_WORD = re.compile(r"[a-z0-9:]+")


def _norm_token(token):
    return (token.lstrip("0") or "0") if token.isdigit() else token  # "01" == "1"


def _tokens(text):
    return [_norm_token(t) for t in _WORD.findall(text.lower())]


def _compact(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


class _Evidence:
    def __init__(self, raw_text):
        self.raw = raw_text
        self.tokens = set(_tokens(raw_text))
        self.compact = _compact(raw_text)

    def has_code(self, code):
        return _compact(code) in self.compact

    def has_url(self, url):
        return url in self.raw

    def words_found(self, value, need=0.8):
        """At least `need` of the value's words (3+ letters, or any with a digit) occur in the records."""
        words = [w for w in _tokens(value) if len(w) >= 3 or any(ch.isdigit() for ch in w)]
        return not words or sum(w in self.tokens for w in words) / len(words) >= need

    def numbers_found(self, value):
        """Every number or time in the value occurs in the records."""
        return all(t in self.tokens for t in _tokens(value) if any(ch.isdigit() for ch in t))


def _ground(card, evidence):
    if not evidence.has_code(card["code"]):
        return None
    words = ("title", "description", "prerequisites", "corequisites", "satisfies", "term")
    numbers = ("credits",)
    for key in words:
        if card[key] and not evidence.words_found(card[key]):
            card[key] = None
    for key in numbers:
        if card[key] and not evidence.numbers_found(card[key]):
            card[key] = None
    if card["catalog_url"] and not evidence.has_url(card["catalog_url"]):
        card["catalog_url"] = None

    kept = []
    for sec in card["sections"]:
        for key in ("crn", "section", "meeting", "seats"):
            if sec[key] and not evidence.numbers_found(sec[key]):
                sec[key] = None
        if sec["instructor"] and not evidence.words_found(sec["instructor"]):
            sec["instructor"] = None
        if any(sec[k] for k in ("crn", "section", "instructor", "meeting")):
            kept.append(sec)
    card["sections"] = kept
    if not kept:
        card["term"] = None

    has_content = any(
        card[k] for k in ("title", "credits", "description", "prerequisites",
                          "corequisites", "satisfies", "catalog_url")
    ) or card["sections"]
    return card if has_content else None


# ── the public entry point ──

def build_course_panel(question, answer, tool_results, extract_json):
    """{"type": "course", "course": {...}} for the one course this turn is about, else None.
    `extract_json(prompt) -> str` is a single call to the model (injected so this
    module doesn't depend on the Gemini SDK)."""
    relevant = [r for r in tool_results if r["name"] in CARD_TOOLS]
    if not relevant:
        _log("no catalog or Banner tool ran; no card")
        return None
    if not _CODE_IN_TEXT.search(f"{question} {answer}"):
        _log("no course code in the question or answer; no card")
        return None

    reply = extract_json(_build_prompt(question, answer, relevant))
    parsed = _parse_json(reply)
    card = _clean_card(parsed.get("course")) if isinstance(parsed, dict) else None
    if card is None:
        _log("model found no single course to show")
        return None

    evidence = _Evidence("\n".join(_render(r) for r in relevant))
    card = _ground(card, evidence)
    if card is None:
        _log("nothing in the card could be matched to the tool results; no card")
        return None
    return {"type": "course", "course": card}
