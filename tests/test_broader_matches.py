"""Finder suggestions must produce the advertised count when a student accepts one."""
import unittest
from pathlib import Path
from unittest.mock import patch

from test_app import HAS_UI, assert_finder_count, data_api, fixture, go_to


@unittest.skipUnless(HAS_UI, "Install project requirements to run UI checks")
class BroaderMatchesTests(unittest.TestCase):
    def test_unknown_tuition_count_and_choice_follow_filters_basis_and_navigation(self):
        from streamlit.testing.v1 import AppTest

        snapshot = fixture(6)
        records = snapshot["records"]
        for index in (1, 2, 5):
            records[index]["tuition_in"] = None
        records[1]["tuition_out"] = None
        records[3]["tuition_out"] = 6000
        with patch.object(data_api, "load_snapshot", return_value=snapshot):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params["schools"] = "2,6"
            app.run(timeout=45)
            assert_finder_count(self, app, 6)
            self.assertTrue(any("3 schools match your other filters with no reported in-state tuition. Included" in c.value for c in app.caption))
            app.multiselect(key="filter_school_types").set_value(["Public"]).run(timeout=45)
            app.select_slider(key="filter_max_tuition").set_value(7000).run(timeout=45)
            assert_finder_count(self, app, 0)
            self.assertTrue(any("2 schools match your other filters with no reported in-state tuition. Hidden" in c.value for c in app.caption))
            self.assertTrue(any(b.label == "Clear must-haves" for b in app.button))
            app.checkbox(key="filter_unknown_tuition").check().run(timeout=45)
            assert_finder_count(self, app, 2)
            self.assertTrue(any("2 schools match your other filters with no reported in-state tuition. Included" in c.value for c in app.caption))
            app.radio(key="filter_tuition_basis").set_value("tuition_out").run(timeout=45)
            assert_finder_count(self, app, 2)
            self.assertTrue(any("1 school matches your other filters with no reported out-of-state tuition. Included" in c.value for c in app.caption))
            go_to(app, "Map")
            self.assertEqual(app.metric[0].value, "2")
            self.assertTrue(app.checkbox(key="map_filter_unknown_tuition").value)
            next(b for b in app.button if b.label == "Include unreported tuition ×").click().run(timeout=45)
            self.assertEqual(app.metric[0].value, "1")
            go_to(app, "Data")
            self.assertEqual(app.metric[0].value, "1")
            app.checkbox(key="data_filter_unknown_tuition").check().run(timeout=45)
            go_to(app, "Finder")
            assert_finder_count(self, app, 2)
            self.assertEqual(app.query_params["schools"], "2,6")
            next(b for b in app.button if b.label == "Reset must-haves").click().run(timeout=45)
            assert_finder_count(self, app, 6)
            self.assertNotIn("filter_unknown_tuition", app.session_state["college_filters"])

    def test_ranked_show_more_reaches_all_schools_and_lists_missing_tuition_last(self):
        from streamlit.testing.v1 import AppTest

        snapshot = fixture(14)
        snapshot["records"][0]["tuition_in"] = None
        with patch.object(data_api, "load_snapshot", return_value=snapshot):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            app.select_slider(key="filter_max_tuition").set_value(18000).run(timeout=45)
            app.checkbox(key="filter_unknown_tuition").check().run(timeout=45)
            app.selectbox(key="fit_priority_1").set_value("tuition_in").run(timeout=45)
            app.button(key="find_best_matches").click().run(timeout=45)
            def visible_ids():
                return [b.key.removeprefix("shortlist_") for b in app.button if (b.key or "").startswith("shortlist_")]
            self.assertEqual(visible_ids(), [str(i) for i in range(2, 14)])
            next(b for b in app.button if b.label == "Show more").click().run(timeout=45)
            self.assertEqual(visible_ids(), [str(i) for i in range(2, 15)] + ["1"])
            self.assertFalse(any(b.label == "Show more" for b in app.button))

    def test_suggestion_keeps_other_state_and_no_limit_includes_unknown_tuition(self):
        from streamlit.testing.v1 import AppTest

        snapshot = fixture(8)
        snapshot["records"][-1]["tuition_in"] = None
        with patch.object(data_api, "load_snapshot", return_value=snapshot):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params["schools"] = "2,3"
            app.run(timeout=45)
            self.assertEqual(app.select_slider(key="filter_max_tuition").options[-1], "No limit")
            app.multiselect(key="filter_school_types").set_value(["Public"]).run(timeout=45)
            assert_finder_count(self, app, 4)
            suggestion = app.button(key="broaden_matches")
            self.assertEqual(suggestion.label, "Show 8 schools · remove the Public requirement")
            self.assertEqual(app.multiselect(key="filter_school_types").value, ["Public"])
            suggestion.click().run(timeout=45)
            assert_finder_count(self, app, 8)
            self.assertFalse(any(b.key == "broaden_matches" for b in app.button))
            go_to(app, "Map")
            self.assertEqual(app.metric[0].value, "8")
            self.assertEqual(app.query_params["schools"], "2,3")

    def test_empty_intersection_can_require_two_changes(self):
        from streamlit.testing.v1 import AppTest

        # Tuition permits school 1, athletics permits school 3, public permits only school 2.
        with (
            patch.object(data_api, "load_snapshot", return_value=fixture(3)),
            patch("assets.overrides", return_value={"3": {"athletics": "NAIA"}}),
        ):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            app.select_slider(key="filter_max_tuition").set_value(5000).run(timeout=45)
            app.multiselect(key="filter_athletics").set_value(["NAIA"]).run(timeout=45)
            app.multiselect(key="filter_school_types").set_value(["Public"]).run(timeout=45)
            assert_finder_count(self, app, 0)
            hint = app.button(key="broaden_matches")
            self.assertIn("Show 1 school · ", hint.label)
            self.assertIn(" and ", hint.label)
            hint.click().run(timeout=45)
            assert_finder_count(self, app, 1)
