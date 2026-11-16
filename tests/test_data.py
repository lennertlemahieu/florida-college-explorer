"""Offline contract tests use synthetic fixtures, never presented as college data."""
import json
import sys
import types
import unittest
from contextlib import contextmanager
from uuid import uuid4
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import data_api

@contextmanager
def isolated_snapshot():
    path = Path(__file__).parent / f"test_snapshot_{uuid4().hex}.json"
    try:
        with patch.object(data_api, "SNAPSHOT", path):
            yield path
    finally:
        path.unlink(missing_ok=True)
        path.with_suffix(".tmp").unlink(missing_ok=True)

def school(identifier=1, **changes):
    values = {"id": identifier, "school.name": "Synthetic test college", "school.state": "FL",
              "school.operating": 1, "school.degrees_awarded.predominant": 3,
              "latest.admissions.admission_rate.overall": .5,
              "latest.completion.completion_rate_4yr_150nt": .7}
    values.update(changes)
    return values

class Response:
    status_code = 200
    def __init__(self, rows, total):
        self.rows, self.total = rows, total
    def json(self):
        return {"results": self.rows, "metadata": {"total": self.total}}

class Session:
    def __init__(self, responses):
        self.responses, self.calls = iter(responses), []
    def get(self, url, params, timeout):
        self.calls.append(params)
        return next(self.responses)

class DataTests(unittest.TestCase):
    def test_scope_excludes_high_school_like_and_other_state_records(self):
        for changes in ({"school.degrees_awarded.predominant": 0},
                        {"school.degrees_awarded.predominant": 1},
                        {"school.operating": 0}, {"school.state": "GA"}):
            self.assertIsNone(data_api.normalize(school(**changes)))
        self.assertEqual(data_api.normalize(school(**{"school.degrees_awarded.predominant": 2}))["level"], "Two-year / community college")

    def test_suppressed_missing_and_invalid_rates_are_not_zero(self):
        value = data_api.normalize(school(**{"latest.cost.tuition.in_state": "PrivacySuppressed",
                                            "latest.admissions.admission_rate.overall": 1.1}))
        self.assertIsNone(value["tuition_in"])
        self.assertIsNone(value["acceptance"])
        self.assertEqual(data_api.normalize(school(**{"latest.admissions.admission_rate.overall": 0}))["acceptance"], 0)

    def test_completion_uses_correct_cohort(self):
        row = school(**{"school.degrees_awarded.predominant": 2,
                        "latest.completion.completion_rate_less_than_4yr_150nt": .35})
        self.assertEqual(data_api.normalize(row)["graduation"], .35)

    def test_pagination_and_snapshot(self):
        session = Session([Response([school(i) for i in range(100)], 101), Response([school(100)], 101)])
        with isolated_snapshot(), patch.dict(sys.modules, {"requests": types.SimpleNamespace()}):
            result = data_api.fetch_colleges("TEST_KEY", session)
            self.assertEqual(len(result["records"]), 101)
            self.assertEqual([c["page"] for c in session.calls], [0, 1])
            self.assertEqual(data_api.load_snapshot()["records"], result["records"])
            self.assertNotIn("TEST_KEY", json.dumps(result))

    def test_failed_refresh_preserves_snapshot(self):
        with isolated_snapshot(), patch.dict(sys.modules, {"requests": types.SimpleNamespace()}):
            data_api.SNAPSHOT.write_text('{"original":true}')
            with self.assertRaises(RuntimeError):
                data_api.fetch_colleges("TEST_KEY", Session([Response([], 0)]))
            self.assertEqual(data_api.SNAPSHOT.read_text(), '{"original":true}')

if __name__ == "__main__":
    unittest.main()
