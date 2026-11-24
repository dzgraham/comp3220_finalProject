import csv
import json
from pathlib import Path 

# Data files live in the project root, one directory above this package.
BASE_DIR = Path(__file__).resolve().parent.parent

def load_courses():
    courses = {}

    with open(BASE_DIR / "courses.csv", "r") as file:
        reader = csv.DictReader(file)

        for row in reader:
            code = row["code"]

            courses[code] = {
                "title": row["title"],
                "credits": int(row["credits"]),
                "level": int(row["level"]),
                "semesters":[
                    s.strip() for s in row["semester_offered"].split(",")
                ],
                "prerequisites": row["prerequisites_parsed"],
                "schedule": row["schedule"],
                "half": row["half"]
            }

    file.close(); 
    return courses

def load_constraints():
    with open(BASE_DIR / "constraints.json", "r") as file:
        return json.load(file)
