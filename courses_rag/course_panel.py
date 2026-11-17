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

# Set by ask_agent() each turn; read by the API after route_question().
last_course_panel: ContextVar = ContextVar("last_course_panel", default=None)
# Every course card from one turn when the question named several courses
# ("Tell me about CS 425 and CS 201"). last_course_panel stays the first one.
last_course_panels: ContextVar = ContextVar("last_course_panels", default=None)
MAX_COURSE_CARDS = 3

# Only these tools describe a course. Transcript and schedule tools are deliberately
# left out, so a student's own records never feed a card.
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


def _tools_text(relevant):
    chunks, used = [], 0
    for item in relevant:
        text = _render(item)[:_PER_TOOL_CHARS]
        text = text[: max(0, _TOTAL_CHARS - used)]
        used += len(text)
        chunks.append(f"[{item['name']}]\n{text}")
    return "\n\n".join(chunks)


def _build_prompt(question, answer, relevant):
    return _PROMPT.format(
        question=question, answer=answer, tools=_tools_text(relevant), max_sections=MAX_SECTIONS
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


# ── reading a card straight from a catalog record (no model call) ──

# Keys that say WHICH course a record is. Keys that merely mention other courses
# (a prerequisite "CS 115" on the CS 116 record) must never identify a record.
_NOT_IDENTITY = ("prereq", "coreq", "equiv", "note", "satisf", "title", "name", "descr", "credit", "url", "link")
_IDENTITY = ("code", "id", "number", "course", "subject")
_SCALAR = (str, int, float)


def _flatten(value, depth=0):
    """(key, value) pairs for the scalar fields of a record and of dicts nested inside
    it (such as a "metadata" block). Lists of plain values are kept; lists of records aren't."""
    pairs = []
    if isinstance(value, dict):
        for key, inner in value.items():
            if isinstance(inner, dict):
                if depth < 3:
                    pairs.extend(_flatten(inner, depth + 1))
            elif isinstance(inner, _SCALAR) and not isinstance(inner, bool):
                pairs.append((str(key), inner))
            elif isinstance(inner, list) and inner and all(isinstance(i, _SCALAR) for i in inner):
                pairs.append((str(key), inner))
    return pairs


def _records(result):
    """Every dict inside a tool result that has several plain fields, i.e. looks like a record."""
    found = []
    if isinstance(result, dict):
        if len(_flatten(result)) >= 3:
            found.append(result)
        for inner in result.values():
            found.extend(_records(inner))
    elif isinstance(result, list):
        for inner in result:
            found.extend(_records(inner))
    return found


def _whole_codes(value):
    """Course codes when the WHOLE value is one code or a list of cross-listed codes
    ("CS 115", "cs-115", "CS 401 / CSSP 401"). Prose that merely mentions a code gives none."""
    codes = set()
    for part in re.split(r"[/,;]|\bor\b", value, flags=re.IGNORECASE):
        cleaned = re.sub(r"[^A-Za-z0-9]+", " ", part).strip().upper()
        cleaned = re.sub(r"([A-Z])(\d)", r"\1 \2", cleaned)
        cleaned = re.sub(r"^COURSES? ", "", re.sub(r"\s+", " ", cleaned))
        if re.fullmatch(r"[A-Z]{2,5} \d{3}[A-Z]?", cleaned):
            codes.add(cleaned)
    return codes


def _identity_codes(flat):
    codes, subject, number = set(), None, None
    for key, value in flat:
        low = key.lower()
        if not isinstance(value, str) or any(bad in low for bad in _NOT_IDENTITY):
            continue
        if "subject" in low:
            subject = value
        if "number" in low:
            number = value
        if any(word in low for word in _IDENTITY):
            codes |= _whole_codes(value)
    if subject and number:
        codes |= _whole_codes(f"{subject} {number}")
    return codes


def _text_of(value, joiner):
    if isinstance(value, list):
        value = joiner.join(str(v).strip() for v in value if str(v).strip())
    return _s(value, multiline=True)


def _field(flat, wanted, exclude=()):
    for key, value in flat:
        low = key.lower()
        if any(w in low for w in wanted) and not any(x in low for x in exclude):
            return key, value
    return None, None


def direct_course_card(question, tool_results, target=None):
    """A card read straight from the catalog record of the ONE course the question names
    (or of `target`, when the caller already picked one of several), or None when it can't
    be done confidently (no code, several codes, no unique matching record, or the record
    lacks a title and some content). Values are copied from the record as they are, so
    nothing here can be invented."""
    if target is None:
        codes = {normalize_code(m) for m in _CODE_IN_TEXT.findall(question or "")} - {None}
        if len(codes) != 1:
            return None
        target = next(iter(codes))

    matches = []
    for item in tool_results:
        if item["name"] == "search_catalog":
            for record in _records(item["result"]):
                flat = _flatten(record)
                if target in _identity_codes(flat):
                    matches.append(flat)
    if not matches:
        return None

    def pick(wanted, exclude=(), joiner="; ", multiline=True):
        for flat in matches:                      # first record that has it wins
            key, value = _field(flat, wanted, exclude)
            if key is not None:
                text = _text_of(value, joiner)
                if text:
                    return text, key
        return None, None

    title, k_title = None, None
    for flat in matches:
        for key, value in flat:
            if key.lower() in ("title", "name", "course_title", "course_name") and isinstance(value, str):
                title, k_title = _s(value), key
                break
        if title:
            break
    description, k_desc = pick(("descr",))
    prerequisites, k_pre = pick(("prereq",), exclude=("coreq",))
    corequisites, k_co = pick(("coreq",))
    satisfies, k_sat = pick(("satisf", "attribute"), joiner=", ")
    credits, k_cred = pick(("credit",), multiline=False)
    url = None
    for flat in matches:
        for key, value in flat:
            if any(w in key.lower() for w in ("url", "link")) and isinstance(value, str) and value.startswith(("http://", "https://")):
                url = value.strip()
                break
        if url:
            break

    if not title or not (description or prerequisites or credits):
        return None
    _log(
        "catalog record keys used: "
        + ", ".join(f"{label}={k}" for label, k in (("title", k_title), ("credits", k_cred), ("description", k_desc),
                    ("prerequisites", k_pre), ("satisfies", k_sat)) if k)
    )
    return {
        "code": target, "title": title, "credits": credits, "description": description,
        "prerequisites": prerequisites, "corequisites": corequisites, "satisfies": satisfies,
        "catalog_url": url, "term": None, "sections": [],
    }


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

    # Only the catalog was consulted: read the card straight from its record, with no model call.
    if not any(r["name"] == "get_course_offering" for r in relevant):
        card = direct_course_card(question, relevant)
        if card is not None:
            _log("card read directly from the catalog record (no model call)")
            return {"type": "course", "course": card}

    if extract_json is None:
        return None
    _log("falling back to the model to arrange the card")
    try:
        reply = extract_json(_build_prompt(question, answer, relevant))
    except Exception as exc:
        # The model was unavailable (e.g. 503 high demand). Show what the catalog record
        # alone gives (no sections) rather than no card.
        _log(f"model call failed ({exc!r}); using the catalog record instead")
        card = direct_course_card(question, relevant)
        return {"type": "course", "course": card} if card is not None else None
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


# ── several courses in one question ──

_PROMPT_MULTI = """You prepare course cards for a university advising side panel.

Student question:
{question}

Assistant answer:
{answer}

Tool results (JSON from the course catalog and Banner):
{tools}

The student asked about these courses: {codes}.
Reply with JSON only, in exactly this shape (one entry per course listed above, in that order):
{{"courses": [{{
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
}}]}}

Rules:
- Use only information found in the tool results. Copy wording exactly (titles,
  descriptions, prerequisites, URLs). Use null for anything not present. Never guess.
- Keep prerequisite AND/OR logic and minimum grades as written.
- "meeting" is the days and times of one section, for example "Mon, Wed 11:25 AM-12:40 PM".
  "seats" is what the record shows about seats, for example "12 of 30 open", only if present.
- Include sections only for the term the student asked about (or the one in the answer),
  at most {max_sections} per course. "term" is that term, for example "Fall 2026".
- "catalog_url" must be a URL that appears in the tool results.
- Leave out a course that has no information in the tool results.
"""


def _question_codes(question):
    """Course codes in the question, in order, without repeats."""
    codes = []
    for match in _CODE_IN_TEXT.findall(question or ""):
        code = normalize_code(match)
        if code and code not in codes:
            codes.append(code)
    return codes


def build_course_panels(question, answer, tool_results, extract_json):
    """A list of course panels: one per course when the question names 2 to
    MAX_COURSE_CARDS courses, else the single panel build_course_panel gives (or []).

    Catalog-only turns read every card straight from the catalog records (no model
    call). When Banner sections are involved there is ONE model call for all the cards.
    If that call fails, the cards the catalog records can give are still returned."""
    codes = _question_codes(question)
    if not (2 <= len(codes) <= MAX_COURSE_CARDS):
        panel = build_course_panel(question, answer, tool_results, extract_json)
        return [panel] if panel else []

    relevant = [r for r in tool_results if r["name"] in CARD_TOOLS]
    if not relevant:
        _log("no catalog or Banner tool ran; no cards")
        return []

    direct = {}
    for code in codes:
        card = direct_course_card(question, relevant, target=code)
        if card is not None:
            direct[code] = card
    has_banner = any(r["name"] == "get_course_offering" for r in relevant)
    if not has_banner and len(direct) == len(codes):
        _log(f"{len(codes)} cards read directly from the catalog records (no model call)")
        return [{"type": "course", "course": direct[c]} for c in codes]

    cards = []
    if extract_json is not None:
        _log("asking the model to arrange the cards")
        try:
            prompt = _PROMPT_MULTI.format(
                question=question, answer=answer, codes=", ".join(codes), max_sections=MAX_SECTIONS,
                tools=_tools_text(relevant),
            )
            parsed = _parse_json(extract_json(prompt))
            evidence = _Evidence("\n".join(_render(r) for r in relevant))
            for raw in (parsed.get("courses") if isinstance(parsed, dict) else None) or []:
                card = _clean_card(raw)
                card = _ground(card, evidence) if card else None
                if card and card["code"] in codes and all(card["code"] != c["code"] for c in cards):
                    cards.append(card)
        except Exception as exc:
            _log(f"model call failed ({exc!r}); using the catalog records instead")
            cards = []
    for code in codes:                                    # fill in any the model missed
        if all(c["code"] != code for c in cards) and code in direct:
            cards.append(direct[code])
    cards.sort(key=lambda c: codes.index(c["code"]))
    return [{"type": "course", "course": c} for c in cards[:MAX_COURSE_CARDS]]
