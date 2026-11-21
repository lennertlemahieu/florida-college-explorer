"""UI checks with clearly synthetic records; no live API keys needed."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import data_api
try:
    import plotly.express
    from streamlit.testing.v1 import AppTest
    HAS_UI = True
except ImportError:
    HAS_UI = False

def go_to(app, section):
    app.session_state["requested_section"] = section
    return app.run(timeout=45)


def fixture(count=6):
    records = []
    for i in range(count):
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

def open_map_list(app):
    go_to(app, "Map")
    app.radio(key="map_view_mode").set_value("List").run(timeout=45)


def assert_finder_count(case, app, number):
    expected = "1 school matches your must-haves" if number == 1 else f"{number} schools match your must-haves"
    case.assertIn(expected, [item.value for item in app.markdown])
    case.assertFalse(app.metric)


@unittest.skipUnless(HAS_UI, "Install project requirements to run UI checks")
class UITests(unittest.TestCase):
    def test_map_routes_to_selected_school_and_shares_zip_filters(self):
        from campus_location import zip_centroids
        from campus_map import map_html

        with (
            patch.object(data_api, "load_snapshot", return_value=fixture()),
            patch("campus_location.requests.get") as fetch,
            patch("campus_map.map_html", wraps=map_html) as render_map,
        ):
            fetch.return_value.json.return_value = {"routes": [{
                "geometry": {"coordinates": [[-82.552, 27.405], [-82, 27.6]]},
                "distance": 48280.32, "duration": 2880,
            }]}
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            app.multiselect(key="filter_school_types").set_value(["Public"]).run(timeout=45)
            go_to(app, "Map")
            self.assertEqual(app.multiselect(key="map_filter_school_types").value, ["Public"])
            app.text_input(key="map_filter_zip").set_value("34243").run(timeout=45)
            app.selectbox(key="map_filter_radius").set_value("50 miles").run(timeout=45)
            app.selectbox(key="map_school").set_value("2").run(timeout=45)
            self.assertFalse(fetch.called)
            app.button(key="map_draw_route").click().run(timeout=45)
            query = json.loads(fetch.call_args.kwargs["params"]["json"])
            self.assertEqual(query["costing_options"], {"auto": {"shortest": True}})
            self.assertEqual(tuple(query["locations"][0].values()), zip_centroids()["34243"])
            self.assertEqual(render_map.call_args.kwargs["route"], [(27.405, -82.552), (27.6, -82)])
            self.assertTrue(any("48 min" in item.value and "30.0 road miles" in item.value for item in app.markdown))
            app.toggle(key="expanded_map").set_value(True).run(timeout=45)
            fetch.assert_called_once()
            app.text_input(key="map_filter_zip").set_value("34236").run(timeout=45)
            self.assertIsNone(render_map.call_args.kwargs["route"])
            app.radio(key="map_view_mode").set_value("List").run(timeout=45)
            self.assertIn("Distance: nearest first", app.selectbox(key="card_sort").options)
            self.assertTrue(any("mi from 34236" in node.proto.body for node in app.get("html")))
            go_to(app, "Finder")
            self.assertEqual(app.text_input(key="filter_zip").value, "34236")
            self.assertEqual(app.selectbox(key="filter_radius").value, "50 miles")
            self.assertFalse(app.exception)

    def test_ask_ai_submits_to_gemini_and_shows_local_summary_on_quota_error(self):
        from ai import DEFAULT_GEMINI_MODEL

        with (
            patch.object(data_api, "load_snapshot", return_value=fixture()),
            patch("streamlit.secrets", {}),
            patch.dict("os.environ", {"GEMINI_API_KEY": "", "GEMINI_MODEL": DEFAULT_GEMINI_MODEL}),
            patch("ai.requests.post") as post,
        ):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params.update({"view": "ai", "schools": "1,2"})
            app.run(timeout=45)
            self.assertFalse(any(w.label == "Answer using" for w in app.radio))
            self.assertFalse(any(w.label == "Gemini model" for w in app.text_input))
            self.assertFalse(any(w.label == "Gemini API key" for w in app.text_input))
            self.assertFalse(any(panel.label == "Gemini setup" for panel in app.expander))
            self.assertFalse(any("Your answer will appear here" in entry.value for entry in app.caption))
            next(b for b in app.button if b.label == "Show data summary").click().run(timeout=45)
            self.assertIsNone(app.session_state["ai_result"]["model"])
            self.assertFalse(post.called)
            os.environ["GEMINI_API_KEY"] = "test-only-key"
            next(b for b in app.button if b.label == "Compare tuition").click().run(timeout=45)
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Test Gemini answer"}]}}]}
            next(b for b in app.button if b.label == "Ask").click().run(timeout=45)
            self.assertIn(f"/models/{DEFAULT_GEMINI_MODEL}:generateContent", post.call_args.args[0])
            result = app.session_state["ai_result"]
            self.assertEqual([record["id"] for record in result["records"]], ["1", "2"])
            self.assertEqual(result["answer"], "Test Gemini answer")
            self.assertIn("Test Gemini answer", [item.value for item in app.markdown])
            self.assertFalse(app.get("download_button"))
            self.assertFalse(any(panel.label == "Data used for this answer" for panel in app.expander))
            post.return_value.status_code = 429
            next(b for b in app.button if b.label == "Ask").click().run(timeout=45)
            result = app.session_state["ai_result"]
            self.assertIsNone(result["model"])
            self.assertIn("$5,000", result["answer"])
            self.assertTrue(any("quota limit" in item.value for item in app.warning))
            self.assertFalse(app.exception)

    def test_legacy_map_link_and_same_session_school_actions(self):
        from campus_map import map_html

        with (
            patch.object(data_api, "load_snapshot", return_value=fixture()),
            patch("campus_map.map_html", wraps=map_html) as render_map,
        ):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params.update({"view": "map", "schools": "4,invalid,4"})
            app.run(timeout=45)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["main_section"], "Map")
            self.assertEqual(app.query_params, {"schools": "4"})
            markers = render_map.call_args.args[0]
            popup = next(marker["popup"] for marker in markers if marker["id"] == "3")
            self.assertIn("Get directions", popup)
            self.assertNotIn("Add to comparison", popup)
            app.selectbox(key="map_school").set_value("3").run(timeout=45)
            app.button(key="map_shortlist_button").click().run(timeout=45)
            self.assertEqual(app.query_params.get("schools"), "4,3")
            self.assertTrue(any("Compare Schools · 2" in link.proto.label for link in app.get("page_link")))
            self.assertEqual(app.button(key="map_shortlist_button").label, "Remove from compare")
            app.button(key="map_shortlist_button").click().run(timeout=45)
            self.assertEqual(app.query_params.get("schools"), "4")
            app.button(key="map_ask_school").click().run(timeout=45)
            self.assertEqual(app.session_state["main_section"], "AI")
            self.assertEqual(app.multiselect(key="ai_picker").value, ["3"])
            self.assertEqual(app.query_params.get("schools"), "4")

    def test_onboarding(self):
        with patch.object(data_api, "load_snapshot", return_value=None):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.title[0].value, "Florida Campus Atlas")

    def test_loaded_comparison_and_empty_search(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture()):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            self.assertEqual(app.session_state["main_section"], "Finder")
            self.assertTrue(any('id="finder-title">Find a School' in node.proto.body for node in app.get("html")))
            go_to(app, "Home")
            self.assertTrue(any(h.value == "About this app" for h in app.subheader))
            self.assertFalse(any('id="finder-title"' in node.proto.body for node in app.get("html")))
            app.button(key="home_Map").click().run(timeout=45)
            self.assertEqual(app.session_state["main_section"], "Map")
            self.assertFalse(any((b.key or "").startswith("shortlist_") for b in app.button))
            next(b for b in app.button if b.label == "Browse matching colleges").click().run(timeout=45)
            self.assertEqual(app.session_state["main_section"], "Map")
            self.assertEqual(app.radio(key="map_view_mode").value, "List")
            self.assertEqual([e.message for e in app.exception], [])
            self.assertEqual(app.metric[0].value, "6")
            go_to(app, "Compare")
            picker = app.multiselect(key="compare_picker")
            self.assertEqual(picker.value, [])
            self.assertEqual(picker.options, sorted(picker.options, key=str.casefold))
            picker.set_value(["2", "1"]).run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            table = next(node.proto.body for node in app.get("html") if 'class="compare-table"' in node.proto.body)
            self.assertLess(table.index("Synthetic college 1"), table.index("Synthetic college 0"))
            self.assertIn("Florida median", table)
            self.assertIn('data-remove-school="2" title="Remove Synthetic college 1 from comparison"', table)
            self.assertIn('aria-label="Remove Synthetic college 0 from comparison"', table)
            self.assertNotIn("max-width:850px", table)
            self.assertIn('class="compare-best"', table)
            self.assertIn('title="Not reported" aria-label="Not reported">–', table)
            self.assertIn('class="compare-color" style="background:#55cdb6"', table)
            chart = json.loads(app.get("plotly_chart")[0].proto.spec)
            self.assertEqual([trace["name"] for trace in chart["data"] if trace["showlegend"]],
                             ["Synthetic college 1", "Synthetic college 0"])
            self.assertEqual([shape["line"]["dash"] for shape in chart["layout"]["shapes"]], ["dash", "dash"])
            self.assertTrue(all(shape["layer"] == "below" for shape in chart["layout"]["shapes"]))
            self.assertTrue(all(trace["textposition"] == "inside" for trace in chart["data"]))
            open_map_list(app)
            app.button(key="shortlist_3").click().run(timeout=45)
            self.assertEqual(app.button(key="shortlist_3").label, "Remove from compare")
            self.assertEqual(app.query_params["schools"], "2,1,3")
            app.button(key="shortlist_3").click().run(timeout=45)
            go_to(app, "Compare")
            self.assertEqual(app.multiselect(key="compare_picker").value, ["2", "1"])
            app.multiselect(key="compare_picker").set_value(["2", "1", "3", "4", "5"]).run(timeout=45)
            chart = json.loads(app.get("plotly_chart")[0].proto.spec)
            self.assertTrue(all(trace["orientation"] == "h" for trace in chart["data"]))
            self.assertEqual(len({trace["marker"]["color"] for trace in chart["data"]}), 5)
            open_map_list(app)
            self.assertTrue(app.button(key="shortlist_6").proto.disabled)
            self.assertFalse(app.button(key="shortlist_5").proto.disabled)
            self.assertTrue(any("Compare holds up to 5 schools" in c.value for c in app.caption))
            app.multiselect(key="map_filter_school_types").set_value(["Public"]).run(timeout=45)
            app.select_slider(key="map_filter_max_tuition").set_value(5000).run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            self.assertTrue(any("No colleges match" in item.value for item in app.warning))

    def test_compare_presets_and_data_units(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture()):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params.update({"view": "compare", "schools": "1,2"})
            app.run(timeout=45)
            table = next(node.proto.body for node in app.get("html") if 'class="compare-table"' in node.proto.body)
            traces = json.loads(app.get("plotly_chart")[0].proto.spec)["data"]
            self.assertTrue(all(f'background:{bar["marker"]["color"]}' in table for bar in traces))
            self.assertEqual(len(app.get("plotly_chart")), 3)
            app.radio(key="compare_filter_tuition_basis").set_value("tuition_out").run(timeout=45)
            cost = json.loads(app.get("plotly_chart")[0].proto.spec)
            self.assertEqual(cost["layout"]["annotations"][0]["text"], "Annual out-of-state tuition")
            self.assertEqual([bar["y"][0] for bar in cost["data"] if bar["xaxis"] == "x"], [15000, 16000])
            app.radio(key="compare_preset").set_value("Outcomes").run(timeout=45)
            table = next(node.proto.body for node in app.get("html") if 'class="compare-table"' in node.proto.body)
            self.assertIn("Higher graduation rate", table)
            self.assertNotIn("Annual in-state tuition", table)
            self.assertNotIn(">Cost</th>", table)
            self.assertEqual(len(app.get("plotly_chart")), 1)
            outcome = json.loads(app.get("plotly_chart")[0].proto.spec)
            self.assertEqual([a["text"] for a in outcome["layout"]["annotations"]],
                             ["Graduation rate", "Earnings 10 years after entry"])
            self.assertEqual(outcome["layout"]["yaxis"]["tickformat"], ".0%")
            self.assertEqual(outcome["layout"]["yaxis2"]["tickprefix"], "$")
            self.assertIn("50.0%", outcome["data"][0]["text"])
            app.multiselect(key="compare_picker").set_value(["1", "2", "3"]).run(timeout=45)
            app.radio(key="compare_preset").set_value("Admissions").run(timeout=45)
            admission = json.loads(app.get("plotly_chart")[0].proto.spec)
            self.assertEqual(len(app.get("plotly_chart")), 1)
            self.assertEqual([a["text"] for a in admission["layout"]["annotations"]],
                             ["Acceptance rate", "Undergraduate enrollment", "n/a"])
            self.assertEqual(admission["layout"]["yaxis"]["tickformat"], ".0%")
            self.assertEqual(admission["layout"]["yaxis2"]["tickformat"], ",d")
            self.assertEqual(admission["data"][0]["text"], ["2,000"])
            go_to(app, "Data")
            self.assertFalse(app.exception)
            stats = app.dataframe[0].value.set_index("Metric")
            self.assertEqual(stats.loc["In-state tuition", "Median"], "$7,500")
            self.assertEqual(stats.loc["Acceptance", "Median"], "30%")
            self.assertEqual(stats.loc["Acceptance", "Reporting schools"], 5)
            self.assertIn("Out-of-state tuition", app.dataframe[1].value)
            self.assertIn("Graduation", app.dataframe[2].value["Metric"].values)

    def test_compare_priority_rows_and_sparse_key_differences(self):
        snapshot = fixture(3)
        snapshot["records"][0]["tuition_out"] = None
        snapshot["records"][1]["earnings"] = None
        with patch.object(data_api, "load_snapshot", return_value=snapshot):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params.update({"view": "compare", "schools": "1,2", "tuition": "out",
                                     "priorities": "tuition_in,graduation,debt"})
            app.run(timeout=45)
            self.assertFalse(app.exception)
            def markup(css_class):
                return next(node.proto.body for node in app.get("html") if f'class="{css_class}"' in node.proto.body)
            table = markup("compare-table")
            self.assertIn("Your priorities</th>", table)
            self.assertIn('Annual out-of-state tuition<span class="compare-priority">Priority 1', table)
            self.assertIn('Higher graduation rate<span class="compare-priority">Priority 2', table)
            self.assertIn('Less student debt<span class="compare-priority">Priority 3', table)
            self.assertNotIn("Annual in-state tuition", table)
            summary = markup("compare-takeaways")
            self.assertEqual(summary.count("<li>"), 3)
            self.assertLess(summary.index("Graduation rate is higher"), summary.index("Median student debt is lower"))
            self.assertIn("Too few schools report annual out-of-state tuition and earnings 10 years after entry", summary)
            app.multiselect(key="compare_picker").set_value(["1", "2", "3"]).run(timeout=45)
            summary = markup("compare-takeaways")
            self.assertIn("Annual out-of-state tuition ranges from $16,000 at Synthetic college 1 to $17,000 at Synthetic college 2.", summary)
            self.assertIn("2 of 3 schools report this figure.", summary)

    def test_comparison_link_and_sparse_results(self):
        snapshot = fixture()
        for record in snapshot["records"][:2]:
            record["tuition_in"] = record["tuition_out"] = None
        snapshot["records"][0]["enrollment"] = 0
        snapshot["records"][1]["acceptance"] = None
        for field in ("tuition_in", "tuition_out", "debt"):
            snapshot["records"][0][field] = None
        with patch.object(data_api, "load_snapshot", return_value=snapshot):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params.update({"view": "compare", "schools": "1,2,2,invalid"})
            app.run(timeout=45)
            self.assertEqual(app.session_state["main_section"], "Compare")
            self.assertEqual(app.multiselect(key="compare_picker").value, ["1", "2"])
            table = next(node.proto.body for node in app.get("html") if 'class="compare-table"' in node.proto.body)
            self.assertNotIn("Annual in-state tuition", table)
            self.assertNotIn("Annual out-of-state tuition", table)
            self.assertIn('Undergraduate enrollment</th><td><span class="compare-missing" title="Not reported"', table)
            cost_rows = table.split(">Cost</th>", 1)[1].split(">Admissions</th>", 1)[0]
            self.assertNotIn('class="compare-best"', cost_rows)
            self.assertNotIn('scope="row">Athletics', table)
            gap = next(c.value for c in app.caption if c.value.startswith("**Data gaps**"))
            self.assertIn("No reported values for Annual in-state tuition, Acceptance rate.", gap)
            self.assertIn("Only Synthetic college 1 has reported median student debt ($10,100).", gap)
            self.assertIn("Only Synthetic college 1 has reported undergraduate enrollment (2,300).", gap)
            self.assertEqual(len(app.get("plotly_chart")), 1)
            self.assertTrue(any(h.value == "Outcomes comparison" for h in app.subheader))
            self.assertNotIn("Easier to get into", table)
            next(w for w in app.toggle if w.label == "Show only differences").set_value(True).run(timeout=45)
            table = next(node.proto.body for node in app.get("html") if 'class="compare-table"' in node.proto.body)
            self.assertNotIn('scope="row">Athletics', table)
            app.multiselect(key="compare_picker").set_value(["1", "2", "3"]).run(timeout=45)
            chart = json.loads(app.get("plotly_chart")[0].proto.spec)
            self.assertEqual([a["text"] for a in chart["layout"]["annotations"]], ["Median student debt", "n/a"])
            app.multiselect(key="compare_picker").set_value(["1"]).run(timeout=45)
            self.assertTrue(any("Add at least one more school to compare." == item.value for item in app.info))
            next(w for w in app.button if w.label == "Clear all").click().run(timeout=45)
            self.assertEqual(app.multiselect(key="compare_picker").value, [])

    def test_acceptance_filter_excludes_missing_when_requested(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture()):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            self.assertNotIn("School or city", [w.label for w in app.text_input])
            self.assertNotIn("Acceptance rate range (%)", [w.label for w in app.slider])
            go_to(app, "Map")
            app.slider(key="map_filter_acceptance_range").set_value((20, 40)).run(timeout=45)
            self.assertEqual(app.metric[0].value, "4")
            app.checkbox(key="map_filter_unknown_acceptance").uncheck().run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            self.assertEqual(app.metric[0].value, "3")
            go_to(app, "Finder")
            assert_finder_count(self, app, 6)
            next(b for b in app.button if b.label == "View these on the map").click().run(timeout=45)
            self.assertEqual(app.metric[0].value, "6")
            self.assertTrue(app.checkbox(key="map_filter_unknown_acceptance").value)

    def test_tuition_acceptance_division_intersection(self):
        enrichment = {"3": {"athletics": "NCAA Division II"}, "4": {"athletics": "NCAA Division II"}, "5": {"athletics": "NAIA"}}
        with patch.object(data_api, "load_snapshot", return_value=fixture()), patch("assets.overrides", return_value=enrichment):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            open_map_list(app)
            app.multiselect(key="map_filter_athletics").set_value(["NCAA Division II"]).run(timeout=45)
            app.select_slider(key="map_filter_max_tuition").set_value(7000).run(timeout=45)
            app.slider(key="map_filter_acceptance_range").set_value((20, 40)).run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            self.assertEqual(app.metric[0].value, "1")
            cards = "".join(node.proto.body for node in app.get("html"))
            self.assertEqual(cards.count('<article class="college-card">'), 1)
            self.assertIn("Synthetic college 2", cards)
            self.assertIn("Undergraduate enrollment", cards)
            app.button(key="shortlist_3").click().run(timeout=45)
            go_to(app, "Compare")
            self.assertEqual(app.multiselect(key="compare_picker").value, ["3"])
            go_to(app, "Finder")
            assert_finder_count(self, app, 1)

    def test_sort_and_filters_reset_visible_cards(self):
        snapshot = fixture(18)
        for i, school in enumerate(snapshot["records"][1:], 1):
            school["acceptance"] = i / 20
        with patch.object(data_api, "load_snapshot", return_value=snapshot):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            open_map_list(app)
            self.assertTrue(any(c.value == "Showing 12 of 18 matching colleges." for c in app.caption))
            next(w for w in app.button if w.label == "Show more").click().run(timeout=45)
            self.assertTrue(any(c.value == "Showing 18 of 18 matching colleges." for c in app.caption))
            app.selectbox(key="card_sort").set_value("Acceptance rate: high to low").run(timeout=45)
            self.assertTrue(any(c.value == "Showing 12 of 18 matching colleges." for c in app.caption))
            self.assertFalse(any(w.key == "shortlist_1" for w in app.button))
            next(w for w in app.button if w.label == "Show more").click().run(timeout=45)
            app.select_slider(key="map_filter_max_tuition").set_value(20000).run(timeout=45)
            self.assertTrue(any(c.value == "Showing 12 of 16 matching colleges." for c in app.caption))
            next(b for b in app.button if b.label == "Max tuition $20,000 ×").click().run(timeout=45)
            self.assertTrue(any(c.value == "Showing 12 of 18 matching colleges." for c in app.caption))

    def test_fresh_link_and_ai_share_validated_selection(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture()):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params.update({"view": "compare", "schools": "invalid,6,6,2,3,4,5,1"})
            app.run(timeout=45)
            self.assertEqual(app.multiselect(key="compare_picker").value, ["6", "2", "3", "4", "5"])
            links = app.get("page_link")
            self.assertEqual(len(links), 6)
            for link in links:
                self.assertEqual(parse_qs(link.proto.query_string)["schools"], ["6,2,3,4,5"])
            go_to(app, "AI")
            self.assertEqual(app.multiselect(key="ai_picker").value, ["6", "2", "3", "4", "5"])
            go_to(app, "Compare")
            next(w for w in app.button if w.label == "Clear all").click().run(timeout=45)
            self.assertEqual(app.query_params.get("schools", ""), "")
            self.assertEqual(app.multiselect(key="compare_picker").value, [])

    def test_reset_filters_preserves_search(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture()):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            go_to(app, "Data")
            search = next(w for w in app.text_input if w.label == "School or city")
            search.set_value("Synthetic college 0")
            app.slider(key="data_filter_acceptance_range").set_value((10, 50)).run(timeout=45)
            app.checkbox(key="data_filter_unknown_acceptance").uncheck().run(timeout=45)
            self.assertEqual(app.metric[0].value, "0")
            self.assertTrue(any(c.value == "0 colleges match" for c in app.caption))
            next(w for w in app.button if w.label == "Reset filters").click().run(timeout=45)
            self.assertEqual([e.message for e in app.exception], [])
            self.assertEqual(app.metric[0].value, "1")
            self.assertTrue(any(c.value == "1 college matches" for c in app.caption))
            next(b for b in app.button if b.label == "Search: Synthetic college 0 ×").click().run(timeout=45)
            self.assertEqual(app.metric[0].value, "6")
            go_to(app, "Finder")
            self.assertNotIn("School or city", [w.label for w in app.text_input])
            assert_finder_count(self, app, 6)

    def test_program_filter_combines_with_tuition_and_carries_to_map(self):
        catalog = {
            "release_date": "2026-06-10",
            "source": "https://example.com/programs.zip",
            "programs": {"1107": "Computer Science", "3070": "Data Science"},
            "levels": {"3": "Bachelor"},
            "schools": {"1": {"1107": ["3"]}, "3": {"3070": ["3"]}},
        }
        with (
            patch.object(data_api, "load_snapshot", return_value=fixture()),
            patch.object(data_api, "load_program_catalog", return_value=catalog),
        ):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            app.multiselect(key="filter_programs").set_value(["1107", "3070"]).run(timeout=45)
            assert_finder_count(self, app, 2)
            app.select_slider(key="filter_max_tuition").set_value(6000).run(timeout=45)
            assert_finder_count(self, app, 1)
            self.assertFalse(any(w.key == "filter_unknown_programs" for w in app.checkbox))
            open_map_list(app)
            app.checkbox(key="map_filter_unknown_programs").check().run(timeout=45)
            go_to(app, "Finder")
            assert_finder_count(self, app, 2)
            open_map_list(app)
            self.assertTrue(any("Program availability unreported" in node.proto.body for node in app.get("html")))
            self.assertTrue(any("Computer Science · Bachelor’s" in node.proto.body for node in app.get("html")))
            app.checkbox(key="map_filter_unknown_programs").uncheck().run(timeout=45)
            go_to(app, "Compare")
            self.assertFalse(any(b.label == "Computer Science ×" for b in app.button))
            go_to(app, "Map")
            self.assertEqual(app.session_state["main_section"], "Map")
            self.assertEqual(app.metric[0].value, "1")
            self.assertTrue(any(b.label == "Computer Science ×" for b in app.button))
            go_to(app, "Data")
            self.assertEqual(app.metric[0].value, "1")
            self.assertFalse(app.exception)
            go_to(app, "Finder")
            next(b for b in app.button if b.label == "Computer Science ×").click().run(timeout=45)
            assert_finder_count(self, app, 0)
            self.assertEqual(app.multiselect(key="filter_programs").value, ["3070"])
            go_to(app, "Data")
            next(b for b in app.button if b.label == "Reset filters").click().run(timeout=45)
            self.assertEqual(app.metric[0].value, "6")
            go_to(app, "Map")
            self.assertEqual(app.metric[0].value, "6")

    def test_finder_shows_matches_and_puts_selected_filter_measures_first(self):
        snapshot = fixture(4)
        snapshot["records"][0].update(lat=28, lon=-82)
        snapshot["records"][1].update(lat=27.41, lon=-82.54)
        with patch.object(data_api, "load_snapshot", return_value=snapshot):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            self.assertTrue(any(b.key == "shortlist_1" for b in app.button))
            self.assertIsNone(app.selectbox(key="fit_priority_1").value)
            self.assertFalse(any(w.key == "fit_extra_priorities" for w in app.toggle))
            self.assertFalse(any((b.key or "").startswith("preset_") for b in app.button))
            app.select_slider(key="filter_max_tuition").set_value(6000).run(timeout=45)
            app.text_input(key="filter_zip").set_value("34243").run(timeout=45)
            self.assertEqual(app.selectbox(key="fit_priority_1").options[:2], ["Lower tuition", "Closer to your ZIP"])
            self.assertTrue(any("Max tuition $6,000 · ZIP 34243" in row.value for row in app.markdown))
            self.assertTrue(any(h.value == "Matching colleges" for h in app.subheader))
            app.selectbox(key="fit_priority_1").set_value("tuition_in").run(timeout=45)
            app.selectbox(key="fit_priority_2").set_value("distance_miles").run(timeout=45)
            app.selectbox(key="fit_priority_1").set_value("distance_miles").run(timeout=45)
            self.assertEqual(app.selectbox(key="fit_priority_2").value, "tuition_in")
            app.button(key="find_best_matches").click().run(timeout=45)
            ranked = next(node.proto.body for node in app.get("html") if 'class="college-fit"' in node.proto.body)
            self.assertIn("Synthetic college 1", ranked)
            self.assertIn("mi", ranked)
            self.assertFalse(app.exception)

    def test_best_fit_opens_top_results_in_ai_without_changing_shortlist(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture()):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            self.assertTrue(any(panel.label == "Step 2 · Rank your matches (optional)" for panel in app.expander))
            self.assertTrue(any(h.value == "Matching colleges" for h in app.subheader))
            self.assertTrue(app.button(key="find_best_matches").disabled)
            app.selectbox(key="fit_priority_1").set_value("tuition_in").run(timeout=45)
            self.assertFalse(any('class="college-fit"' in node.proto.body for node in app.get("html")))
            app.button(key="find_best_matches").click().run(timeout=45)
            cards = [node.proto.body for node in app.get("html") if 'class="college-fit"' in node.proto.body]
            self.assertIn("Synthetic college 0", cards[0])
            summary = cards[0].partition("</summary>")[0]
            self.assertIn('aria-label="Rank 1">#1', summary)
            self.assertIn('aria-label="Fit score 100, relative to your matches"', summary)
            self.assertIn("Annual in-state tuition</span><strong>$5,000", summary)
            self.assertIn("Graduation rate</span><strong>50.0%", summary)
            self.assertIn("Earnings 10 years after entry</span><strong>$40,000", summary)
            self.assertIn('class="college-priority"><span>Lower tuition</span><strong>100', summary)
            sections = ["college-name", "college-score-block", "college-priority-bars",
                        "School-wide figures", "college-stat-list", 'class="college-fit-explanation"']
            positions = [summary.index(section) for section in sections]
            self.assertEqual(positions, sorted(positions))
            next(b for b in app.button if b.label == "Ask AI about the top matches").click().run(timeout=45)
            self.assertEqual(app.session_state["main_section"], "AI")
            self.assertEqual(len(app.multiselect(key="ai_picker").value), 3)
            self.assertEqual(app.query_params.get("schools", ""), "")
            go_to(app, "Finder")
            self.assertEqual(app.selectbox(key="fit_priority_1").value, "tuition_in")
            self.assertTrue(any('class="college-fit"' in node.proto.body for node in app.get("html")))
            self.assertFalse(app.exception)

    def test_sparse_ranked_handoffs_include_every_visible_top_school(self):
        snapshot = fixture(3)
        for record in snapshot["records"][1:]:
            record["tuition_in"] = None
        with patch.object(data_api, "load_snapshot", return_value=snapshot):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params["schools"] = "2"
            app.run(timeout=45)
            app.selectbox(key="fit_priority_1").set_value("tuition_in").run(timeout=45)
            app.button(key="find_best_matches").click().run(timeout=45)
            link = next(link.proto for link in app.get("link_button") if link.proto.label == "Compare top 3")
            self.assertEqual(parse_qs(urlsplit(link.url).query)["schools"], ["1,2,3"])
            next(b for b in app.button if b.label == "Ask AI about the top matches").click().run(timeout=45)
            self.assertEqual(app.multiselect(key="ai_picker").value, ["1", "2", "3"])
            self.assertEqual(list(app.session_state["ai_fit_context"]), ["1"])
            go_to(app, "Finder")
            app.button(key="map_school_3").click().run(timeout=45)
            self.assertEqual(app.selectbox(key="map_school").value, "3")
            go_to(app, "Finder")
            app.button(key="ask_school_2").click().run(timeout=45)
            self.assertEqual(app.multiselect(key="ai_picker").value, ["2"])
            self.assertEqual(app.query_params["schools"], "2")
            self.assertFalse(app.exception)

    def test_score_audit_requires_developer_setting(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture(3)):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            app.selectbox(key="fit_priority_1").set_value("tuition_in").run(timeout=45)
            with patch.dict("os.environ", {"ATLAS_DEVELOPER_MODE": "false"}):
                app.button(key="find_best_matches").click().run(timeout=45)
                self.assertNotIn("Check the score calculations", [panel.label for panel in app.expander])
            with patch.dict("os.environ", {"ATLAS_DEVELOPER_MODE": "true"}):
                app.run(timeout=45)
                self.assertIn("Check the score calculations", [panel.label for panel in app.expander])

    def test_compare_link_preserves_priorities_residency_and_selected_map(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture(5)):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params.update({"view": "compare", "schools": "4,1", "tuition": "out",
                                     "priorities": "debt,debt,not-a-priority,tuition_in"})
            app.run(timeout=45)
            self.assertEqual(app.radio(key="compare_filter_tuition_basis").value, "tuition_out")
            self.assertEqual(app.query_params["priorities"], "debt,tuition_in")
            table = next(node.proto.body for node in app.get("html") if 'class="compare-table"' in node.proto.body)
            self.assertLess(table.index(">Your priorities<"), table.index(">Admissions<"))
            app.button(key="compare_map").click().run(timeout=45)
            self.assertFalse(app.exception)
            self.assertEqual(app.multiselect(key="map_picked_schools").value, ["4", "1"])
            next(b for b in app.button if b.label == "Return to all matching schools").click().run(timeout=45)
            self.assertEqual(len(app.selectbox(key="map_school").options), 5)
            go_to(app, "Compare")
            app.button(key="compare_ask").click().run(timeout=45)
            self.assertEqual(app.multiselect(key="ai_picker").value, ["4", "1"])
            go_to(app, "Compare")
            app.radio(key="compare_filter_tuition_basis").set_value("tuition_in").run(timeout=45)
            self.assertNotIn("tuition", app.query_params)
            app.button(key="compare_remove_4").click().run(timeout=45)
            self.assertEqual(app.multiselect(key="compare_picker").value, ["1"])
            self.assertEqual(app.query_params["schools"], "1")
            self.assertFalse(app.exception)

    def test_priority_order_size_and_resubmission(self):
        with patch.object(data_api, "load_snapshot", return_value=fixture()):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
            fields = ("tuition_in", "graduation", "earnings", "debt", "enrollment")
            for i, field in enumerate(fields, 1):
                self.assertEqual(sum((w.key or "").startswith("fit_priority_") for w in app.selectbox), i)
                app.selectbox(key=f"fit_priority_{i}").set_value(field).run(timeout=45)
            self.assertTrue(app.button(key="find_best_matches").disabled)
            size = app.selectbox(key="fit_campus_size")
            self.assertEqual(size.options, ["Small", "Medium", "Large"])
            size.set_value("Medium (2,000–9,999)").run(timeout=45)
            app.button(key="find_best_matches").click().run(timeout=45)
            next(b for b in app.button if b.label == "Ask AI about the top matches").click().run(timeout=45)
            record = next(iter(app.session_state["ai_fit_context"].values()))
            self.assertEqual(list(record["weights"].values()), [5, 4, 3, 2, 1])
            self.assertEqual(record["weights"]["Lower tuition"], 5)
            go_to(app, "Finder")
            self.assertEqual(app.selectbox(key="fit_campus_size").value, "Medium (2,000–9,999)")
            self.assertIn("Less student debt", app.selectbox(key="fit_priority_1").options)
            app.selectbox(key="fit_priority_1").set_value("acceptance").run(timeout=45)
            self.assertEqual(app.selectbox(key="fit_priority_4").value, "debt")
            self.assertEqual(len(set(app.session_state["fit_priorities"])), 5)
            self.assertFalse(any('class="college-fit"' in node.proto.body for node in app.get("html")))
            app.selectbox(key="fit_priority_1").set_value(None).run(timeout=45)
            self.assertEqual(app.selectbox(key="fit_priority_1").value, "graduation")
            self.assertEqual(app.selectbox(key="fit_priority_5").value, None)
            self.assertFalse(app.exception)

    def test_close_scores_and_separate_top_three_comparison(self):
        snapshot = fixture(4)
        snapshot["records"][1]["tuition_in"] = snapshot["records"][0]["tuition_in"]
        with patch.object(data_api, "load_snapshot", return_value=snapshot):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params["schools"] = "4"
            app.run(timeout=45)
            app.selectbox(key="fit_priority_1").set_value("tuition_in").run(timeout=45)
            app.button(key="find_best_matches").click().run(timeout=45)
            self.assertFalse(app.exception)
            self.assertFalse(app.session_state["finder_filters"])
            self.assertEqual(app.query_params["schools"], "4")
            link = next(link.proto for link in app.get("link_button") if link.proto.label == "Compare top 3")
            self.assertEqual(parse_qs(urlsplit(link.url).query)["schools"], ["1,2,3"])
            cards = [node.proto.body for node in app.get("html") if 'class="college-fit"' in node.proto.body]
            self.assertIn("Very close to #2", cards[0])
            self.assertIn("Very close to #1", cards[1])
            self.assertNotIn("Very close", cards[2])

    def test_residency_changes_actual_rank_card_and_shared_map_filter(self):
        snapshot = fixture(4)
        snapshot["records"][2]["tuition_out"] = 6500
        with patch.object(data_api, "load_snapshot", return_value=snapshot):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.query_params["schools"] = "1,2"
            app.run(timeout=45)
            self.assertIn("Public (2)", app.multiselect(key="filter_school_types").options)
            self.assertIn("Four-year (2)", app.multiselect(key="filter_degree_levels").options)
            self.assertEqual(app.radio(key="filter_tuition_basis").value, "tuition_in")
            app.select_slider(key="filter_max_tuition").set_value(7000).run(timeout=45)
            app.selectbox(key="fit_priority_1").set_value("tuition_in").run(timeout=45)
            assert_finder_count(self, app, 3)
            app.radio(key="filter_tuition_basis").set_value("tuition_out").run(timeout=45)
            assert_finder_count(self, app, 1)
            app.button(key="find_best_matches").click().run(timeout=45)
            self.assertFalse(app.exception)
            card = next(e.proto.body for e in app.get("html") if 'class="college-fit"' in e.proto.body)
            self.assertIn("Synthetic college 2", card)
            self.assertIn("Annual out-of-state tuition</span><strong>$6,500", card)
            go_to(app, "Map")
            self.assertEqual(app.radio(key="map_filter_tuition_basis").value, "tuition_out")
            self.assertEqual(app.metric[0].value, "1")
            self.assertEqual(app.query_params["schools"], "1,2")

if __name__ == "__main__":
    unittest.main()
