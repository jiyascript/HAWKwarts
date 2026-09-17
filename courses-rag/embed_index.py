"""Embed scraped courses with a HuggingFace sentence-transformers model
and upsert them into a Pinecone index.

"""

import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from catalog_lib import EMBED_DIM, course_to_metadata, course_to_text, get_model

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"


def get_index(pc: Pinecone, index_name: str):
    existing = set(pc.list_indexes().names())
    if index_name not in existing:
        print(f"Creating Pinecone index '{index_name}' (dim={EMBED_DIM})...")
        pc.create_index(
            name=index_name,
            dimension=EMBED_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return pc.Index(index_name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=str(DATA_DIR / "courses.json"))
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    pinecone_key = os.environ.get("PINECONE_API_KEY")
    if not pinecone_key:
        raise SystemExit("PINECONE_API_KEY not set. Copy .env.example to .env and fill it in.")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "iit-catalog")

    courses = json.loads(Path(args.file).read_text())
    print(f"Loaded {len(courses)} courses from {args.file}")

    print("Loading embedding model (first run downloads it)...")
    model = get_model()

    texts = [course_to_text(c) for c in courses]
    print("Embedding courses...")
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True)

    pc = Pinecone(api_key=pinecone_key)
    index = get_index(pc, index_name)

    vectors = [
        {"id": course["id"], "values": emb.tolist(), "metadata": course_to_metadata(course)}
        for course, emb in zip(courses, embeddings)
    ]

    print(f"Upserting {len(vectors)} vectors into '{index_name}'...")
    for i in range(0, len(vectors), args.batch_size):
        batch = vectors[i : i + args.batch_size]
        index.upsert(vectors=batch)
        print(f"  upserted {i + len(batch)}/{len(vectors)}")

    print("Done.")


if __name__ == "__main__":
    main()
