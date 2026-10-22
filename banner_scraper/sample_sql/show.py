import sqlite3
import sys
import textwrap

DB_PATH = "../advising.db"
WIDTH = 100

sql_path = sys.argv[1] if len(sys.argv) > 1 else "query.sql"
with open(sql_path, "r", encoding="utf-8") as file:
    sql = file.read()

connection = sqlite3.connect("file:" + DB_PATH + "?mode=ro", uri=True)
cursor = connection.execute(sql)
columns = [column[0] for column in cursor.description]
rows = cursor.fetchall()
label_width = max(len(column) for column in columns)

for number, row in enumerate(rows, start=1):
    print("--- row %d of %d ---" % (number, len(rows)))
    for column, value in zip(columns, row):
        text = "" if value is None else str(value)
        prefix = column.ljust(label_width) + " : "
        if text:
            print(textwrap.fill(text, WIDTH, initial_indent=prefix,
                                subsequent_indent=" " * len(prefix)))
        else:
            print(prefix + "-")
    print()