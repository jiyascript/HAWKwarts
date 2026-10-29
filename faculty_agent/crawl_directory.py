import requests
from bs4 import BeautifulSoup
import json
import time

BASE_URL = "https://www.iit.edu/directory/people"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def crawl_directory(max_pages=130):
    all_people = []
    for page in range(max_pages):
        print(f"Fetching page {page}...", flush=True)
        try:
            resp = requests.get(BASE_URL, params={"page": page}, headers=HEADERS, timeout=10)
        except requests.exceptions.RequestException as e:
            print(f"  Request failed: {e}")
            break
        if resp.status_code != 200:
            print(f"  Status {resp.status_code}, stopping.")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.profile-item")
        if not articles:
            print("  No profile-item articles found on this page — stopping.")
            break

        for article in articles:
            name_link = article.select_one("h3.arrow-link a")
            if not name_link:
                continue
            name = name_link.get_text(strip=True)
            profile_url = "https://www.iit.edu" + name_link["href"]

            tags = [li.get_text(strip=True) for li in article.select(".listing-item__tags ul li")]

            email_link = article.select_one(".person-email a")
            email = email_link.get_text(strip=True) if email_link else None

            all_people.append({
                "name": name,
                "profile_url": profile_url,
                "tags": tags,
                "email": email,
            })

        print(f"  Found {len(articles)} people on this page")
        time.sleep(0.5)

    return all_people

if __name__ == "__main__":
    people = crawl_directory()
    with open("iit_directory.json", "w") as f:
        json.dump(people, f, indent=2)
    print(f"Saved {len(people)} entries.")
