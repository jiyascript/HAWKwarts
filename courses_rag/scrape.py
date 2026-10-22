"""Scrape course data from the IIT catalog (catalog.iit.edu).

Usage:
    python scrape.py cs ece math          # scrape specific subjects
    python scrape.py --all                # discover and scrape every subject
    python scrape.py                      # defaults to just "cs"
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://catalog.iit.edu"
COURSES_INDEX = f"{BASE_URL}/courses/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; iit-catalog-rag/1.0)"}
DATA_DIR = Path(__file__).parent / "data"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def discover_subjects() -> list[str]:
    """Find every subject code linked from the catalog's course index page."""
    html = fetch(COURSES_INDEX)
    soup = BeautifulSoup(html, "html.parser")
    codes = set()
    for a in soup.find_all("a", href=True):
        m = re.match(r"^/courses/([a-z0-9]+)/$", a["href"])
        if m:
            codes.add(m.group(1))
    return sorted(codes)


def extract_prereq_codes(block) -> list[str]:
    """Pull referenced course codes (e.g. "CS 115") out of a prerequisite/corequisite block."""
    codes = []
    for a in block.find_all("a", href=True):
        m = re.search(r"[?&]P=([^&]+)", a["href"])
        if m:
            codes.append(clean_text(urllib.parse.unquote_plus(m.group(1))))
    return codes


def parse_courses(html: str, subject: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    courses = []

    for block in soup.select("div.courseblock"):
        code_el = block.select_one(".coursecode")
        title_el = block.select_one(".coursetitle")
        desc_el = block.select_one(".courseblockdesc")
        if not code_el or not title_el:
            continue

        code = clean_text(code_el.get_text(" ", strip=True))
        title = clean_text(title_el.get_text(" ", strip=True))
        description = clean_text(desc_el.get_text(" ", strip=True)) if desc_el else ""

        record = {
            "id": code,
            "subject": subject.upper(),
            "code": code,
            "title": title,
            "description": description,
            "credits": None,
            "lecture_hours": None,
            "lab_hours": None,
            "prerequisites_text": "",
            "prerequisite_codes": [],
            "corequisites_text": "",
            "satisfies": "",
            "url": source_url,
        }

        for attr in block.select("div.courseblockattr"):
            strong = attr.find("strong")
            if not strong:
                continue
            label = clean_text(strong.get_text(strip=True))
            full_text = clean_text(attr.get_text(" ", strip=True))
            value = full_text[len(label):].strip()

            if "hours" in attr.get("class", []):
                for span in attr.find_all("span"):
                    span_strong = span.find("strong")
                    if not span_strong:
                        continue
                    span_label = clean_text(span_strong.get_text(strip=True)).rstrip(":").lower()
                    span_value = clean_text(span.get_text(" ", strip=True))
                    span_value = span_value[len(clean_text(span_strong.get_text(strip=True))):].strip()
                    if span_label == "lecture":
                        record["lecture_hours"] = span_value
                    elif span_label == "lab":
                        record["lab_hours"] = span_value
                    elif span_label == "credits":
                        record["credits"] = span_value
            elif label.startswith("Prerequisite"):
                record["prerequisites_text"] = value
                record["prerequisite_codes"] = extract_prereq_codes(attr)
            elif label.startswith("Corequisite"):
                record["corequisites_text"] = value
            elif label.startswith("Satisfies"):
                record["satisfies"] = value

        courses.append(record)

    return courses


def scrape_subject(subject: str) -> list[dict]:
    url = f"{BASE_URL}/courses/{subject}/"
    print(f"Fetching {url} ...")
    html = fetch(url)
    courses = parse_courses(html, subject, url)
    print(f"  -> {len(courses)} courses")
    return courses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("subjects", nargs="*", default=["cs"], help="Subject codes, e.g. cs ece math")
    parser.add_argument("--all", action="store_true", help="Discover and scrape every subject in the catalog")
    parser.add_argument("--out", default=str(DATA_DIR / "courses.json"))
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)

    if args.all:
        subjects = discover_subjects()
        print(f"Discovered {len(subjects)} subjects: {', '.join(subjects)}")
    else:
        subjects = args.subjects

    all_courses = []
    for subject in subjects:
        try:
            all_courses.extend(scrape_subject(subject))
        except requests.HTTPError as e:
            print(f"  ! skipping {subject}: {e}", file=sys.stderr)
        time.sleep(0.5)  # be polite to the catalog server

    out_path = Path(args.out)
    out_path.write_text(json.dumps(all_courses, indent=2))
    print(f"\nWrote {len(all_courses)} courses to {out_path}")


if __name__ == "__main__":
    main()
