"""Transparent scoring for the Atlas's best-fit finder."""
import math

CRITERIA = {
    "tuition_in": ("Lower tuition", False),
    "tuition_out": ("Lower out-of-state tuition", False),
    "graduation": ("Higher graduation rate", True),
    "earnings": ("Higher earnings after college", True),
    "debt": ("Less student debt", False),
    "acceptance": ("Easier to get into", True),
    "enrollment": ("Preferred school size", True),
    "distance_miles": ("Closer to your ZIP", False),
}
PRIORITY_HELP = {
    "tuition_in": "Annual in-state tuition and required fees, before financial aid. Housing and meals are separate.",
    "tuition_out": "Annual out-of-state tuition and required fees, before financial aid. Housing and meals are separate.",
    "graduation": "Share of students who finish within 150% of the usual time, such as six years for a four-year degree.",
    "earnings": "Median annual earnings of covered former students 10 years after they first entered college.",
    "debt": "Median federal student loan debt among graduates who borrowed.",
    "acceptance": "A higher reported acceptance rate means a larger share of past applicants was admitted. Your own chances can differ.",
    "enrollment": "Matches the number of undergraduates to the campus size you choose.",
    "distance_miles": "Ranks campuses by straight-line distance from the center of your ZIP area.",
}
SIZE_RANGES = {
    "Small (under 2,000)": (0, 2000),
    "Medium (2,000–9,999)": (2000, 10000),
    "Large (10,000 or more)": (10000, float("inf")),
}

METRIC_NAMES = {
    "tuition_in": "annual in-state tuition",
    "tuition_out": "annual out-of-state tuition",
    "graduation": "graduation rate",
    "earnings": "median earnings 10 years after entry",
    "debt": "median debt for graduates",
    "acceptance": "acceptance rate",
    "enrollment": "undergraduate enrollment",
}


SHORT_METRICS = {
    "tuition_in": "in-state tuition", "tuition_out": "out-of-state tuition",
    "earnings": "earnings", "debt": "student debt", "acceptance": "acceptance rate",
    "graduation": "graduation rate", "enrollment": "campus size",
    "distance_miles": "distance from your ZIP",
}


def match_statistics(results, weights):
    """Number of matches and frequency of each reported value, for honest rank and tie wording."""
    return {field: {"total": len(results), "count": int(results[field].count()),
                    "ties": results[field].value_counts().to_dict()} for field in weights}


def ordinal(n):
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def join_phrases(parts):
    if len(parts) < 2:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def fit_explanation(school, criteria, weights, size, match_stats):
    """Give short, student-facing comparisons in strength-to-tradeoff order."""
    strengths, other, tradeoffs, missing = [], [], [], []
    for field in weights:
        label = SHORT_METRICS[field]
        if field not in criteria:
            missing.append(label)
            continue
        value = school[field]
        score = criteria[field]
        if field == "enrollment":
            preferred = size.split(" (", 1)[0].lower()
            matches = score == 100
            phrase = f"{value:,.0f} undergraduates, {'within' if matches else 'outside'} your {preferred}-campus range"
            (strengths if matches else tradeoffs).append(phrase)
            continue
        if field == "distance_miles":
            formatted = f"{value:,.1f} mi"
        elif field in ("graduation", "acceptance"):
            formatted = f"{value:.1%}"
        else:
            formatted = f"${value:,.0f}"
        stats = match_stats[field]
        count, total = stats["count"], stats["total"]
        ties = stats["ties"][value]
        if ties == count:
            if total == 1:
                other.append(f"{label} of {formatted}")
            elif count == 1:
                other.append(f"only match with data for {label} ({formatted})")
            else:
                other.append(f"{label} tied at {formatted} across all {count} with data")
            continue

        # The percentile includes equals. Count strictly better/worse values to give competition ranks.
        worse = round(count * score / 100) - ties
        better = count - worse - ties
        favorable = better <= worse
        position = (better if favorable else worse) + 1
        direction = "highest" if CRITERIA[field][1] == favorable else "lowest"
        place = direction if position == 1 else f"{ordinal(position)}-{direction}"
        cohort = f"of your {count} matches" if count == total else f"of {count} with data"
        phrase = f"{'tied for ' if ties > 1 else ''}{place} {label} {cohort} ({formatted})"
        if better == worse:
            other.append(phrase)
        else:
            (strengths if favorable else tradeoffs).append(phrase)

    # Give the common comparison group once. Keep the denominator on any measure with missing data.
    total_matches = next((stat["total"] for stat in match_stats.values()), 0)
    common_group = f" of your {total_matches} matches"
    has_group = False
    for phrases in (strengths, other, tradeoffs):
        for i, phrase in enumerate(phrases):
            if common_group in phrase:
                if has_group:
                    phrases[i] = phrase.replace(common_group, "")
                has_group = True
    first_line = join_phrases(strengths + other)
    if first_line:
        first_line = first_line[0].upper() + first_line[1:] + "."
    last_line = ""
    if tradeoffs:
        last_line = ("Tradeoff" if len(tradeoffs) == 1 else "Tradeoffs") + " · " + join_phrases(tradeoffs) + "."
    if missing:
        first = max(weights, key=weights.get)
        missing = [label + " (your first priority)" if label == SHORT_METRICS[first] else label for label in missing]
        last_line = (last_line + " Missing · " + join_phrases(missing) + ".").strip()
    return "\n".join(line for line in (first_line, last_line) if line)


def rank_reason(leader, school, breakdown, weights):
    """Explain a first-priority reversal using the same reported priorities on both sides."""
    if school["id"] == leader["id"] or not weights:
        return ""
    leader_scores, scores = breakdown[leader["id"]], breakdown[school["id"]]
    first = max(weights, key=weights.get)
    if (scores.keys() != leader_scores.keys() or first not in scores
            or scores[first] <= leader_scores[first] or leader["fit_score"] <= school["fit_score"]):
        return ""

    def difference(field, favored):
        if field == "enrollment":
            return f"a campus in your preferred size range ({favored[field]:,.0f} undergraduates)"
        gap = abs(leader[field] - school[field])
        if field in ("acceptance", "graduation"):
            points = f"{gap * 100:.1f}".rstrip("0").rstrip(".")
            amount = (f"{points} percentage {'point' if points == '1' else 'points'}"
                      if points != "0" else "less than 0.1 percentage points")
        elif field == "distance_miles":
            return f"{gap:,.1f} fewer miles in a straight line"
        else:
            amount = f"${gap:,.0f}"
        direction = "higher" if CRITERIA[field][1] else "lower"
        return f"{amount} {direction} {SHORT_METRICS[field]}"

    weighted_gaps = {field: weights[field] * (leader_scores[field] - scores[field]) for field in scores}
    leader_gains = sorted((f for f in scores if weighted_gaps[f] > 0), key=weighted_gaps.get, reverse=True)
    school_gains = [f for f in weights if weighted_gaps.get(f, 0) < 0]
    advantages = join_phrases([difference(f, school) for f in school_gains])
    deciding = join_phrases([difference(f, leader) for f in leader_gains])
    return (f"This school has {advantages}. {leader['name']} ranks first with your weights "
            f"because it has {deciding}.")


def rank_schools(matches, statewide, weights, size):
    """Rank the filtered schools and return full-precision scores for each reported priority.

    The statewide argument is retained for existing callers. Only the current matches
    form the comparison group. Each numeric score is the percentage of reporting
    schools this value equals or beats in the student's preferred direction.
    """
    weights = {field: weight for field, weight in weights.items() if weight > 0}
    if not weights:
        return matches.copy(), {}

    scores = {}
    for field in weights:
        values = matches[field]
        if field == "enrollment":
            low, high = SIZE_RANGES[size]
            scores[field] = (values.between(low, high, inclusive="left") * 100).where(values.notna())
        else:
            scores[field] = values.rank(
                method="max", pct=True, ascending=CRITERIA[field][1],
            ) * 100

    eligible = matches.copy()
    numerator = 0
    denominator = 0
    coverage = 0
    priority_fields = [field for field, weight in weights.items() if weight == max(weights.values())]
    for field, weight in weights.items():
        metric = scores[field]
        numerator = numerator + metric.fillna(0) * weight
        denominator = denominator + metric.notna() * weight
        coverage = coverage + metric.notna()
    eligible["fit_score"] = numerator / denominator.where(denominator.ne(0))
    eligible["fit_coverage"] = coverage
    eligible["fit_priority_covered"] = sum(scores[field].notna()
                                           for field in priority_fields).eq(len(priority_fields))
    eligible["fit_name_order"] = eligible["name"].str.casefold()
    rank_fields = ["fit_priority_covered", "fit_score", "fit_coverage"]
    ascending = [False, False, False]
    ranked = eligible.sort_values(
        [*rank_fields, "fit_name_order", "id"], ascending=[*ascending, True, True], na_position="last",
    )
    breakdown = {
        row["id"]: {field: float(series.loc[index]) for field, series in scores.items()
                    if math.isfinite(series.loc[index])}
        for index, row in ranked.iterrows()
    }
    return ranked, breakdown
