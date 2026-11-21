"""Analysis helpers keep missing observations missing and flag rather than discard outliers."""
import pandas as pd


METRIC_NAMES = {"tuition_in": "In-state tuition", "tuition_out": "Out-of-state tuition",
                "acceptance": "Acceptance", "enrollment": "Enrollment", "graduation": "Graduation",
                "debt": "Debt", "earnings": "Earnings"}


def descriptive_table(frame):
    rows = []
    for field, label in METRIC_NAMES.items():
        values = frame[field].dropna()
        summary = values.describe()
        row = {"Metric": label, "Reporting schools": len(values)}
        for statistic, heading in (("mean", "Mean"), ("std", "Std. deviation"), ("min", "Minimum"),
                                    ("25%", "25th percentile"), ("50%", "Median"),
                                    ("75%", "75th percentile"), ("max", "Maximum")):
            value = summary[statistic]
            if pd.isna(value):
                formatted = "–"
            elif field in ("acceptance", "graduation"):
                formatted = f"{value * 100:.1f}".removesuffix(".0") + (" pp" if statistic == "std" else "%")
            elif field == "enrollment":
                formatted = f"{value:,.0f}"
            else:
                formatted = f"${value:,.0f}"
            row[heading] = formatted
        rows.append(row)
    return pd.DataFrame(rows)


def paired_takeaway(frame, first, second, first_label, second_label):
    pairs = frame[[first, second]].dropna()
    if len(pairs) < 3:
        return "At least three schools with both measures are needed to describe a relationship."
    if pairs[first].nunique() < 2 or pairs[second].nunique() < 2:
        return "A correlation cannot be measured because one or both values are the same across these schools."
    correlation = pairs[first].corr(pairs[second])
    if abs(correlation) < .2:
        return f"{first_label.capitalize()} and {second_label} have little linear relationship here (r = {correlation:.2f})."
    direction = "higher" if correlation > 0 else "lower"
    return f"Schools with higher {first_label} tend to have {direction} {second_label} in this group (r = {correlation:.2f})."


def outlier_summary(frame, columns):
    rows = []
    for column in columns:
        values = frame[column].dropna()
        q1, q3 = values.quantile(.25), values.quantile(.75)
        spread = q3 - q1
        flagged = ((values < q1 - 1.5 * spread) | (values > q3 + 1.5 * spread)).sum() if len(values) >= 4 and spread > 0 else 0
        rows.append({"Metric": METRIC_NAMES[column], "Missing": int(frame[column].isna().sum()),
                     "Available": len(values), "IQR flags": int(flagged)})
    return rows
