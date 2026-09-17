from functools import lru_cache
from sentence_transformers import SentenceTransformer

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
