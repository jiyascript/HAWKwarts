import json
import os
import re
from bs4 import BeautifulSoup

CACHE_DIR = ".cache"
OUTPUT_DIR = "data"

# CATALOG_HTML = r".cache\Fall 2026\catalog\CS.html"
# CATALOG_JSON = r".cache\Fall 2026\catalog\CS.json"
# SCHEDULE_HTML = r".cache\Fall 2026\schedule\CS.html"
# SCHEDULE_JSON = r".cache\Fall 2026\schedule\CS.json"
# OUTPUT_FILE = "courses.json"

def clean_text(text):
    return " ".join(text.split())

def get_labeled_value(text, label):
    pattern = label + r":\s*(.*?)(?=\n|$)"
    match = re.search(pattern, text)
    if match:
        return clean_text(match.group(1))
    return ""

def get_catalog_data(soup, catalog_json):
    catalog_courses = {}

    for title_row in soup.find_all("td", class_="nttitle"):
        link = title_row.find("a")
        if link is None:
            continue

        title_text = clean_text(link.get_text(" ", strip=True))
        match = re.search(
            r"^([A-Z0-9]+)\s+(\d+)\s*-\s*(.*)$",
            title_text
        )
        if not match:
            continue

        course_code = match.group(1)
        course_num = match.group(2)
        title = match.group(3)

        catalog_url = link.get("href", "")
        if catalog_url.startswith("/"):
            catalog_url = "https://ssb.iit.edu" + catalog_url

        title_tr = title_row.find_parent("tr")
        info_tr = title_tr.find_next_sibling("tr")
        if info_tr is None:
            continue

        info_cell = info_tr.find("td")
        if info_cell is None:
            continue

        description_text = clean_text(
            info_cell.get_text(" ", strip=True)
        )
        description = re.split(
            r"\d+\.\d+\s+(?:(?:OR|TO)\s+\d+\.\d+\s+)?Credit hours",
            description_text,
            maxsplit=1
        )[0].strip()

        # Find catalog syllabus
        syllabus_url = ""
        syllabus_link = info_cell.find(
            "a",
            string=lambda s: s and "Syllabus Available" in s,
            recursive=False
        )
        if syllabus_link:
            syllabus_url = syllabus_link.get("href", "")
            if syllabus_url.startswith("/"):
                syllabus_url = "https://ssb.iit.edu" + syllabus_url

        catalog_info = catalog_json.get(course_num, {})
        catalog_courses[course_code + course_num] = {
            "title": title,
            "catalog_entry_url": catalog_url,
            "course_description": description,
            "catalog_syllabus_url": syllabus_url,
            "catalog_restrictions": catalog_info.get("restrictions", ""),
            "mutual_exclusions": catalog_info.get("mutual_exclusion", "")
        }

    return catalog_courses

def process_department(semester, department):
    catalog_html_path = os.path.join(CACHE_DIR, semester, "catalog", department + ".html")
    catalog_json_path = os.path.join(CACHE_DIR, semester, "catalog", department + ".json")
    schedule_html_path = os.path.join(CACHE_DIR, semester, "schedule", department + ".html")
    schedule_json_path = os.path.join(CACHE_DIR, semester, "schedule", department + ".json")

    with open(catalog_html_path, "r", encoding="utf-8") as f:
        catalog_soup = BeautifulSoup(f, "html.parser")
    with open(catalog_json_path, "r", encoding="utf-8") as f:
        catalog_json = json.load(f)

    catalog_courses = get_catalog_data(catalog_soup, catalog_json)

    with open(schedule_html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    with open(schedule_json_path, "r", encoding="utf-8") as f:
        availability = json.load(f)
    
    courses = {}

    for heading in soup.find_all("th", class_="ddtitle"):
        link = heading.find("a")
        if link is None:
            continue

        heading_text = clean_text(link.get_text(" ", strip=True))

        match = re.search(
            r"^(.*?)\s*-\s*(\d+)\s*-\s*([A-Z0-9]+)\s+(\d+)\s*-\s*(\d+)$",
            heading_text
        )
        if not match:
            continue

        schedule_title = match.group(1)
        crn = match.group(2)
        course_code = match.group(3)
        course_num = match.group(4)
        course_combined = course_code + " " + course_num
        section = match.group(5)

        course_key = course_code + course_num
        catalog_course = catalog_courses.get(course_key, {})
        course_title = catalog_course.get("title", schedule_title)

        if schedule_title != course_title:
            section_name = schedule_title
        else:
            section_name = ""

        course_url = link.get("href", "")
        if course_url.startswith("/"):
            course_url = "https://ssb.iit.edu" + course_url

        heading_row = heading.find_parent("tr")

        info_row = heading_row.find_next_sibling("tr")
        if info_row is None:
            continue
        info_cell = info_row.find("td")
        if info_cell is None:
            continue

        text = info_cell.get_text("\n", strip=True)

        notes = ""
        note_tag = info_cell.find("b", string=lambda s: s and s.strip() == "NOTE:")

        if note_tag:
            note_parts = []

            for element in note_tag.next_siblings:
                if getattr(element, "name", None) == "br":
                    break
                if hasattr(element, "get_text"):
                    note_parts.append(element.get_text(" ", strip=True))
                else:
                    note_parts.append(str(element).strip())

            notes = clean_text(" ".join(note_parts))

        associated_term = get_labeled_value(text, "Associated Term")
        registration_dates = get_labeled_value(text, "Registration Dates")
        levels = get_labeled_value(text, "Levels")
        attributes = get_labeled_value(text, "Attributes")
        credits_match = re.search(r"([\d.]+)\s+Credits", text)
        credits = float(credits_match.group(1)) if credits_match else None
        schedule_type = ""
        instructional_method = ""

        schedule_type_match = re.search(r"([\w/]+(?:\s[\w/]+)*)\s+Schedule Type", text)
        schedule_type = schedule_type_match.group(1) if schedule_type_match else ""

        instructional_method_match = re.search(r"([\w/]+(?:\s[\w/]+)*)\s+Instructional Method", text)
        instructional_method = instructional_method_match.group(1) if instructional_method_match else ""

        catalog_entry_url = ""
        catalog_link = info_cell.find(
            "a",
            string=lambda s: s and "View Catalog Entry" in s
        )

        if catalog_link:
            catalog_entry_url = catalog_link.get("href", "")
            if catalog_entry_url.startswith("/"):
                catalog_entry_url = "https://ssb.iit.edu" + catalog_entry_url

        meeting_table = info_cell.find(
            "table",
            class_="datadisplaytable"
        )

        meetings = []
        if meeting_table:
            rows = meeting_table.find_all("tr")

            for row in rows[1:]:
                cells = row.find_all("td")

                if len(cells) < 7:
                    continue

                values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]

                instructor_email = ""
                email_link = cells[6].find("a", href=True)
                if email_link:
                    href = email_link["href"]

                    if href.startswith("mailto:"):
                        instructor_email = href[7:]

                instructor = re.sub(
                    r"\s*\(\s*[A-Z]\s*\)",
                    "",
                    values[6]
                ).strip()

                meetings.append({
                    "type": values[0],
                    "time": values[1],
                    "days": values[2],
                    "location": values[3],
                    "date_range": values[4],
                    "schedule_type": values[5],
                    "instructor": instructor,
                    "instructor_email": instructor_email
                })

        section_availability = availability.get(crn, {})
        learning_objectives = section_availability.get(
            "learning_objectives",
            ""
        )

        section_data = {
            "section": section,
            "section_name": section_name,
            "crn": crn,
            "section_url": course_url,
            "credits": credits,
            "schedule_type": schedule_type,
            "instructional_method": instructional_method,
            "associated_term": associated_term,
            "registration_dates": registration_dates,
            "levels": levels,
            "attributes": attributes,
            "notes": notes,
            "meetings": meetings,
            "availability": {
                "capacity": section_availability.get("capacity"),
                "actual": section_availability.get("actual"),
                "remaining": section_availability.get("remaining"),
                "waitlist_capacity": section_availability.get("waitlist_capacity"),
                "waitlist_actual": section_availability.get("waitlist_actual"),
                "waitlist_remaining": section_availability.get("waitlist_remaining")
            },
            "restrictions": section_availability.get("restrictions", ""),
            "prerequisites": section_availability.get("prerequisites", ""),
            "general_requirements": section_availability.get("general_requirements", "")
        }

        if course_key not in courses:
            courses[course_key] = {
                "course_code": course_code,
                "course_num": course_num,
                "course_combined": course_combined,
                "title": course_title,
                "catalog_entry_url": catalog_course.get("catalog_entry_url", catalog_entry_url),
                "course_description": catalog_course.get("course_description", ""),
                "learning_objectives": learning_objectives,
                "catalog_syllabus_url": catalog_course.get("catalog_syllabus_url", ""),
                "catalog_restrictions": catalog_course.get("catalog_restrictions", ""),
                "mutual_exclusions": catalog_course.get("mutual_exclusions", ""),
                "sections": []
            }
        courses[course_key]["sections"].append(section_data)

    output = {
        "term": semester,
        "courses": list(courses.values())
    }

    output_dir = os.path.join(OUTPUT_DIR, semester)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, department + ".json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("Created", output_path)

for semester in os.listdir(CACHE_DIR):
    schedule_dir = os.path.join(CACHE_DIR, semester, "schedule")
    if not os.path.isdir(schedule_dir):
        continue

    for filename in os.listdir(schedule_dir):
        if not filename.endswith(".html"):
            continue
        department = filename[:-len(".html")]
        process_department(semester, department)

print("done")