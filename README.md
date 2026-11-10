# Library Circulation and Demand Dashboard

**Course:** B.Tech ECE (Section A), Python Programming Laboratory (end-semester project) - Institute of Engineering & Management, Kolkata
**Submitted to:** Prof. Indranil Basu
**Topic:** Library circulation and demand dashboard
**Report:** `Project_Report.pdf`

A Python program that analyses the borrowing records of a campus library: it validates the
records, finds high-demand book categories, checks duplicated and incomplete records, compares
alternative definitions of "demand" and "overdue", draws plots and exports JSON/CSV summaries.

> **Important - simulated data.** `data/loans.csv` and `data/catalogue.csv` are produced by
> `data_generator.py` (fixed random seed 42). They are **not** real library records. Results
> demonstrate the program, not real student behaviour.

## Team and individual contributions

| Name | Roll no. | Contribution |
|------|----------|--------------|
| Kushal Chakraborty | 58 | Individual project: design, coding, data generation, testing, analysis and report |

## How to run

1. Install Python 3.9 or newer.
2. Install the libraries: `pip install -r requirements.txt`
   (Windows: `py -m pip install -r requirements.txt`)
3. *(Optional - the data files are already included)* regenerate the data: `python data_generator.py`
4. Run the analysis: `python library_dashboard.py`
   - add `--show` to open the plot windows
   - other options: `--data`, `--catalogue`, `--out` (see `python library_dashboard.py --help`)
5. Run the tests: `python tests.py`

Results are written to the `outputs/` folder.

## Files

| File | Purpose |
|------|---------|
| `library_dashboard.py` | Main program: validation, classes, NumPy/Pandas analysis, plots, exports |
| `data_generator.py` | Creates the simulated catalogue and loan records (with deliberate faults) |
| `tests.py` | 23 automated unit tests |
| `data/loans.csv` | 437 simulated loan rows (420 valid + 17 faulty) |
| `data/catalogue.csv` | 240 book titles in 6 categories |
| `outputs/fig1_monthly_trend.png` | Monthly loans with 3-month moving average |
| `outputs/fig2_category_demand.png` | Loans and overdue rate per category |
| `outputs/fig3_loan_durations.png` | Distribution of loan lengths |
| `outputs/fig4_evaluation.png` | Effect of cleaning and loans-per-title comparison |
| `outputs/summary.json`, `category_summary.csv`, `rejected_rows.csv` | Exported summaries |
| `outputs/console_output.txt`, `test_results.txt` | Saved program and test output |
| `Project_Report.pdf` | Project report |

## CSV format

`loans.csv` columns: `loan_id, student_id, book_id, category, issue_date, due_date, return_date`
(dates as `YYYY-MM-DD`; a blank `return_date` means the book is still on loan).
`catalogue.csv` columns: `book_id, category`. Student IDs are anonymised.

## Course outcomes covered

| Outcome | Where |
|---------|-------|
| CO1 functions and control flow | `is_overdue`, `parse_date`, `frequency_counts`, `validate_rows` |
| CO2 data structures and file I/O | dicts, lists, sets, `Counter`, `csv` module, `json` module |
| CO3 classes and special methods | `LoanRecord` (`__init__`, `__repr__`, `__eq__`, `__hash__`, `__lt__`), `LoanCollection` (`__len__`, `__getitem__`, `__iter__`, `__contains__`) |
| CO4 NumPy | loan-duration arrays, mean/median/SD/percentile, moving average |
| CO5 Pandas, CSV/JSON | group-by category/month summaries, JSON and CSV export |
| CO6 Matplotlib and interpretation | four labelled figures and an automatic written interpretation |

## Method in brief

- **Validation:** a row is rejected if a mandatory field is blank, a date is impossible, the return
  or due date is before the issue date, the category is not in the catalogue, or the `loan_id` is a duplicate.
- **Overdue rule:** a loan is overdue if returned (or, if still out, held at 31 Jul 2026) after its due date.
- **Evaluation (BL5):** (A) rankings from raw rows vs cleaned records, (B) demand as loan count vs
  loans per catalogue title, (C) overdue rate with 0-day vs 7-day grace period.
- **Limits:** the data are synthetic, one library, one academic year; demand is not the same as
  need, and per-title demand uses catalogue size, not number of physical copies.
