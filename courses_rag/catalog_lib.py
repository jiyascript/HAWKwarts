from functools import lru_cache
from sentence_transformers import SentenceTransformer
import json

MODEL_NAME = "BAAI/bge-base-en-v1.5"
EMBED_DIM = 768
# bge models are asymmetric: queries need this instruction prefix, documents don't.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed_query(text: str):
    model = get_model()
    return model.encode(QUERY_PREFIX + text, normalize_embeddings=True).tolist()


def course_to_text(course: dict) -> str:
    parts = [f"{course['code']}: {course['title']}."]
    if course.get("description"):
        parts.append(course["description"])
    if course.get("prerequisites_text"):
        parts.append(f"Prerequisites: {course['prerequisites_text']}.")
    if course.get("satisfies"):
        parts.append(f"Satisfies: {course['satisfies']}.")
    return " ".join(parts)


def course_to_metadata(course: dict) -> dict:
    # Pinecone metadata values must be str/number/bool/list[str] - no None.
    return {
        "subject": course["subject"],
        "code": course["code"],
        "title": course["title"],
        "description": course["description"][:4000],
        "credits": course.get("credits") or "",
        "prerequisites_text": course.get("prerequisites_text") or "",
        "prerequisite_codes": course.get("prerequisite_codes") or [],
        "satisfies": course.get("satisfies") or "",
        "url": course.get("url") or "",
    }

def minor_group_to_text(minor: dict, group: dict) -> str:
    lines = [
        f"Minor: {minor['name']}",
        f"Requirement: {group.get('context') or 'Course requirements'}",
    ]
    for requirement in group.get("requirements", []):
        kind = requirement.get("type")

        if kind == "course":
            code = requirement["course"]
            title = requirement.get("title", "")
            credits = requirement.get(
                "credits_text", requirement.get("credits")
            )

            line = f"- {code}: {title}"
            if credits is not None:
                line += f" ({credits} credits)"
            lines.append(line)

        elif kind == "choose":
            options = requirement.get("options", [])
            count = requirement.get("count")
            raw_text = requirement.get("raw_text", "")

            if raw_text:
                lines.append(raw_text)

            if count is not None:
                qualifier = "at least " if requirement.get("minimum") else ""
                lines.append(
                    f"Select {qualifier}{count} from: {', '.join(options)}"
                )
            else:
                lines.append(f"Options: {', '.join(options)}")

            if requirement.get("credits_required") is not None:
                lines.append(
                    f"Credits required: {requirement['credits_required']}"
                )

        elif kind == "one_of":
            options = requirement.get("options", [])
            lines.append(f"Choose one of: {', '.join(options)}")

        elif requirement.get("raw_text"):
            lines.append(requirement["raw_text"])

    return "\n".join(lines)


def minor_group_to_metadata(minor: dict, group: dict) -> dict:
    """Create Pinecone-compatible metadata for a requirement group."""
    course_codes = []
    for req in group.get("requirements", []):
        kind = req.get("type")
        if kind == "course":
            course_codes.append(req["course"])
        elif kind in ("choose", "one_of"):
            course_codes.extend(req.get("options", []))
    return {
        "doc_type": "minor_requirement",
        "minor_id": minor["minor_id"],
        "name": minor["name"],
        "group": group["group"],
        "context": group.get("context") or "",
        "course_codes": list(dict.fromkeys(course_codes)),
        "url": minor.get("url", ""),
    }

def minor_to_chunks(minor: dict) -> list[dict]:
    """Create searchable chunks for a minor, preserving requirement groups."""

    chunks = []

    for group in minor.get("requirement_groups", []):
        chunks.append({
            "id": f"minor:{minor['minor_id']}:group:{group['group']}",
            "text": minor_group_to_text(minor, group),
            "metadata": minor_group_to_metadata(minor, group),
        })

    # specific cases where there are requirements outside of the groups
    requirements = minor.get("requirements", [])

    if requirements:
        top_level_group = {
            "group": 0,
            "context": "General minor requirements",
            "requirements": requirements,
        }

        chunks.append({
            "id": f"minor:{minor['minor_id']}:general",
            "text": minor_group_to_text(minor, top_level_group),
            "metadata": minor_group_to_metadata(minor, top_level_group),
        })

    return chunks

def format_requirement_option(option) -> str:
    """Preserve course and free-text options as searchable text."""
    if isinstance(option, str):
        return option

    if isinstance(option, dict):
        if option.get("course"):
            code = option["course"]
            title = option.get("title", "")
            return f"{code}: {title}" if title else code

        if option.get("raw_text"):
            return option["raw_text"]

        return json.dumps(option, ensure_ascii=False)

    return str(option)

def program_section_to_text(program: dict, section: dict) -> str:
    """Convert one program requirement section into searchable text."""

    lines = [
        f"Program: {program['title']}",
        f"Credential: {program['credential']}",
        f"Level: {program['level']}",
        f"Section: {section['name']}",
    ]

    if section.get("credits") is not None:
        lines.append(f"Section credits: {section['credits']}")

    for item in section.get("items", []):
        kind = item.get("type")

        if kind == "course":
            line = f"- {item['course']}: {item.get('title', '')}"
            if item.get("credits") is not None:
                line += f" ({item['credits']} credits)"
            lines.append(line)

        elif kind in ("one_of", "choose"):
            options = [
                format_requirement_option(opt)
                for opt in item.get("options",[])
            ]

            if kind == "one_of":
                lines.append(f"Choose one of: {', '.join(options)}")
            else:
                count = item.get("count")
                qualifier = "at least " if item.get("minimum") else ""
                lines.append(
                    f"Choose {qualifier}{count} from: {', '.join(options)}"
                    if count is not None
                    else f"Choose from: {', '.join(options)}"
                )

            if item.get("credits_required") is not None:
                lines.append(
                    f"Credits required: {item['credits_required']}"
                )

        elif item.get("raw_text"):
            lines.append(item["raw_text"])

        else:
            # Preserve unexpected requirement structures.
            lines.append(json.dumps(item, ensure_ascii=False))

    return "\n".join(lines)


def program_to_chunks(program: dict) -> list[dict]:
    """Create searchable chunks for a degree or certificate program."""

    chunks = []

    for i, section in enumerate(program.get("requirements", []), start=1):
        course_codes = []

        for item in section.get("items", []):
            if item.get("type") == "course":
                course_codes.append(item["course"])
            elif item.get("type") in ("choose", "one_of"):
                course_codes.extend(
                    opt["course"]
                    for opt in item.get("options", [])
                    if isinstance(opt, dict) and opt.get("course")
                )

                course_codes.extend(
                    opt
                    for opt in item.get("options", [])
                    if isinstance(opt, str)
                )

        chunks.append({
            "id": f"program:{program['program_id']}:section:{i}",
            "text": program_section_to_text(program, section),
            "metadata": {
                "doc_type": "program_requirement",
                "program_id": program["program_id"],
                "name": program["name"],
                "credential": program["credential"],
                "level": program["level"],
                "section": section["name"],
                "course_codes": list(dict.fromkeys(course_codes)),
                "url": program.get("url") or "",
            },
        })

    # Preserve program-wide information separately.
    overview = [
        f"Program: {program['title']}",
        f"Credential: {program['credential']}",
        f"Level: {program['level']}",
    ]

    for field, label in [
        ("total_credits", "Total credits"),
        ("minimum_credits", "Minimum credits"),
    ]:
        if program.get(field) is not None:
            overview.append(f"{label}: {program[field]}")

    for constraint in program.get("credit_constraints", []):
        overview.append(
            "Credit constraint: "
            + (constraint if isinstance(constraint, str)
               else json.dumps(constraint, ensure_ascii=False))
        )

    for note in program.get("notes", []):
        overview.append(
            "Note: "
            + (note if isinstance(note, str)
               else json.dumps(note, ensure_ascii=False))
        )

    if len(overview) > 3:
        chunks.append({
            "id": f"program:{program['program_id']}:overview",
            "text": "\n".join(overview),
            "metadata": {
                "doc_type": "program_overview",
                "program_id": program["program_id"],
                "name": program["name"],
                "credential": program["credential"],
                "level": program["level"],
                "url": program.get("url") or "",
            },
        })

    return chunks


def specialization_item_to_text(item: dict) -> str:
    """Convert a specialization requirement into searchable text."""
    kind = item.get("type")

    if kind == "course":
        line = f"- {item['course']}: {item.get('title', '')}"
        if item.get("credits") is not None:
            line += f" ({item['credits']} credits)"
        return line

    if kind in ("choose", "one_of"):
        options = [
            format_requirement_option(opt)
            for opt in item.get("options", [])
        ]

        if kind == "one_of":
            line = f"Choose one of: {', '.join(options)}"
        else:
            count = item.get("count")
            qualifier = "at least " if item.get("minimum") else ""
            line = (
                f"Choose {qualifier}{count} from: {', '.join(options)}"
                if count is not None
                else f"Choose from: {', '.join(options)}"
            )

        if item.get("credits_required") is not None:
            line += f" ({item['credits_required']} credits required)"

        return line

    if item.get("raw_text"):
        return item["raw_text"]

    return json.dumps(item, ensure_ascii=False)


def specialization_to_chunks(spec: dict) -> list[dict]:
    """Create one searchable chunk per specialization."""
    lines = [
        f"Specialization: {spec['name']}",
        f"Parent program: {spec['parent_program_name']}",
        f"Credential: {spec['credential']}",
        "",
        "Required courses and requirements:",
    ]

    for item in spec.get("requirements", []):
        lines.append(specialization_item_to_text(item))

    if spec.get("recommended_electives"):
        lines.extend(["", "Recommended electives (not mandatory):"])

        for item in spec["recommended_electives"]:
            lines.append(specialization_item_to_text(item))

    course_codes = []

    for item in spec.get("requirements", []) + spec.get("recommended_electives", []):
        if item.get("type") == "course":
            course_codes.append(item["course"])
        elif item.get("type") in ("choose", "one_of"):
            course_codes.extend(
                opt["course"] if isinstance(opt, dict) else opt
                for opt in item.get("options", [])
                if isinstance(opt, str) or (
                    isinstance(opt, dict) and opt.get("course")
                )
            )

    return [{
        "id": f"specialization:{spec['id']}",
        "text": "\n".join(lines),
        "metadata": {
            "doc_type": "specialization_requirement",
            "specialization_id": spec["id"],
            "name": spec["name"],
            "parent_program_id": spec["parent_program_id"],
            "parent_program_name": spec["parent_program_name"],
            "credential": spec["credential"],
            "course_codes": list(dict.fromkeys(course_codes)),
            "url": spec.get("url") or "",
        },
    }]

