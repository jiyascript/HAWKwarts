import json
import os
import re

DATA_DIR = "data"
DATA_DIR2 = "cleaned_data"

def load_semester_courses(semester):
    semester_dir = os.path.join(DATA_DIR, semester)
    semester2_dir = os.path.join(DATA_DIR2, semester)
    os.makedirs(semester2_dir, exist_ok = True)

    all_courses = []

    print("Searching:", semester_dir)
    print("Exists:", os.path.exists(semester_dir))

    for files in os.listdir(semester_dir):
        print("Found:", files)
        if not files.endswith(".json"):
            continue

        path = os.path.join(semester_dir, files)
        with open(path, "r", encoding="utf-8") as file:
            department_data = json.load(file)

        print("# of courses:", len(department_data.get("courses", [])))
        all_courses.extend(department_data["courses"])
    return all_courses

def split_location(location):
    parts = location.rsplit(" ", 1)
    if len(parts) == 2 and any(char.isdigit() for char in parts[1]):
        return parts[0], parts[1]
    return location, ""

DAY_ORDER = "MTWRFSU"

def merge_meetings(meetings):
    merged = {}
    for meeting in meetings:
        key = (
            meeting["type"],
            meeting["time"],
            meeting["location"],
            meeting["schedule_type"],
            tuple(i["email"] or i["name"] for i in meeting["instructors"]),
        )
        if key not in merged:
            merged[key] = dict(meeting)
        else:
            days = merged[key]["days"] + meeting["days"]
            merged[key]["days"] = "".join(sorted(set(days), key=DAY_ORDER.find))
    return list(merged.values())

def parse_days(days):
    if days and all(letter in DAY_ORDER for letter in days):
        return list(days)
    return []

def build_relational(semester, courses):
    course_rows = []
    offering_rows = []
    section_rows = []
    meeting_rows = []
    meeting_instructor_rows = []
    professors = {}

    for course in courses:
        course_id = course["course_combined"]
        offering_id = semester + ":" + course_id

        course_rows.append({
            "course_id": course_id,
            "subject_code": course["course_code"],
            "course_num": course["course_num"],
            "title": course["title"],
        })

        offering_rows.append({
            "offering_id": offering_id,
            "course_id": course_id,
            "term": semester,
            "course_description": course["course_description"],
            "learning_objectives": course["learning_objectives"],
            "catalog_entry_url": course["catalog_entry_url"],
            "catalog_syllabus_url": course["catalog_syllabus_url"],
            "levels": course["levels"],
            "attributes": course["attributes"],
            "restrictions": course["restrictions"],
            "prerequisites": course["prerequisites"],
            "general_requirements": course["general_requirements"],
            "mutual_exclusions": course["mutual_exclusions"],
        })

        for section in course["sections"]:
            crn = section["crn"]
            section_id = semester + ":" + crn 
            availability = section["availability"]

            section_rows.append({
                "section_id": section_id,
                "offering_id": offering_id,  
                "crn": crn,
                "section": section["section"],
                "section_name": section["section_name"],
                "section_url": section["section_url"],
                "credits": section["credits"],
                "schedule_type": section["schedule_type"],
                "campus": section["campus"],
                "notes": section["notes"],
                "capacity": availability.get("capacity"),
                "actual": availability.get("actual"),
                "remaining": availability.get("remaining"),
                "waitlist_capacity": availability.get("waitlist_capacity"),
                "waitlist_actual": availability.get("waitlist_actual"),
                "waitlist_remaining": availability.get("waitlist_remaining"),
            })

            for number, meeting in enumerate(merge_meetings(section["meetings"]), start=1):
            # for number, meeting in enumerate(section["meetings"], start=1):
                meeting_id = section_id + ":" + str(number)
                building, room = split_location(meeting["location"])

                meeting_rows.append({
                    "meeting_id": meeting_id,
                    "section_id": section_id,
                    "type": meeting["type"],
                    "schedule_type": meeting["schedule_type"],
                    "days": meeting["days"],
                    "time": meeting["time"],
                    "location": meeting["location"],
                    "building": building,
                    "room": room,
                })

                for instructor in meeting["instructors"]:
                    if instructor["name"].upper().startswith("TBA"):
                        continue

                    professor_id = instructor["email"] or "name:" + instructor["name"].lower()

                    if professor_id not in professors:
                        professors[professor_id] = {
                            "professor_id": professor_id,
                            "name": instructor["name"],
                            "email": instructor["email"] or None,
                        }

                    meeting_instructor_rows.append({
                        "meeting_id": meeting_id,
                        "professor_id": professor_id,
                        "is_primary": instructor["primary"],
                    })

    return {
        "courses": course_rows,
        "course_offerings": offering_rows,
        "sections": section_rows,
        "meetings": meeting_rows,
        "meeting_instructors": meeting_instructor_rows,
        "professors": list(professors.values()),
    }

VECTOR_FIELDS = [
    ("course_description", "Course Description"),
    ("learning_objectives", "Learning Objectives"),
    ("prerequisites", "Prerequisites"),
    ("general_requirements", "General Requirements"),
    ("restrictions", "Restrictions"),
]

def build_vector(semester, courses):
    records = []

    for course in courses:
        course_id = course["course_combined"]

        for field_key, field_label in VECTOR_FIELDS:
            text = course.get(field_key, "")
            if not text:
                continue

            records.append({
                "id": "%s:%s" % (course_id, field_key),
                "term": semester,
                "course_id": course_id,
                "title": course["title"],
                "field": field_label,
                "text": text,
            })

        for section in course["sections"]:
            if not section["notes"]:
                continue
            records.append({
                "id": "%s:section:%s:notes" % (course_id, section["crn"]),
                "term": semester,
                "course_id": course_id,
                "title": course["title"],
                "crn": section["crn"],
                "field": "Section Notes",
                "text": section["notes"],
            })

    return records

def build_scheduling(semester, courses):
    scheduling_courses = []

    for course in courses:
        if not course["sections"]:
            continue 

        sections = []
        for section in course["sections"]:
            meetings = []
            for meeting in merge_meetings(section["meetings"]):
                building, room = split_location(meeting["location"])
                meetings.append({
                    "type": meeting["type"],
                    "days": parse_days(meeting["days"]),
                    # "start_minutes": start,
                    # "end_minutes": end,
                    "time": meeting["time"],
                    "building": building,
                    "room": room,
                    "instructors": [i for i in meeting["instructors"]
                                    if not i["name"].upper().startswith("TBA")],
                })

            sections.append({
                "section_id": semester + ":" + section["crn"],
                "crn": section["crn"],
                "section": section["section"],
                "section_name": section["section_name"],
                "credits": section["credits"],
                "schedule_type": section["schedule_type"],
                "campus": section["campus"],
                "notes": section["notes"],
                "meetings": meetings,
                "availability": section["availability"],
            })

        scheduling_courses.append({
            "course_id": course["course_combined"],
            "title": course["title"],
            "levels": course["levels"],
            "attributes": course["attributes"],
            "restrictions": course["restrictions"],
            "prerequisites": course["prerequisites"],
            "general_requirements": course["general_requirements"],
            "mutual_exclusions": course["mutual_exclusions"],
            "sections": sections,
        })

    scheduling_courses.sort(key=lambda course: course["course_id"])
    return {"term": semester, "courses": scheduling_courses}

def build_databases(semester):
    courses = load_semester_courses(semester)
    relational = build_relational(semester, courses)
    vector = build_vector(semester, courses)

    semester_dir = os.path.join(DATA_DIR2, semester)
    print("")

    for table_name, rows in relational.items():
        path = os.path.join(semester_dir, "r_" + table_name + ".json") # r for relational
        with open(path, "w", encoding="utf-8") as file:
            json.dump(rows, file, indent=2, ensure_ascii=False)
        print("Created", path)

    vector_path = os.path.join(semester_dir, "vector.json")
    with open(vector_path, "w", encoding="utf-8") as file:
        json.dump(vector, file, indent=2, ensure_ascii=False)
    print("Created", vector_path)

    scheduling_path = os.path.join(semester_dir, "scheduling.json")
    with open(scheduling_path, "w", encoding="utf-8") as file:
        json.dump(build_scheduling(semester, courses), file, indent=2, ensure_ascii=False)
    print("Created", scheduling_path)

if __name__ == "__main__":
    semester = "Fall 2026" # adjust semester here 
    build_databases(semester)
    
    # can also do multiple semesters like this
    # for semester in ["Spring 2026", "Fall 2026"]: 
        # build_databases(semester)

