"""Analysis helpers keep missing observations missing and flag rather than discard outliers."""
def outlier_summary(frame, columns):
    rows = []
    for column in columns:
        values = frame[column].dropna()
        q1, q3 = values.quantile(.25), values.quantile(.75)
        spread = q3 - q1
        flagged = ((values < q1 - 1.5 * spread) | (values > q3 + 1.5 * spread)).sum() if len(values) >= 4 and spread > 0 else 0
        rows.append({"Metric": column, "Missing": int(frame[column].isna().sum()),
                     "Available": len(values), "IQR flags": int(flagged)})
    return rows
