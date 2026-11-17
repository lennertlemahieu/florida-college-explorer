"""UI checks with clearly synthetic records; no live API keys needed."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import data_api
try:
    import plotly.express
    from streamlit.testing.v1 import AppTest
    HAS_UI = True
except ImportError:
    HAS_UI = False

def fixture():
    records = []
    for i in range(6):
        row = {"id": i + 1, "school.name": f"Synthetic college {i}", "school.state": "FL",
               "school.city": "Test City", "school.operating": 1,
               "school.degrees_awarded.predominant": 2 if i % 2 else 3,
               "school.ownership": 1 if i % 2 else 2,
               "location.lat": 27.5 + i / 10, "location.lon": -82,
               "latest.admissions.admission_rate.overall": None if i == 0 else i / 10,
               "latest.cost.tuition.in_state": 5000 + i * 1000,
               "latest.cost.tuition.out_of_state": 15000 + i * 1000,
               "latest.student.size": 2000 + i * 300,
               "latest.completion.completion_rate_4yr_150nt": .5 + i / 100,
               "latest.completion.completion_rate_less_than_4yr_150nt": .3 + i / 100,
               "latest.aid.median_debt.completers.overall": 10000 + i * 100,
               "latest.earnings.10_yrs_after_entry.median": 40000 + i * 1000}
        records.append(data_api.normalize(row))
    return {"records": records, "fetched_at": "2026-01-01T00:00:00Z"}

@unittest.skipUnless(HAS_UI, "Install project requirements to run UI checks")
class UITests(unittest.TestCase):
    def test_onboarding(self):
        with patch.object(data_api, "load_snapshot", return_value=None):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.title[0].value, "Florida Campus Atlas")

    def test_loaded_comparison_and_empty_search(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture()):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            self.assertEqual(app.metric[0].value, "6")
            app.radio(key="main_section").set_value("Compare").run(timeout=45)
            first, second, third = [app.selectbox(key=f"compare_school_{i}") for i in range(1, 4)]
            self.assertEqual([first.value, second.value, third.value], [None, None, None])
            self.assertEqual(first.options, sorted(first.options, key=str.casefold))
            first.select("2")
            second.select("1").run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            self.assertEqual([h.value for h in app.subheader if h.value.startswith("Synthetic college")],
                             ["Synthetic college 1", "Synthetic college 0"])
            app.radio(key="main_section").set_value("Map").run(timeout=45)
            app.radio(key="main_section").set_value("Compare").run(timeout=45)
            self.assertEqual(app.selectbox(key="compare_school_1").value, "2")
            self.assertEqual(app.selectbox(key="compare_school_2").value, "1")
            search = next(w for w in app.text_input if w.label == "School or city")
            search.set_value("nonexistent institution").run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            self.assertTrue(any("No colleges match" in item.value for item in app.warning))

    def test_acceptance_filter_excludes_missing_when_requested(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture()):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            next(w for w in app.checkbox if w.label == "Filter by acceptance rate").check()
            next(w for w in app.slider if w.label == "Acceptance rate range (%)").set_value((20, 40))
            next(w for w in app.button if w.label == "Apply filters").click().run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            self.assertEqual(app.metric[0].value, "3")

    def test_tuition_acceptance_division_intersection(self):
        enrichment = {"3": {"athletics": "NCAA Division II"}, "4": {"athletics": "NCAA Division II"}, "5": {"athletics": "NAIA"}}
        with patch.object(data_api, "load_snapshot", return_value=fixture()), patch("assets.overrides", return_value=enrichment):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            next(w for w in app.multiselect if w.label == "Athletics division / association").set_value(["NCAA Division II"])
            for label in ["Filter by tuition", "Filter by acceptance rate"]:
                next(w for w in app.checkbox if w.label == label).check()
            next(w for w in app.number_input if w.label == "Maximum annual tuition ($)").set_value(7000)
            next(w for w in app.slider if w.label == "Acceptance rate range (%)").set_value((20, 40))
            next(w for w in app.button if w.label == "Apply filters").click().run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            self.assertEqual(app.metric[0].value, "1")
            cards = next(node.proto.body for node in app.get("html") if '<section class="college-grid"' in node.proto.body)
            self.assertEqual(cards.count('<details class="college-card">'), 1)
            self.assertIn("Synthetic college 2", cards)
            self.assertIn("Undergraduate enrollment", cards)
            app.radio(key="main_section").set_value("Compare").run(timeout=45)
            self.assertEqual(app.selectbox(key="compare_school_1").options, ["Synthetic college 2"])

    def test_additional_outcome_filters(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture()):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            for label in ["Filter by enrollment", "Filter by graduation rate", "Filter by student debt", "Filter by earnings"]:
                next(w for w in app.checkbox if w.label == label).check()
            next(w for w in app.number_input if w.label == "Minimum undergraduate enrollment").set_value(2500)
            next(w for w in app.slider if w.label == "Graduation rate range (%)").set_value((50, 100))
            next(w for w in app.number_input if w.label == "Maximum median completer debt ($)").set_value(10300)
            next(w for w in app.number_input if w.label == "Minimum median earnings ($)").set_value(42000)
            next(w for w in app.button if w.label == "Apply filters").click().run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            cards = next(node.proto.body for node in app.get("html") if '<section class="college-grid"' in node.proto.body)
            self.assertEqual(cards.count('<details class="college-card">'), 1)
            self.assertIn("Synthetic college 2", cards)

if __name__ == "__main__":
    unittest.main()
