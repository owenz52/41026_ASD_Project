import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))
                ).resolve()
DATABASE = DATA_DIR / "enrolment.db"

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["DATA_DIR"] = str(DATA_DIR)
    if not DATABASE.exists():
        # fixed interpreter and bundled script
        subprocess.run( # noqa: S603
            [sys.executable, str(BASE_DIR / "init_db.py")],
            check=True,
        )
    with sqlite3.connect(
        DATABASE.as_uri() + "?mode=rw",
        uri=True,
    ) as connection:
        results = connection.execute("PRAGMA quick_check").fetchall()
        if results != [("ok",)]:
            raise RuntimeError(f"Database integrity check failed: {results}")
        connection.execute("""
            SELECT course_id, course_name, course_code,
                   description, availability
            FROM courses LIMIT 0
        """)
        connection.execute("""
            SELECT enrolment_id, student_id, course_id,
                   enrolment_status, enrolment_date
            FROM enrolments LIMIT 0
        """)

    print("Database validated; starting API.", flush=True)
    # Replace this process with the bundled API using a fixed argument list
    os.execv( # noqa: S606
        sys.executable,
        [sys.executable, str(BASE_DIR / "app.py")],
    )

if __name__ == "__main__":
    main()