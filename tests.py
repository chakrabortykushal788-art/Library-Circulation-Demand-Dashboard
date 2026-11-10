"""
tests.py - automated checks for the Library Circulation and Demand Dashboard.

Run:  python tests.py        (or:  python -m unittest -v tests)
"""
import os
import tempfile
import unittest
from datetime import date

import numpy as np

import library_dashboard as ld


def good_row(**over):
    row = {"loan_id": "L1", "student_id": "M001", "book_id": "B001",
           "category": "Physics", "issue_date": "2026-01-10",
           "due_date": "2026-01-24", "return_date": "2026-01-20"}
    row.update(over)
    return row


class TestFunctions(unittest.TestCase):
    def test_is_overdue_returned_late(self):
        self.assertTrue(ld.is_overdue(date(2026, 1, 24), date(2026, 1, 25), date(2026, 7, 31)))

    def test_is_overdue_returned_on_due_date_is_not_overdue(self):
        self.assertFalse(ld.is_overdue(date(2026, 1, 24), date(2026, 1, 24), date(2026, 7, 31)))

    def test_is_overdue_unreturned_uses_reference_date(self):
        self.assertTrue(ld.is_overdue(date(2026, 7, 1), None, date(2026, 7, 31)))
        self.assertFalse(ld.is_overdue(date(2026, 8, 1), None, date(2026, 7, 31)))

    def test_grace_period(self):
        due, ret = date(2026, 1, 24), date(2026, 1, 28)       # 4 days late
        self.assertTrue(ld.is_overdue(due, ret, date(2026, 7, 31), grace_days=0))
        self.assertFalse(ld.is_overdue(due, ret, date(2026, 7, 31), grace_days=7))

    def test_parse_date_rejects_impossible_date(self):
        with self.assertRaises(ValueError):
            ld.parse_date("31/02/2026")

    def test_frequency_counts_sorted(self):
        self.assertEqual(list(ld.frequency_counts(["a", "b", "b", "c", "b", "a"])),
                         ["b", "a", "c"])
        self.assertEqual(len(ld.frequency_counts("aabbbc", top=2)), 2)


class TestLoanRecord(unittest.TestCase):
    def test_valid_record(self):
        rec = ld.LoanRecord.from_dict(good_row())
        self.assertEqual(rec.loan_days(), 10)
        self.assertTrue(rec.is_returned())

    def test_blank_return_date_means_still_on_loan(self):
        rec = ld.LoanRecord.from_dict(good_row(return_date=""))
        self.assertFalse(rec.is_returned())

    def test_missing_field_rejected(self):
        for field in ld.MANDATORY_FIELDS:
            with self.assertRaises(ValueError, msg=field):
                ld.LoanRecord.from_dict(good_row(**{field: " "}))

    def test_return_before_issue_rejected(self):
        with self.assertRaises(ValueError):
            ld.LoanRecord.from_dict(good_row(return_date="2026-01-01"))

    def test_due_before_issue_rejected(self):
        with self.assertRaises(ValueError):
            ld.LoanRecord.from_dict(good_row(due_date="2026-01-01"))

    def test_special_methods(self):
        a = ld.LoanRecord.from_dict(good_row())
        b = ld.LoanRecord.from_dict(good_row(student_id="M002"))      # same loan_id
        c = ld.LoanRecord.from_dict(good_row(loan_id="L2", issue_date="2026-02-01",
                                             due_date="2026-02-15", return_date="2026-02-05"))
        self.assertEqual(a, b)                      # __eq__ by loan_id
        self.assertEqual(len({a, b, c}), 2)         # __hash__
        self.assertLess(a, c)                       # __lt__ by issue date
        self.assertIn("L1", repr(a))                # __repr__


class TestCollection(unittest.TestCase):
    def setUp(self):
        rows = [good_row(loan_id=f"L{i}", return_date=f"2026-01-{10 + i:02d}")
                for i in range(1, 6)]
        rows.append(good_row(loan_id="L9", return_date=""))            # still out
        self.col = ld.LoanCollection(ld.LoanRecord.from_dict(r) for r in rows)

    def test_len_getitem_iter(self):
        self.assertEqual(len(self.col), 6)
        self.assertEqual(self.col[0].loan_id, "L1")
        self.assertIsInstance(self.col[1:3], ld.LoanCollection)
        self.assertEqual(len(self.col[1:3]), 2)
        self.assertEqual(sum(1 for _ in self.col), 6)

    def test_durations_numpy(self):
        d = self.col.durations(returned_only=True)
        self.assertIsInstance(d, np.ndarray)
        self.assertEqual(d.tolist(), [1, 2, 3, 4, 5])

    def test_dataframe_columns(self):
        df = self.col.to_dataframe()
        for col in ("loan_days", "days_late", "overdue", "returned", "month"):
            self.assertIn(col, df.columns)
        self.assertEqual(int((~df["returned"]).sum()), 1)


class TestValidationAndCsv(unittest.TestCase):
    def test_validate_rows_flags_each_problem(self):
        rows = [good_row(loan_id="A"),
                good_row(loan_id="A"),                                  # duplicate
                good_row(loan_id="B", student_id=""),                   # missing
                good_row(loan_id="C", issue_date="31/02/2026"),         # bad date
                good_row(loan_id="D", return_date="2026-01-01"),        # return < issue
                good_row(loan_id="E", category="Astrology"),            # unknown
                good_row(loan_id="F")]                                  # fine
        recs, rej = ld.validate_rows(rows, known_categories={"Physics"})
        self.assertEqual([r.loan_id for r in recs], ["A", "F"])
        self.assertEqual([r["reason"].split(":")[0] for r in rej],
                         ["duplicate loan_id", "missing field", "invalid date format",
                          "return date before issue date", "unknown category"])
        self.assertEqual(rej[0]["line"], 3)                             # header is line 1

    def test_read_csv_rejects_missing_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.csv")
            with open(path, "w") as fh:
                fh.write("loan_id,student_id\nL1,M1\n")
            with self.assertRaises(ValueError):
                ld.read_csv_rows(path)


class TestAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.result = ld.run("data/loans.csv", "data/catalogue.csv", cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_row_accounting(self):
        r = self.result["rows"]
        self.assertEqual(r["input"], r["valid"] + r["rejected"])
        self.assertEqual(sum(r["rejected_by_reason"].values()), r["rejected"])

    def test_category_totals_match_valid_records(self):
        total = sum(v["loans"] for v in self.result["category_summary"].values())
        self.assertEqual(total, self.result["rows"]["valid"])

    def test_monthly_totals_match_valid_records(self):
        self.assertEqual(sum(self.result["monthly_loans"].values()),
                         self.result["rows"]["valid"])

    def test_moving_average_length(self):
        self.assertEqual(len(ld.moving_average(np.arange(12), 3)), 10)
        self.assertAlmostEqual(ld.moving_average([3, 6, 9], 3)[0], 6.0)

    def test_outputs_created(self):
        for name in ("fig1_monthly_trend.png", "fig2_category_demand.png",
                     "fig3_loan_durations.png", "fig4_evaluation.png",
                     "summary.json", "category_summary.csv", "rejected_rows.csv"):
            self.assertTrue(os.path.exists(os.path.join(self.tmp.name, name)), name)

    def test_grace_period_reduces_overdue_rate(self):
        o = self.result["overdue_rule_overall"]
        self.assertLess(o["overdue_pct_grace7"], o["overdue_pct_grace0"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
