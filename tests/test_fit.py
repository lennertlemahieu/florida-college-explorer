import unittest

import pandas as pd

from campus_location import driving_url, miles_between, zip_centroids
from fit import fit_explanation, match_statistics, rank_reason, rank_schools


class FinderTests(unittest.TestCase):
    def test_cost_weight_orders_lowest_first_and_keeps_missing_unscored(self):
        schools = pd.DataFrame({
            "id": ["4", "2", "1", "3"],
            "name": ["Missing", "Second", "First", "Higher cost"],
            "level": ["Four-year"] * 4,
            "tuition_in": [None, 8000, 8000, 12000],
        })
        ranked, breakdown = rank_schools(schools, schools, {"tuition_in": 5}, None)
        self.assertEqual(ranked["id"].tolist(), ["1", "2", "3", "4"])
        self.assertTrue(pd.isna(ranked.iloc[-1]["fit_score"]))
        self.assertEqual(breakdown["4"], {})

    def test_missing_top_priority_does_not_outrank_complete_result(self):
        schools = pd.DataFrame({
            "id": ["1", "2", "3"],
            "name": ["A", "B", "C"],
            "level": ["Four-year", "Four-year", "Two-year"],
            "tuition_in": [10000, None, 7000],
            "graduation": [.3, .9, .5],
        })
        ranked, breakdown = rank_schools(schools, schools, {"tuition_in": 5, "graduation": 1}, None)
        self.assertEqual(ranked["id"].tolist(), ["3", "1", "2"])
        self.assertEqual(breakdown["2"], {"graduation": 100})
        self.assertEqual(ranked.iloc[-1]["fit_score"], 100)

    def test_tuition_is_ordered_across_degree_levels_and_ignores_filtered_out_schools(self):
        schools = pd.DataFrame({
            "id": ["1", "2", "3", "4", "5"],
            "name": ["A", "B", "C", "D", "E"],
            "level": ["Four-year", "Two-year", "Two-year", "Two-year", "Four-year"],
            "tuition_in": [9000, 3000, 5000, 0, 5000],
        })
        matches = schools[schools.id != "4"]
        ranked, detail = rank_schools(matches, schools, {"tuition_in": 5}, None)
        self.assertEqual(ranked["id"].tolist(), ["2", "3", "5", "1"])
        self.assertEqual(ranked["fit_score"].tolist(), [100, 75, 75, 25])
        self.assertEqual(detail["3"], detail["5"])

    def test_breakdown_reproduces_score_without_rounding_and_excludes_unreported_weight(self):
        schools = pd.DataFrame({"id": ["a", "b", "c"], "name": ["A", "B", "C"],
                                "tuition_in": [10, 20, 30], "earnings": [None, 60, 90]})
        ranked, detail = rank_schools(schools, schools, {"tuition_in": 5, "earnings": 4}, None)
        scores = ranked.set_index("id")["fit_score"]
        self.assertAlmostEqual(detail["b"]["tuition_in"], 200 / 3)
        self.assertAlmostEqual(scores["b"], (5 * detail["b"]["tuition_in"] + 4 * detail["b"]["earnings"]) / 9)
        self.assertEqual(detail["a"], {"tuition_in": 100})
        self.assertEqual(scores["a"], 100)

    def test_explanation_uses_filtered_values_and_names_missing_priority(self):
        row = {"tuition_in": 4000, "graduation": None}
        weights = {"tuition_in": 1, "graduation": 5}
        stats = {"tuition_in": {"total": 4, "count": 4, "ties": {4000: 1}}}
        reason = fit_explanation(row, {"tuition_in": 100}, weights, None, stats)
        self.assertIn("Lowest in-state tuition of your 4 matches ($4,000)", reason)
        self.assertIn("graduation rate (your first priority)", reason)

        stats["tuition_in"] = {"count": 3, "total": 4, "ties": {4000: 3}}
        reason = fit_explanation(row, {"tuition_in": 100}, weights, None, stats)
        self.assertNotIn("lowest", reason)
        self.assertNotIn("median", reason)
        missing = fit_explanation(row, {}, weights, None, stats)
        self.assertIn("in-state tuition", missing)
        self.assertIn("graduation rate", missing)

    def test_explanation_covers_every_priority_and_puts_strengths_first(self):
        weights = {"tuition_in": 5, "earnings": 4, "debt": 3, "acceptance": 2}
        row = {"tuition_in": 16000, "earnings": 80000, "debt": 10000, "acceptance": None}
        stats = {"tuition_in": {"total": 4, "count": 4, "ties": {16000: 1}},
                 "earnings": {"total": 4, "count": 3, "ties": {80000: 1}},
                 "debt": {"total": 4, "count": 1, "ties": {10000: 1}}}
        reason = fit_explanation(row, {"tuition_in": 25, "earnings": 100, "debt": 100}, weights, None, stats)
        self.assertIn("Highest earnings of 3 with data ($80,000)", reason)
        self.assertIn("Tradeoff · highest in-state tuition of your 4 matches ($16,000)", reason)
        self.assertLess(reason.index("$80,000"), reason.index("$16,000"))
        self.assertIn("only match with data for student debt ($10,000)", reason)
        self.assertIn("Missing · acceptance rate", reason)

    def test_explanation_distinguishes_size_match_from_mismatch(self):
        weights = {"enrollment": 5}
        size = "Medium (2,000–9,999)"
        reason = fit_explanation({"enrollment": 2000}, {"enrollment": 100}, weights, size, {})
        self.assertIn("2,000 undergraduates", reason)
        self.assertIn("within your medium-campus range", reason)
        reason = fit_explanation({"enrollment": 1999}, {"enrollment": 0}, weights, size, {})
        self.assertIn("outside your medium-campus range", reason)

    def test_runner_up_can_win_tuition_but_lose_on_other_priorities(self):
        schools = pd.DataFrame({"id": ["A", "B", "C"], "name": ["A College", "B College", "C College"],
                                "tuition_in": [2000, 1000, 3000], "debt": [1000, 9000, 2000],
                                "acceptance": [.9, .7, .15]})
        weights = {"tuition_in": 5, "debt": 4, "acceptance": 3}
        ranked, breakdown = rank_schools(schools, schools, weights, None)
        self.assertEqual(ranked["id"].tolist()[:2], ["A", "B"])
        reason = rank_reason(ranked.iloc[0], ranked.iloc[1], breakdown, weights)
        self.assertIn("A College", reason)
        self.assertIn("$8,000 lower student debt", reason)
        self.assertIn("20 percentage points higher acceptance rate", reason)
        self.assertIn("$1,000 lower in-state tuition", reason)
        self.assertEqual(rank_reason(ranked.iloc[0], ranked.iloc[2], breakdown, weights), "")
        explanation = fit_explanation(ranked.iloc[0], breakdown["A"], weights, None, match_statistics(schools, weights))
        self.assertIn("2nd-lowest in-state tuition", explanation)
        self.assertEqual(explanation.count("of your 3 matches"), 1)

    def test_rank_reason_skips_ties_and_incomplete_comparisons(self):
        weights = {"tuition_out": 5, "earnings": 4, "debt": 3}
        leader = {"id": "1", "name": "First", "fit_score": 90, "tuition_out": 16502, "earnings": 67394, "debt": 5000}
        challenger = {"id": "2", "fit_score": 85, "tuition_out": 15000, "earnings": 50000, "debt": 6000}
        detail = {"1": {"tuition_out": 70, "earnings": 100, "debt": 100},
                  "2": {"tuition_out": 100, "earnings": 50, "debt": 60}}
        reason = rank_reason(leader, challenger, detail, weights)
        self.assertIn("$1,502 lower out-of-state tuition", reason)
        self.assertIn("$17,394 higher earnings", reason)
        self.assertEqual(rank_reason(leader, {**challenger, "fit_score": 90}, detail, weights), "")
        del detail["2"]["debt"]
        self.assertEqual(rank_reason(leader, challenger, detail, weights), "")

    def test_rank_reason_treats_size_as_a_range_not_a_larger_is_better_metric(self):
        weights = {"tuition_in": 5, "enrollment": 4}
        leader = {"id": "1", "name": "First", "fit_score": 90, "tuition_in": 10001, "enrollment": 1200}
        challenger = {"id": "2", "fit_score": 80, "tuition_in": 10000, "enrollment": 9000}
        detail = {"1": {"tuition_in": 90, "enrollment": 100}, "2": {"tuition_in": 100, "enrollment": 0}}
        reason = rank_reason(leader, challenger, detail, weights)
        self.assertIn("your preferred size range (1,200 undergraduates)", reason)

    def test_zip_lookup_and_driving_link(self):
        sarasota = zip_centroids()["34243"]
        self.assertAlmostEqual(miles_between(sarasota, *sarasota), 0)
        self.assertGreater(miles_between(sarasota, 25.76, -80.19), 150)
        self.assertIn("origin=34243%2C+USA", driving_url({"lat": 27.38, "lon": -82.55}, "34243"))
