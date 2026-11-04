"""Turns this turn's tool results into structured data for the website's
Courses & Faculty panel. Pure functions, no network or model calls."""
import re
from contextvars import ContextVar

last_panel: ContextVar = ContextVar("last_panel", default=None)

_DIRECTORY_TOOL = "search_iit_faculty_directory"
_RESEARCH_TOOL = "search_faculty_research"


def _this_turn_tool_messages(messages):
    """ToolMessages after the latest user message, oldest first."""
    out = []
    for msg in reversed(messages):
        kind = getattr(msg, "type", "")
        if kind == "human":
            break
        if kind == "tool":
            out.append(msg)
    out.reverse()
    return out


def _text(msg) -> str:
    content = getattr(msg, "content", "")
    return content if isinstance(content, str) else ""


_PHONE_RE = re.compile(r"\b\d{3}[.\-]\d{3}[.\-]\d{4}\b")
_EMAIL_RE = re.compile(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+")
# The directory tool cuts the profile page text at this many characters, so a
# section that runs to the very end of a text this long may be cut off mid-word.
_BIO_LIMIT = 600


def parse_profile_text(bio, name):
    """Pull structured fields out of the directory profile page text, which looks like:
    '<Name> <Position> Tags: Faculty ... Education <..> Research Interests <..>
     Contact Information <email> <phones> <office>'.
    Every field is optional; anything not confidently found is left empty."""
    out = {"position": None, "education": None, "research_interests": None,
           "phones": [], "office": None}
    if not bio:
        return out
    text = " ".join(bio.split())
    truncated = len(bio) >= _BIO_LIMIT

    if name:
        m = re.match(rf"{re.escape(name)}\s+(.+?)\s+Tags:", text, re.I)
        if m and len(m.group(1)) <= 120:
            out["position"] = m.group(1).strip()

    rest = text.split("Tags:", 1)[1] if "Tags:" in text else text

    def section(label):
        m = re.search(
            rf"\b{label}\s+(.+?)(?:\s+(Research Interests|Contact Information)\b|$)", rest
        )
        if not m:
            return None
        if m.group(2) is None and truncated:
            return None  # ran into the cut-off, so it may be a partial sentence
        value = m.group(1).strip()
        return value or None

    out["education"] = section("Education")
    out["research_interests"] = section("Research Interests")

    m = re.search(r"Contact Information\s+(.*)$", rest)
    if m:
        contact = m.group(1)
        out["phones"] = _PHONE_RE.findall(contact)
        leftover = _PHONE_RE.sub(" ", _EMAIL_RE.sub(" ", contact))
        leftover = " ".join(leftover.split())
        if 2 <= len(leftover) <= 60 and not truncated:
            out["office"] = leftover
    return out


def parse_directory(text: str):
    """Parse search_iit_faculty_directory output for ONE matched person.
    Returns None for 'not found' / 'multiple matches' results."""
    if not text.startswith("Name:"):
        return None
    name = re.search(r"^Name:\s*(.+)$", text, re.M)
    titles = re.search(r"^Titles:\s*(.+)$", text, re.M)
    email = re.search(r"^Email:\s*(.+)$", text, re.M)
    profile = re.search(r"^Profile:\s*(\S+)", text, re.M)
    bio = re.search(r"Full profile text:\s*(.+)$", text, re.S)

    def clean(m):
        v = m.group(1).strip() if m else None
        return None if v in (None, "", "N/A", "None") else v

    title_str = clean(titles)
    parsed_name = clean(name)
    bio_text = clean(bio)
    return {
        "name": parsed_name,
        "titles": [t.strip() for t in title_str.split(",")] if title_str else [],
        "email": clean(email),
        "profile_url": clean(profile),
        "bio": bio_text,
        **parse_profile_text(bio_text, parsed_name),
    }


def parse_research(text: str):
    """Parse search_faculty_research output for ONE matched author.
    Returns None for 'not found', 'multiple matches' and error results."""
    if not text.startswith("Name:"):
        return None
    name = re.search(r"^Name:\s*(.+)$", text, re.M)
    works = re.search(r"^Works count:\s*(\d+)", text, re.M)
    cites = re.search(r"^Citations:\s*(\d+)", text, re.M)
    source = re.search(r"^Source:\s*(\S+)", text, re.M)
    pubs = []
    for line in text.splitlines():
        m = re.match(r"^- (.+?) \((\d{4}|n\.d\.)\)\s*$", line)
        if m:
            pubs.append(
                {"title": m.group(1).strip(),
                 "year": int(m.group(2)) if m.group(2).isdigit() else None}
            )
    return {
        "name": name.group(1).strip() if name else None,
        "works_count": int(works.group(1)) if works else None,
        "citations": int(cites.group(1)) if cites else None,
        "openalex_url": source.group(1) if source else None,
        "publications": pubs,
    }


def _first_last(name: str):
    toks = [t.strip(".") for t in (name or "").lower().split() if t.strip(".")]
    return (toks[0], toks[-1]) if toks else (None, None)


def _make_profile(directory, research):
    """Merge one professor's directory and research results into a panel profile."""
    name = (directory or research or {}).get("name")
    if not name:
        return None
    return {
        "type": "professor",
        "profile": {
            "name": name,
            "titles": directory["titles"] if directory else [],
            "email": directory["email"] if directory else None,
            "profile_url": directory["profile_url"] if directory else None,
            "bio": directory["bio"] if directory else None,
            "position": directory["position"] if directory else None,
            "education": directory["education"] if directory else None,
            "research_interests": directory["research_interests"] if directory else None,
            "phones": directory["phones"] if directory else [],
            "office": directory["office"] if directory else None,
            "research": research,  # None if the research tool wasn't used/found nothing
        },
    }


def _same_person(a, b):
    """(first, last) pairs match; a lone initial matches any first name starting with it."""
    (af, al), (bf, bl) = a, b
    if not al or al != bl:
        return False
    return af == bf or (bool(af) and bool(bf) and af[0] == bf[0] and (len(af) == 1 or len(bf) == 1))


def _lookup(known, key):
    """Latest entry in `known` (oldest first) for the same person as `key`."""
    for other_key, value in reversed(list(known.items())):
        if _same_person(other_key, key):
            return value
    return None


def _known_from_history(messages):
    """Everything the tools have returned about each professor so far in this
    thread, as (directories, researches): {(first, last): parsed result}. When a
    professor was looked up more than once, the latest result wins."""
    directories, researches = {}, {}
    for msg in messages:
        if getattr(msg, "type", "") != "tool":
            continue
        tool = getattr(msg, "name", "")
        if tool == _DIRECTORY_TOOL:
            parsed, store = parse_directory(_text(msg)), directories
        elif tool == _RESEARCH_TOOL:
            parsed, store = parse_research(_text(msg)), researches
        else:
            continue
        if parsed and parsed["name"]:
            key = _first_last(parsed["name"])
            store.pop(key, None)  # re-insert so dict order reflects recency
            store[key] = parsed
    return directories, researches


def _profile_for(key, directories, researches):
    return _make_profile(_lookup(directories, key), _lookup(researches, key))


def _mention_index(first, last, text):
    """Position of this professor's name in text (earliest match), or -1.
    Accepted: the full name (a middle initial is fine), a title plus first or last
    name ("Prof. Saniie", "Dr. Jacek"), or a bare last name of 4+ letters (shorter
    ones need the full name or a title, to avoid matching ordinary words)."""
    text = (text or "").lower()
    title = r"(?:prof(?:essor)?|dr|doctor)\.?\s+"
    patterns = [
        rf"\b{re.escape(first)}\s+(?:[a-z]\.?\s+)?{re.escape(last)}\b",
        rf"\b{title}(?:{re.escape(first)}|{re.escape(last)})\b",
    ]
    if len(last) >= 4:
        patterns.append(rf"\b{re.escape(last)}\b")
    best = -1
    for pattern in patterns:
        m = re.search(pattern, text)
        if m and (best < 0 or m.start() < best):
            best = m.start()
    return best


def _mentioned_key(keys, question, answer):
    """The known professor named in the question, else in the answer (earliest mention)."""
    for text in (question, answer):
        best_key, best_pos = None, -1
        for key in keys:
            if not key[0] or not key[1]:
                continue
            pos = _mention_index(key[0], key[1], text)
            if pos >= 0 and (best_pos < 0 or pos < best_pos):
                best_key, best_pos = key, pos
        if best_key is not None:
            return best_key
    return None


def build_panel(messages, question=None, answer=None):
    """Return {"type": "professor", "profile": {...}} for the professor this turn is
    about, else None. `messages` is the whole thread, so the card is assembled from
    EVERYTHING the tools have returned about that person so far (directory and
    research together), not just this turn's results.

    Who the turn is about: the professor looked up by a tool this turn; failing
    that, when question/answer are given, the known professor named in the question
    or the answer. The second case covers a turn where the advisor answered from
    its chat memory, or its lookup failed, so a closed tab can be reopened."""
    directories, researches = _known_from_history(messages)

    this_directory = this_research = None
    for msg in _this_turn_tool_messages(messages):
        tool = getattr(msg, "name", "")
        if tool == _DIRECTORY_TOOL:
            this_directory = parse_directory(_text(msg)) or this_directory
        elif tool == _RESEARCH_TOOL:
            this_research = parse_research(_text(msg)) or this_research

    chosen = this_directory or this_research
    if chosen and chosen["name"]:
        key = _first_last(chosen["name"])
    elif question is not None or answer is not None:
        key = _mentioned_key(list({**directories, **researches}), question, answer)
    else:
        key = None
    if key is None:
        return None
    return _profile_for(key, directories, researches)


def tool_names_this_turn(messages):
    """Names of the tools that returned a result after the latest user message."""
    return [getattr(m, "name", "") for m in _this_turn_tool_messages(messages)]


def panel_from_directory_text(text, messages=None):
    """Panel for one professor from a raw search_iit_faculty_directory result, or None.
    With `messages`, research already returned about them earlier in the thread is
    included too."""
    directory = parse_directory(text or "")
    if not directory or not directory["name"]:
        return None
    research = None
    if messages:
        _, researches = _known_from_history(messages)
        research = _lookup(researches, _first_last(directory["name"]))
    return _make_profile(directory, research)


_TITLES = {"prof", "professor", "dr", "doctor"}


def _named(words, first, last):
    for i, word in enumerate(words):
        if word in _TITLES and i + 1 < len(words) and words[i + 1] in (first, last):
            return True
        if word == first and i + 1 < len(words):
            following = words[i + 1]
            if following == last:
                return True
            if len(following) == 1 and i + 2 < len(words) and words[i + 2] == last:
                return True  # middle initial: 
    return False


def people_named_in(text, directory):
    """Directory entries whose name appears in text: the full name (a middle initial
    is fine) or a title plus a first/last name ("Prof. Saniie", "Dr. Jacek"). A bare
    last name alone doesn't count, so surnames that are ordinary words don't match."""
    words = re.findall(r"[a-z]+", (text or "").lower())
    if not words:
        return []
    found = []
    for person in directory:
        tokens = re.findall(r"[a-z]+", str(person.get("name", "")).lower())
        if len(tokens) >= 2 and _named(words, tokens[0], tokens[-1]):
            found.append(person)
    return found


def has_directory_data(panel):
    p = panel["profile"]
    return bool(p["titles"] or p["email"] or p["profile_url"] or p["bio"])


def people_matching_name(name, directory):
    """Directory entries that are the same person as `name` (a middle initial or a
    lone first initial is fine)."""
    key = _first_last(name)
    return [p for p in directory if _same_person(_first_last(str(p.get("name", ""))), key)]


def panel_with_directory(panel, directory_text):
    """The panel's research plus the directory data from a raw
    search_iit_faculty_directory result. Unchanged if that result isn't usable."""
    directory = parse_directory(directory_text or "")
    if not directory or not directory["name"]:
        return panel
    return _make_profile(directory, panel["profile"]["research"])
