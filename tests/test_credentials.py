"""A requested credential must belong to the requested major."""
import unittest
from pathlib import Path
from unittest.mock import patch

from test_app import HAS_UI, assert_finder_count, data_api, fixture, open_map_list


@unittest.skipUnless(HAS_UI, "Install project requirements to run UI checks")
class CredentialFilterTests(unittest.TestCase):
    def test_masters_alone_and_with_major_on_finder_and_map(self):
        from streamlit.testing.v1 import AppTest

        catalog = {
            "programs": {"5116": "Nursing", "1107": "Computer Science"},
            "levels": {"3": "Bachelor", "5": "Master"},
            "schools": {
                "1": {"5116": ["3"], "1107": ["5"]},
                "2": {"5116": ["5"]},
                "3": {"5116": ["3"]},
            },
        }
        with (
            patch.object(data_api, "load_snapshot", return_value=fixture(3)),
            patch.object(data_api, "load_program_catalog", return_value=catalog),
        ):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            app.multiselect(key="filter_degree_levels").set_value(["Master’s"]).run(timeout=45)
            assert_finder_count(self, app, 2)
            app.multiselect(key="filter_programs").set_value(["5116"]).run(timeout=45)
            assert_finder_count(self, app, 1)
            open_map_list(app)
            self.assertEqual(app.metric[0].value, "1")
            self.assertEqual(app.multiselect(key="map_filter_degree_levels").value, ["Master’s"])
            card = next(n.proto.body for n in app.get("html") if 'class="college-card"' in n.proto.body)
            self.assertIn("Nursing · Master’s", card)
            self.assertIn("View master’s fields of study (1)", card)
            app.multiselect(key="map_filter_programs").set_value([]).run(timeout=45)
            self.assertEqual(app.metric[0].value, "2")

    def test_degree_first_then_major_checks_award_in_that_subject(self):
        from streamlit.testing.v1 import AppTest

        catalog = {
            "programs": {"5116": "Nursing", "1107": "Computer Science"},
            "levels": {"1": "Certificate", "2": "Associate", "3": "Bachelor"},
            "schools": {
                "1": {"5116": ["1", "2"], "1107": ["3"]},
                "2": {"5116": ["2", "3"]},
                "3": {"1107": ["3"]},
            },
        }
        with (
            patch.object(data_api, "load_snapshot", return_value=fixture(3)),
            patch.object(data_api, "load_program_catalog", return_value=catalog),
        ):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            app.multiselect(key="filter_degree_levels").set_value(["Four-year"]).run(timeout=45)
            assert_finder_count(self, app, 2)
            app.multiselect(key="filter_programs").set_value(["5116"]).run(timeout=45)
            self.assertFalse(app.exception)
            assert_finder_count(self, app, 1)
            open_map_list(app)
            self.assertEqual(app.button(key="shortlist_2").label, "Add to compare")
            card = next(n.proto.body for n in app.get("html") if 'class="college-card"' in n.proto.body)
            self.assertIn("Nursing · Bachelor’s", card.partition("</summary>")[0])
            self.assertNotIn("Nursing · Associate", card)
            self.assertEqual(app.metric[0].value, "1")
            self.assertEqual(app.multiselect(key="map_filter_degree_levels").value, ["Four-year"])
            app.multiselect(key="map_filter_degree_levels").set_value(["Certificate"]).run(timeout=45)
            self.assertEqual(app.metric[0].value, "1")
            app.multiselect(key="map_filter_programs").set_value([]).run(timeout=45)
            self.assertEqual(app.multiselect(key="map_filter_degree_levels").value, [])
            self.assertEqual(app.metric[0].value, "3")
