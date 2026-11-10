"""
library_dashboard.py
====================
Library Circulation and Demand Dashboard  (Python Programming Laboratory)

Analyses borrowing records of a campus library: validates the records,
summarises demand by book category and by month, checks duplicated and
incomplete records, evaluates alternative definitions of "demand" and
"overdue", draws plots and exports JSON/CSV summaries.

Run:
    python data_generator.py            # creates the SIMULATED data (once)
    python library_dashboard.py         # runs the full analysis
    python library_dashboard.py --show  # also opens the plot windows

Course outcomes covered
    CO1  functions and control flow ......... is_overdue, parse_date, frequency_counts, validate_rows
    CO2  data structures and file I/O ....... dicts, lists, sets, Counter, csv, json
    CO3  classes and special methods ........ LoanRecord, LoanCollection
    CO4  NumPy .............................. durations, percentiles, moving average
    CO5  Pandas and CSV/JSON ................ group-by summaries, JSON export
    CO6  Matplotlib and interpretation ...... four labelled figures + written interpretation
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import date, datetime

import matplotlib
if "--show" not in sys.argv:
    matplotlib.use("Agg")           # draw to files only, no window needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATE_FORMAT = "%Y-%m-%d"
# Fixed "today" for the simulated data set (last day covered by the data), so
# that results are reproducible and do not change with the computer's clock.
REFERENCE_DATE = date(2026, 7, 31)
REQUIRED_COLUMNS = ["loan_id", "student_id", "book_id", "category",
                    "issue_date", "due_date", "return_date"]
MANDATORY_FIELDS = ["loan_id", "student_id", "book_id", "category",
                    "issue_date", "due_date"]          # return_date may be blank


# ----------------------------------------------------------------------
# CO1  Functions and control flow
# ----------------------------------------------------------------------
def parse_date(text):
    """Convert 'YYYY-MM-DD' text to a date; raise ValueError if impossible."""
    return datetime.strptime(text.strip(), DATE_FORMAT).date()


def is_overdue(due, returned, reference, grace_days=0):
    """
    Overdue check.  A loan is overdue if it was returned (or, if it is still
    out, is being held at the reference date) more than `grace_days` after
    its due date.
    """
    end = returned if returned is not None else reference
    return (end - due).days > grace_days


def frequency_counts(items, top=None):
    """Return a {item: count} dict sorted from most to least frequent."""
    counts = Counter(items)
    ordered = counts.most_common(top)
    return dict(ordered)


# ----------------------------------------------------------------------
# CO3  Classes and special methods
# ----------------------------------------------------------------------
class LoanRecord:
    """
    One borrowing event, validated on construction.

    Special methods and why they are used
      __init__ : validates fields so an invalid record can never exist
      __repr__ : readable output when printing / debugging records
      __eq__ / __hash__ : two records are the same loan if loan_id matches,
                  which lets sets and dicts detect duplicates directly
      __lt__   : records sort naturally by issue date, so sorted(records)
                  gives a chronological list
    """

    def __init__(self, loan_id, student_id, book_id, category,
                 issue_date, due_date, return_date=None):
        for name, value in (("loan_id", loan_id), ("student_id", student_id),
                            ("book_id", book_id), ("category", category)):
            if not str(value).strip():
                raise ValueError(f"missing field: {name}")
        if due_date < issue_date:
            raise ValueError("due date before issue date")
        if return_date is not None and return_date < issue_date:
            raise ValueError("return date before issue date")
        self.loan_id = str(loan_id).strip()
        self.student_id = str(student_id).strip()
        self.book_id = str(book_id).strip()
        self.category = str(category).strip()
        self.issue_date = issue_date
        self.due_date = due_date
        self.return_date = return_date

    @classmethod
    def from_dict(cls, row):
        """Build a record from a CSV row (dict of text); raise ValueError if bad."""
        for field in MANDATORY_FIELDS:
            if not (row.get(field) or "").strip():
                raise ValueError(f"missing field: {field}")
        try:
            issue = parse_date(row["issue_date"])
            due = parse_date(row["due_date"])
            ret_text = (row.get("return_date") or "").strip()
            returned = parse_date(ret_text) if ret_text else None
        except ValueError:
            raise ValueError("invalid date format")
        return cls(row["loan_id"], row["student_id"], row["book_id"],
                   row["category"], issue, due, returned)

    def is_returned(self):
        return self.return_date is not None

    def loan_days(self, reference=REFERENCE_DATE):
        end = self.return_date if self.return_date else reference
        return (end - self.issue_date).days

    def overdue(self, reference=REFERENCE_DATE, grace_days=0):
        return is_overdue(self.due_date, self.return_date, reference, grace_days)

    def to_dict(self):
        return {"loan_id": self.loan_id, "student_id": self.student_id,
                "book_id": self.book_id, "category": self.category,
                "issue_date": self.issue_date, "due_date": self.due_date,
                "return_date": self.return_date}

    def __repr__(self):
        return (f"LoanRecord({self.loan_id}, {self.student_id}, {self.book_id}, "
                f"{self.category}, issued {self.issue_date})")

    def __eq__(self, other):
        return isinstance(other, LoanRecord) and self.loan_id == other.loan_id

    def __hash__(self):
        return hash(self.loan_id)

    def __lt__(self, other):
        return self.issue_date < other.issue_date


class LoanCollection:
    """
    A container of LoanRecord objects that behaves like a read-only list.

      __len__     : len(collection) gives the number of loans
      __getitem__ : collection[3] or collection[:10] (slices give a new collection)
      __iter__    : lets 'for loan in collection' and pandas/NumPy conversion work
      __contains__: 'record in collection' uses the loan_id based equality
    """

    def __init__(self, records=()):
        self._records = list(records)

    def __len__(self):
        return len(self._records)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return LoanCollection(self._records[index])
        return self._records[index]

    def __iter__(self):
        return iter(self._records)

    def __contains__(self, record):
        return record in self._records

    def __repr__(self):
        return f"LoanCollection({len(self)} loans)"

    # CO4: NumPy ------------------------------------------------------
    def durations(self, returned_only=True):
        """NumPy array of loan lengths in days."""
        recs = [r for r in self._records if r.is_returned() or not returned_only]
        return np.array([r.loan_days() for r in recs], dtype=float)

    # CO5: Pandas -----------------------------------------------------
    def to_dataframe(self):
        df = pd.DataFrame([r.to_dict() for r in self._records])
        for col in ("issue_date", "due_date", "return_date"):
            df[col] = pd.to_datetime(df[col])
        end = df["return_date"].fillna(pd.Timestamp(REFERENCE_DATE))
        df["returned"] = df["return_date"].notna()
        df["loan_days"] = (end - df["issue_date"]).dt.days
        df["days_late"] = (end - df["due_date"]).dt.days
        df["overdue"] = df["days_late"] > 0
        df["month"] = df["issue_date"].dt.to_period("M")
        return df


# ----------------------------------------------------------------------
# CO2  File input / output and validation
# ----------------------------------------------------------------------
def read_csv_rows(path):
    """Read a CSV file into a list of dictionaries (one per row)."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing required column(s): {', '.join(missing)}")
        return list(reader)


def load_catalogue(path):
    """Return {book_id: category} from the catalogue file ({} if absent)."""
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["book_id"]: r["category"] for r in csv.DictReader(fh)}


def validate_rows(rows, known_categories=None):
    """
    Turn raw CSV rows into LoanRecord objects.

    Returns (records, rejected) where `rejected` is a list of dicts holding
    the CSV line number, loan_id and the reason.  Rules: mandatory fields
    present, dates valid and in order, category known, loan_id unique.
    """
    records, rejected, seen_ids = [], [], set()
    for line_no, row in enumerate(rows, start=2):      # line 1 is the header
        try:
            rec = LoanRecord.from_dict(row)
            if known_categories and rec.category not in known_categories:
                raise ValueError("unknown category")
            if rec.loan_id in seen_ids:
                raise ValueError("duplicate loan_id")
        except ValueError as err:
            rejected.append({"line": line_no,
                             "loan_id": (row.get("loan_id") or "").strip(),
                             "reason": str(err)})
            continue
        seen_ids.add(rec.loan_id)
        records.append(rec)
    return records, rejected


# ----------------------------------------------------------------------
# CO4 + CO5  Analysis
# ----------------------------------------------------------------------
def duration_statistics(collection):
    """NumPy statistics of loan length for returned loans."""
    d = collection.durations(returned_only=True)
    return {"returned_loans": int(d.size),
            "mean_days": float(np.mean(d)), "median_days": float(np.median(d)),
            "std_days": float(np.std(d, ddof=1)),
            "p90_days": float(np.percentile(d, 90)),
            "max_days": float(np.max(d))}


def monthly_counts(df):
    """Loans issued per month, including months with zero loans."""
    counts = df.groupby("month").size()
    full = pd.period_range(counts.index.min(), counts.index.max(), freq="M")
    return counts.reindex(full, fill_value=0)


def moving_average(values, window=3):
    """Simple moving average using NumPy convolution ('valid' part only)."""
    kernel = np.ones(window) / window
    return np.convolve(np.asarray(values, dtype=float), kernel, mode="valid")


def category_summary(df, catalogue):
    """Demand and behaviour per book category (Pandas group-by)."""
    summary = df.groupby("category").agg(
        loans=("loan_id", "count"),
        borrowers=("student_id", "nunique"),
        overdue_rate_pct=("overdue", lambda s: 100 * s.mean()))
    summary["mean_days_returned"] = (df[df["returned"]]
                                     .groupby("category")["loan_days"].mean())
    summary["share_pct"] = 100 * summary["loans"] / summary["loans"].sum()
    if catalogue:
        titles = pd.Series(Counter(catalogue.values()))
        summary["titles"] = titles
        summary["loans_per_title"] = summary["loans"] / summary["titles"]
    return summary.sort_values("loans", ascending=False)


def evaluate(df, summary, raw_rows, known_categories):
    """
    BL5 evaluation: compare alternatives and report whether conclusions change.
      A. Raw (uncleaned) loan counts vs cleaned counts per category
      B. Demand as raw loan count vs loans per catalogue title
      C. Overdue rule: due date as stored (0 days grace) vs 7 days grace
    """
    raw_counts = Counter(r["category"] for r in raw_rows
                         if r.get("category") in known_categories)
    ev = pd.DataFrame({"raw_loans": pd.Series(raw_counts),
                       "clean_loans": summary["loans"]}).fillna(0).astype(int)
    ev["inflation_pct"] = 100 * (ev["raw_loans"] - ev["clean_loans"]) / ev["clean_loans"]
    ev["rank_raw"] = ev["raw_loans"].rank(ascending=False, method="min").astype(int)
    ev["rank_clean"] = ev["clean_loans"].rank(ascending=False, method="min").astype(int)
    if "loans_per_title" in summary:
        ev["loans_per_title"] = summary["loans_per_title"]
        ev["rank_per_title"] = ev["loans_per_title"].rank(ascending=False,
                                                          method="min").astype(int)
    grace0 = df.groupby("category")["overdue"].mean() * 100
    grace7 = (df["days_late"] > 7).groupby(df["category"]).mean() * 100
    ev["overdue_pct_grace0"] = grace0
    ev["overdue_pct_grace7"] = grace7
    overall = {"overdue_pct_grace0": float(100 * df["overdue"].mean()),
               "overdue_pct_grace7": float(100 * (df["days_late"] > 7).mean())}
    return ev.sort_values("clean_loans", ascending=False), overall


def interpretation(stats, summary, ev, overall, peaks, n_raw, n_clean, rejected_kinds):
    """Automated written discussion (kept cautious: simulated data)."""
    top = summary.index[0]
    lines = [
        f"{n_clean} valid loans remain from {n_raw} input rows; "
        f"{n_raw - n_clean} rows were rejected "
        f"({', '.join(f'{k}: {v}' for k, v in rejected_kinds.items())}).",
        f"By raw loan count the most requested category is {top} "
        f"({summary.loc[top, 'loans']} loans, {summary.loc[top, 'share_pct']:.1f}% of loans).",
    ]
    if "rank_per_title" in ev:
        top_pt = ev["loans_per_title"].idxmax()
        lines.append(
            f"Per catalogue title, {top_pt} is busiest "
            f"({ev.loc[top_pt, 'loans_per_title']:.2f} loans per title), so the "
            f"conclusion about 'high demand' depends on whether size of collection is considered.")
    lines.append(f"Loans last {stats['mean_days']:.1f} days on average "
                 f"(median {stats['median_days']:.0f}, 90th percentile {stats['p90_days']:.0f}).")
    lines.append(f"Months above mean + 1 SD of monthly loans: {', '.join(peaks) or 'none'}; "
                 f"compare them with the academic calendar (e.g. exam periods) before "
                 f"treating them as genuine demand rather than incomplete or duplicated data.")
    lines.append(f"Overdue rate is {overall['overdue_pct_grace0']:.1f}% with the stored 14-day rule "
                 f"but {overall['overdue_pct_grace7']:.1f}% if a 7-day grace period is allowed.")
    lines.append("All data are simulated; the figures demonstrate the dashboard, "
                 "not real borrowing behaviour.")
    return lines


# ----------------------------------------------------------------------
# CO6  Matplotlib figures
# ----------------------------------------------------------------------
def style_axes(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.25)


def plot_monthly_trend(monthly, path):
    labels = [p.strftime("%b %y") for p in monthly.index]
    x = np.arange(len(monthly))
    ma = moving_average(monthly.values, 3)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(x, monthly.values, color="#2e66a7", label="Loans per month")
    ax.plot(x[1:-1], ma, color="#d6604d", marker="o", linewidth=2, label="3-month moving average")
    ax.axhline(monthly.mean() + monthly.std(), color="gray", linestyle="--", linewidth=1,
               label="Mean + 1 SD (peak threshold)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    style_axes(ax, "Monthly loan volume", "Month of issue", "Number of loans")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=150)
    return fig


def plot_categories(summary, path):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.2))
    cats = summary.index.tolist()
    bars = a1.barh(cats[::-1], summary["loans"][::-1], color="#2e66a7")
    a1.bar_label(bars, padding=2, fontsize=8); a1.margins(x=0.12)
    style_axes(a1, "Loans by category", "Number of loans", "")
    bars2 = a2.barh(cats[::-1], summary["overdue_rate_pct"][::-1], color="#d6604d")
    a2.bar_label(bars2, fmt="%.1f%%", padding=2, fontsize=8); a2.margins(x=0.15)
    style_axes(a2, "Overdue rate by category", "Loans overdue (%)", "")
    a2.set_yticklabels([])
    fig.suptitle("Demand and overdue rate by book category", fontweight="bold")
    fig.tight_layout(); fig.savefig(path, dpi=150)
    return fig


def plot_durations(collection, path):
    d = collection.durations(returned_only=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(d, bins=np.arange(0, d.max() + 3, 2), color="#2e66a7", edgecolor="white")
    ax.axvline(d.mean(), color="#d6604d", linestyle="--", label=f"Mean {d.mean():.1f} d")
    ax.axvline(np.median(d), color="green", linestyle=":", label=f"Median {np.median(d):.0f} d")
    ax.axvline(14, color="black", linewidth=1, label="Due after 14 d")
    style_axes(ax, "Distribution of loan lengths (returned loans)",
               "Days borrowed", "Number of loans")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=150)
    return fig


def plot_evaluation(ev, path):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.2))
    x = np.arange(len(ev)); w = 0.38
    a1.bar(x - w / 2, ev["raw_loans"], w, label="Raw rows (uncleaned)", color="#b0b8c4")
    a1.bar(x + w / 2, ev["clean_loans"], w, label="Cleaned records", color="#2e66a7")
    a1.set_xticks(x); a1.set_xticklabels(ev.index, rotation=30, ha="right", fontsize=8)
    style_axes(a1, "Effect of cleaning", "", "Number of loans")
    a1.legend(fontsize=8)
    if "loans_per_title" in ev:
        order = ev.sort_values("loans_per_title", ascending=False)
        bars = a2.bar(order.index, order["loans_per_title"], color="#4d9a6c")
        a2.bar_label(bars, fmt="%.2f", fontsize=8, padding=2)
        a2.set_xticks(range(len(order)))
        a2.set_xticklabels(order.index, rotation=30, ha="right", fontsize=8)
        style_axes(a2, "Demand per catalogue title", "", "Loans per title")
    fig.suptitle("Evaluating data quality and the definition of demand",
                 fontweight="bold")
    fig.tight_layout(); fig.savefig(path, dpi=150)
    return fig


# ----------------------------------------------------------------------
# Main program
# ----------------------------------------------------------------------
def run(data_path, catalogue_path, out_dir, show=False):
    os.makedirs(out_dir, exist_ok=True)
    catalogue = load_catalogue(catalogue_path)
    known = set(catalogue.values()) or None

    raw_rows = read_csv_rows(data_path)
    records, rejected = validate_rows(raw_rows, known)
    collection = LoanCollection(sorted(records))            # uses __lt__
    df = collection.to_dataframe()

    rejected_kinds = frequency_counts(r["reason"].split(":")[0] for r in rejected)
    stats = duration_statistics(collection)
    monthly = monthly_counts(df)
    summary = category_summary(df, catalogue)
    ev, overall = evaluate(df, summary, raw_rows, known or set(summary.index))
    peaks = [p.strftime("%b %Y") for p, v in monthly.items()
             if v > monthly.mean() + monthly.std()]
    top_books = frequency_counts((r.book_id for r in collection), top=5)
    top_students = frequency_counts((r.student_id for r in collection), top=5)
    still_out = int((~df["returned"]).sum())
    text = interpretation(stats, summary, ev, overall, peaks,
                          len(raw_rows), len(collection), rejected_kinds)

    # ---- console report ------------------------------------------------
    print("=" * 64)
    print(" LIBRARY CIRCULATION AND DEMAND DASHBOARD (simulated data)")
    print("=" * 64)
    print(f"Input rows: {len(raw_rows)}   Valid: {len(collection)}   Rejected: {len(rejected)}")
    for kind, n in rejected_kinds.items():
        print(f"   rejected - {kind}: {n}")
    print(f"Still on loan at {REFERENCE_DATE}: {still_out}")
    print("\nLoan length (returned loans): "
          f"mean {stats['mean_days']:.1f} d, median {stats['median_days']:.0f} d, "
          f"SD {stats['std_days']:.1f}, P90 {stats['p90_days']:.0f} d")
    print("\nCategory summary:\n", summary.round(2).to_string())
    print("\nEvaluation:\n", ev.round(2).to_string())
    print("\nMost borrowed books :", top_books)
    print("Most active borrowers:", top_students)
    print("\nInterpretation:")
    for line in text:
        print(" -", line)

    # ---- exports ---------------------------------------------------------
    summary.round(3).to_csv(os.path.join(out_dir, "category_summary.csv"))
    rejected_df = pd.DataFrame(rejected)
    rejected_df.to_csv(os.path.join(out_dir, "rejected_rows.csv"), index=False)
    export = {
        "rows": {"input": len(raw_rows), "valid": len(collection),
                 "rejected": len(rejected), "rejected_by_reason": rejected_kinds,
                 "still_on_loan": still_out},
        "loan_length_days": {k: round(v, 3) for k, v in stats.items()},
        "monthly_loans": {str(p): int(v) for p, v in monthly.items()},
        "peak_months": peaks,
        "category_summary": json.loads(summary.round(3).to_json(orient="index")),
        "evaluation": json.loads(ev.round(3).to_json(orient="index")),
        "overdue_rule_overall": {k: round(v, 3) for k, v in overall.items()},
        "top_books": top_books, "top_borrowers": top_students,
        "interpretation": text,
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(export, fh, indent=2)

    # ---- figures ---------------------------------------------------------
    plot_monthly_trend(monthly, os.path.join(out_dir, "fig1_monthly_trend.png"))
    plot_categories(summary, os.path.join(out_dir, "fig2_category_demand.png"))
    plot_durations(collection, os.path.join(out_dir, "fig3_loan_durations.png"))
    plot_evaluation(ev, os.path.join(out_dir, "fig4_evaluation.png"))
    print(f"\nSaved figures, summary.json and CSV summaries in '{out_dir}/'")
    if show:
        plt.show()
    return export


def main():
    parser = argparse.ArgumentParser(description="Library circulation and demand dashboard")
    parser.add_argument("--data", default="data/loans.csv", help="loan records CSV")
    parser.add_argument("--catalogue", default="data/catalogue.csv", help="catalogue CSV")
    parser.add_argument("--out", default="outputs", help="folder for figures and summaries")
    parser.add_argument("--show", action="store_true", help="open plot windows")
    args = parser.parse_args()
    try:
        run(args.data, args.catalogue, args.out, args.show)
    except (OSError, ValueError) as err:
        sys.exit(f"Error: {err}")


if __name__ == "__main__":
    main()
