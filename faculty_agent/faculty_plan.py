"""Planning helpers for multi-part faculty questions. Pure functions: no model,
network or LangChain imports, so they are fast to test.

Why this exists: the 8B chat model is unreliable at deciding to call SEVERAL tools
in one turn (asked for a professor's background AND publications, it usually
calls only the directory tool). So code decides which lookups a question needs,
runs them, and the model only writes the answer from the results.
"""
import re

# How many professors one question may look up. Each adds a directory fetch (and
# an OpenAlex query when publications are wanted), so this keeps the wait short.
MAX_PEOPLE = 3

_RESEARCH = re.compile(
    r"\b(publications?|publish\w*|papers?|articles?|written|wrote|writes|cited|citations?|"
    r"h-?index|journals?|research\w*|recent work|studies|studied)\b",
    re.I,
)
_PRONOUN = re.compile(r"\b(he|his|him|she|her|hers|they|their|them)\b", re.I)


def wants_research(question):
    """True when the question asks about publications or research."""
    return bool(_RESEARCH.search(question or ""))


def has_pronoun(question):
    return bool(_PRONOUN.search(question or ""))


# ── "course + professor" questions ──────────────────────────────────────────
_COURSE_REF = re.compile(r"\b[a-z]{2,5}\s?-?\s?\d{3}[a-z]?\b|\b(course|class|section)\b", re.I)
_PROF_REF = re.compile(r"\b(professors?|prof|instructors?|faculty|teacher)\b", re.I)
_DETAIL = re.compile(
    r"\b(tell|about|research\w*|publications?|publish\w*|papers?|background|bio|email|"
    r"contact|office|profile|interests?|describe|more|written|wrote|expert\w*)\b",
    re.I,
)


def wants_both(question):
    """A question about a specific course AND details of its professor, such as
    "Tell me about CS 100 and the professor that teaches it". A plain "who teaches
    CS 331?" is not one: the course answer already lists instructors."""
    q = question or ""
    return bool(_COURSE_REF.search(q) and _PROF_REF.search(q) and _DETAIL.search(q))


# ── finding directory people in free text (a course answer, a Banner field) ─
def _first_names_match(a, b):
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= 3 and long_.startswith(short)  # matt / matthew


def people_in_text(text, directory, max_gap=2):
    """Directory entries whose first and last name appear in `text`, in order of
    appearance. Allows middle names or initials ("Michael Kamol Lee" finds
    "Michael Lee") and "Last, First" order. First names match exactly or as a
    nickname prefix (Matt / Matthew); when an exact match exists it wins, so
    "Matthew Bauer" does not also bring up "Matt Bauer"."""
    words = re.findall(r"[a-z]+", (text or "").lower())
    if not words:
        return []

    by_last = {}
    for person in directory:
        tokens = re.findall(r"[a-z]+", str(person.get("name", "")).lower())
        if len(tokens) >= 2:
            by_last.setdefault(tokens[-1], []).append((person, tokens[0]))

    found, seen = [], set()
    for i, word in enumerate(words):
        entries = by_last.get(word)
        if not entries:
            continue
        # first names appearing just before the surname, or just after it ("Lee, Michael")
        nearby = words[max(0, i - 1 - max_gap): i] + words[i + 1: i + 2]
        hits = [(p, first) for p, first in entries if any(_first_names_match(first, w) for w in nearby)]
        exact = [(p, first) for p, first in hits if first in nearby]
        for person, _ in exact or hits:
            key = person.get("profile_url") or person.get("name")
            if key not in seen:
                seen.add(key)
                found.append(person)
    return found


def split_instructors(field):
    """Instructor names out of one Banner-style field: "Matthew J. Bauer; Michael
    Lee", "Bauer, Matthew", or "Matthew Bauer and Michael Lee" -> name strings."""
    text = (field or "").strip()
    if not text:
        return []
    parts = re.split(r"\s*(?:;|/|\band\b|&|\|)\s*", text)
    out = []
    for part in parts:
        part = part.strip(" .,")
        if part and part.lower() not in {"tba", "staff", "n/a"}:
            out.append(part)
    return out


def _card_sections(course_card):
    """Section dicts from a course panel ({"type": "course", "course": {...}}), a bare card,
    or a list of either."""
    cards = course_card if isinstance(course_card, list) else [course_card]
    for card in cards:
        if not isinstance(card, dict):
            continue
        inner = card.get("course", card)
        for section in (inner.get("sections") if isinstance(inner, dict) else None) or []:
            if isinstance(section, dict):
                yield section


def instructors_from_course(course_card, course_answer, directory):
    """(people, unmatched) for a course lookup. `people` are directory entries for
    the instructors named in the course answer or in the course card's sections,
    most-mentioned-first order kept; `unmatched` are section instructors who are
    not in the directory (e.g. other campuses). No model calls."""
    people = list(people_in_text(course_answer or "", directory))
    seen = {p.get("profile_url") or p.get("name") for p in people}

    unmatched = []
    for section in _card_sections(course_card):
        for name in split_instructors(section.get("instructor")):
            matches = people_in_text(name, directory)
            if not matches:
                if name not in unmatched:
                    unmatched.append(name)
            for person in matches:
                key = person.get("profile_url") or person.get("name")
                if key not in seen:
                    seen.add(key)
                    people.append(person)

    # a name the answer already matched is not "unmatched" just because the
    # card spells it differently
    matched_last = {re.findall(r"[a-z]+", p.get("name", "").lower())[-1] for p in people if p.get("name")}
    unmatched = [
        n for n in unmatched
        if (re.findall(r"[a-z]+", n.lower()) or [""])[-1] not in matched_last
    ]
    return people, unmatched


def question_about_people(people, original_question):
    """A question for the faculty agent about specific people, keeping the
    original question's research/publication wish."""
    names = " and ".join(p["name"] for p in people)
    question = f"Tell me about {names}"
    if wants_research(original_question):
        question += " and their research and publications"
    return question
