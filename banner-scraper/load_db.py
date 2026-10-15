import json
import os
import sqlite3

DATA_DIR2 = "cleaned_data"
DB_PATH = "advising.db"

SCHEMA = """
CREATE TABLE courses (
    course_id TEXT PRIMARY KEY,
    subject_code TEXT,
    course_num TEXT,
    title TEXT
);

CREATE TABLE professors (
    professor_id TEXT PRIMARY KEY,
    name TEXT,
    email TEXT
);

CREATE TABLE course_offerings (
    offering_id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    term TEXT,
    course_description TEXT,
    learning_objectives TEXT,
    catalog_entry_url TEXT,
    catalog_syllabus_url TEXT,
    levels TEXT,
    attributes TEXT,
    restrictions TEXT,
    prerequisites TEXT,
    general_requirements TEXT,
    mutual_exclusions TEXT
);

CREATE TABLE sections (
    section_id TEXT PRIMARY KEY,
    offering_id TEXT NOT NULL REFERENCES course_offerings(offering_id),
    crn TEXT,
    section TEXT,
    section_name TEXT,
    section_url TEXT,
    credits REAL,
    schedule_type TEXT,
    campus TEXT,
    notes TEXT,
    capacity INTEGER,
    actual INTEGER,
    remaining INTEGER,
    waitlist_capacity INTEGER,
    waitlist_actual INTEGER,
    waitlist_remaining INTEGER
);

CREATE TABLE meetings (
    meeting_id TEXT PRIMARY KEY,
    section_id TEXT NOT NULL REFERENCES sections(section_id),
    type TEXT,
    schedule_type TEXT,
    days TEXT,
    time TEXT,
    location TEXT,
    building TEXT,
    room TEXT
);

CREATE TABLE meeting_instructors (
    meeting_id TEXT NOT NULL REFERENCES meetings(meeting_id),
    professor_id TEXT NOT NULL REFERENCES professors(professor_id),
    is_primary INTEGER,
    PRIMARY KEY (meeting_id, professor_id)
);
"""

TABLE_ORDER = ["courses", "professors", "course_offerings", "sections", "meetings", "meeting_instructors"]
REPEATING_TABLES = ("courses", "professors")

def load_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)

    for semester in os.listdir(DATA_DIR2):
        semester_dir = os.path.join(DATA_DIR2, semester)
        if not os.path.isdir(semester_dir):
            continue

        for table in TABLE_ORDER:
            path = os.path.join(semester_dir, "r_" + table + ".json")
            with open(path, "r", encoding="utf-8") as file:
                rows = json.load(file)
            if not rows:
                continue

            columns = list(rows[0].keys())
            verb = "INSERT OR IGNORE" if table in REPEATING_TABLES else "INSERT"
            sql = "%s INTO %s (%s) VALUES (%s)" % (
                verb, table, ", ".join(columns), ", ".join("?" * len(columns)))
            connection.executemany(sql, [[row[column] for column in columns] for row in rows])

        print("Loaded", semester)

    connection.commit()
    connection.close()

if __name__ == "__main__":
    load_database()