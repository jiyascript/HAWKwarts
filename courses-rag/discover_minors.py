import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


INDEX_URL = (
    "https://catalog.iit.edu/"
    "undergraduate/undergraduate-education/minors/"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_PATH = DATA_DIR / "minors.json"


def clean_text(text: str) -> str:
    return " ".join(text.split())


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def main():
    response = requests.get(
        INDEX_URL,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    minors = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        name = clean_text(
            a.get_text(" ", strip=True)
        )

        href = urljoin(
            INDEX_URL,
            a["href"],
        )

        # Minor pages in the catalog use URLs such as:
        # /minor-applied-mathematics/
        # /minor-computer-science/
        if "/minor-" not in href:
            continue

        if href in seen_urls:
            continue

        seen_urls.add(href)

        minors.append(
            {
                "id": slugify(name),
                "name": name,
                "url": href,
                "source_url": INDEX_URL,
            }
        )

    minors.sort(
        key=lambda minor: minor["name"]
    )

    DATA_DIR.mkdir(exist_ok=True)

    with OUTPUT_PATH.open("w") as f:
        json.dump(
            minors,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"Discovered {len(minors)} minors."
    )

    for minor in minors:
        print(
            f"{minor['name']}: "
            f"{minor['url']}"
        )

    print()
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()