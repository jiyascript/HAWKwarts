"""Embed scraped courses with a HuggingFace sentence-transformers model
and upsert them into a Pinecone index.

"""

import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from catalog_lib import EMBED_DIM, course_to_metadata, course_to_text, get_model, minor_to_chunks, program_to_chunks, specialization_to_chunks

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
    parser.add_argument("--dataset",choices=["courses", "minors", "programs", "specializations"],default="courses",help="Dataset to embed into Pinecone",)
    parser.add_argument("--file", default=str(DATA_DIR / "courses.json"))
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    pinecone_key = os.environ.get("PINECONE_API_KEY")
    if not pinecone_key:
        raise SystemExit("PINECONE_API_KEY not set. Copy .env.example to .env and fill it in.")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "iit-catalog")
    
    if args.dataset == "minors":
        data_file = DATA_DIR / "minor_requirements.json"
        minors = json.loads(data_file.read_text())

        records = [
            chunk
            for minor in minors
            for chunk in minor_to_chunks(minor)
        ]

        namespace = "requirements"
    
    elif args.dataset == "programs":
        programs = json.loads(
            (DATA_DIR / "program_requirements.json").read_text()
        )

        records = [
            chunk
            for program in programs
            for chunk in program_to_chunks(program)
        ]

        namespace = "requirements"

        print(f"Loaded {len(programs)} programs")
        print(f"Generated {len(records)} program chunks")

    elif args.dataset == "specializations":
        specializations = json.loads(
            (DATA_DIR / "specializations.json").read_text()
        )

        # TODO: Revisit ITM degree pathways and subject-area, grouping. The course info is not currently preserved for exact requirement lookup. 
        excluded_ids = {
            "information-technology-and-management:m-s:master-of-science-in-information-technology-and-management-coursework-only-option-without-specialization",
            "information-technology-and-management:mas:master-of-information-technology-and-management-with-specialization",
        }

        records = [
            chunk
            for spec in specializations
            if spec["id"] not in excluded_ids
            and not (
                spec["parent_program_id"]
                == "information-technology-and-management:mas"
                and spec["name"].startswith("Subject:")
            )
            for chunk in specialization_to_chunks(spec)
        ]

        namespace = "requirements"
        print(f"Loaded {len(specializations)} specializations")
        print(f"Generated {len(records)} specialization chunks")
    else:
        courses = json.loads(Path(args.file).read_text())

        records = [
            {
                "id": course["id"],
                "text": course_to_text(course),
                "metadata": course_to_metadata(course),
            }
            for course in courses
        ]
        namespace = ""

    print(f"Loaded {len(records)} records for {args.dataset}")


    print("Loading embedding model (first run downloads it)...")
    model = get_model()

    texts = [record["text"] for record in records]
    print("Embedding courses...")
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True)

    pc = Pinecone(api_key=pinecone_key)
    index = get_index(pc, index_name)
    vectors = [
        {
            "id": record["id"],
            "values": emb.tolist(),
            "metadata": record["metadata"],
        }
        for record, emb in zip(records, embeddings)
    ]

    print(f"Upserting {len(vectors)} vectors into '{index_name}'...")
    for i in range(0, len(vectors), args.batch_size):
        batch = vectors[i : i + args.batch_size]
        index.upsert(vectors=batch, namespace=namespace)
        print(f"  upserted {i + len(batch)}/{len(vectors)}")

    print("Done.")


if __name__ == "__main__":
    main()
