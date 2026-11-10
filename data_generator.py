"""
data_generator.py
-----------------
Creates the SIMULATED datasets used by the Library Circulation and Demand
Dashboard.  NOTHING in the generated files is a real library record.

    python data_generator.py

writes
    data/catalogue.csv  - one row per book title (book_id, category)
    data/loans.csv      - borrowing records (loan_id, student_id, book_id,
                          category, issue_date, due_date, return_date)

A fixed random seed makes the files reproducible.  A small number of
deliberately faulty rows (duplicates, blank fields, impossible dates,
unknown categories) is mixed in so that the validation code and the
data-quality analysis have something real to detect.
"""
import csv
import os
import random
from datetime import date, timedelta

SEED = 42
LOAN_PERIOD_DAYS = 14
# Academic year covered by the simulation: Aug 2025 - Jul 2026
START_YEAR, START_MONTH = 2025, 8
N_VALID_LOANS = 420
N_STUDENTS = 80

# category: (number of titles in catalogue, relative demand weight)
CATEGORIES = {
    "Computer Science": (60, 0.26),
    "Electronics": (50, 0.24),
    "Mathematics": (40, 0.16),
    "Physics": (30, 0.12),
    "Literature": (40, 0.12),
    "Management": (20, 0.10),
}
# Relative loan volume per month, Aug..Jul (peaks around exams in Dec and May)
MONTH_WEIGHTS = [0.7, 1.0, 1.1, 0.9, 1.3, 0.8, 1.0, 1.1, 1.0, 1.4, 0.9, 0.5]
EXAM_MONTH_INDEXES = (4, 9)   # Dec, May


def month_start(index):
    """Return the first day of the index-th month of the academic year."""
    month = (START_MONTH - 1 + index) % 12 + 1
    year = START_YEAR + (START_MONTH - 1 + index) // 12
    return date(year, month, 1)


def build_catalogue():
    rows, n = [], 1
    for category, (titles, _w) in CATEGORIES.items():
        for _ in range(titles):
            rows.append({"book_id": f"B{n:03d}", "category": category})
            n += 1
    return rows


def generate_loans(seed=SEED):
    rng = random.Random(seed)
    catalogue = build_catalogue()
    by_cat = {}
    for row in catalogue:
        by_cat.setdefault(row["category"], []).append(row["book_id"])

    cat_names = list(CATEGORIES)
    cat_weights = [CATEGORIES[c][1] for c in cat_names]
    # a few students borrow much more often than the rest
    students = [f"M{i:03d}" for i in range(1, N_STUDENTS + 1)]
    student_weights = [4 if i < 8 else 1 for i in range(N_STUDENTS)]
    data_end = month_start(11) + timedelta(days=30)         # 31 Jul 2026

    loans = []
    for k in range(1, N_VALID_LOANS + 1):
        m = rng.choices(range(12), weights=MONTH_WEIGHTS)[0]
        issue = month_start(m) + timedelta(days=rng.randint(0, 27))
        category = rng.choices(cat_names, weights=cat_weights)[0]
        book = rng.choice(by_cat[category])
        student = rng.choices(students, weights=student_weights)[0]
        due = issue + timedelta(days=LOAN_PERIOD_DAYS)

        extra = 2 if m in EXAM_MONTH_INDEXES else 0     # exam-time loans run longer
        days = int(round(rng.gauss(11 + extra, 4.5)))
        days = max(1, min(days, 45))
        returned = issue + timedelta(days=days)
        if issue > data_end - timedelta(days=10) and rng.random() < 0.5:
            returned = None                              # still on loan at data end
        elif returned > data_end:
            returned = None
        loans.append({
            "loan_id": f"L{k:04d}", "student_id": student, "book_id": book,
            "category": category, "issue_date": issue.isoformat(),
            "due_date": due.isoformat(),
            "return_date": returned.isoformat() if returned else "",
        })

    # ---- deliberately faulty rows -------------------------------------
    bad = []
    for row in rng.sample(loans, 8):                     # exact duplicates
        bad.append(dict(row))
    for field in ("student_id", "category", "student_id", "category"):  # incomplete
        row = dict(rng.choice(loans)); row["loan_id"] = f"X{len(bad):04d}"
        row[field] = ""
        bad.append(row)
    for _ in range(3):                                   # returned before issued
        row = dict(rng.choice(loans)); row["loan_id"] = f"X{len(bad):04d}"
        row["issue_date"] = "2026-03-20"; row["due_date"] = "2026-04-03"
        row["return_date"] = "2026-03-10"
        bad.append(row)
    for _ in range(2):                                   # impossible calendar date
        row = dict(rng.choice(loans)); row["loan_id"] = f"X{len(bad):04d}"
        row["issue_date"] = "31/02/2026"
        bad.append(row)
    for row in bad:                                      # scatter through the file
        loans.insert(rng.randint(0, len(loans)), row)
    return loans


def write_csv(path, rows, fieldnames):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    write_csv("data/catalogue.csv", build_catalogue(), ["book_id", "category"])
    loans = generate_loans()
    write_csv("data/loans.csv", loans,
              ["loan_id", "student_id", "book_id", "category",
               "issue_date", "due_date", "return_date"])
    print(f"Wrote data/catalogue.csv and data/loans.csv ({len(loans)} loan rows, simulated)")
