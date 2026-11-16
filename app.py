"""Run with: streamlit run app.py."""
import html
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from ai import summarize
from analysis import outlier_summary
from assets import cached_icons, overrides, refresh_icons
from data_api import NUMERIC, fetch_colleges, load_snapshot
from map_view import map_html

st.set_page_config(page_title="Florida College Explorer", page_icon="🎓", layout="wide")
st.markdown("""<style>
.block-container {padding-top:2rem;max-width:1500px}
h1,h2,h3 {letter-spacing:-.035em}
[data-testid="stMetric"] {background:white;border:1px solid #dce6e8;border-radius:12px;padding:16px}
.eyebrow {color:#007f73;font-size:.8rem;font-weight:700;letter-spacing:.16em}
</style>""", unsafe_allow_html=True)

def secret(name, fallback=""):
    try:
        return os.environ.get(name) or st.secrets.get(name, fallback)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return os.environ.get(name, fallback)

def display(value, kind="number"):
    if pd.isna(value):
        return "Not reported"
    if kind == "percent":
        return f"{value:.1%}"
    if kind == "money":
        return f"${value:,.0f}"
    return f"{value:,.0f}"

LABELS = {"tuition_in": "In-state tuition ($)", "tuition_out": "Out-of-state tuition ($)",
          "acceptance": "Acceptance rate", "enrollment": "Undergraduate enrollment",
          "graduation": "Graduation rate (150% of normal time)", "debt": "Median completer debt ($)",
          "earnings": "Median earnings 10 years after entry ($)"}
METRICS = list(LABELS)

st.markdown('<div class="eyebrow">COST · ACCESS · OUTCOMES</div>', unsafe_allow_html=True)
st.title("Find your place in Florida.")
st.write("Explore colleges, community colleges, and universities. Compare the numbers behind your next chapter.")

with st.sidebar:
    st.header("Data connection")
    score_key = st.text_input("College Scorecard API key", value=secret("COLLEGE_SCORECARD_API_KEY", "DEMO_KEY"), type="password")
    st.caption("DEMO_KEY is rate-limited. Get your own key at api.data.gov/signup/.")
    refresh = st.button("Fetch / refresh Florida colleges", type="primary", width="stretch")
    if refresh:
        try:
            with st.spinner("Fetching every page and saving a snapshot…"):
                fetch_colleges(score_key)
            st.success("College data refreshed.")
        except Exception as exc:
            st.error(str(exc) if isinstance(exc, RuntimeError) else "Data request failed. Check your connection and try again.")

try:
    snapshot = load_snapshot()
except (OSError, ValueError):
    snapshot = None
    st.error("The saved snapshot could not be read. Refresh data to replace it.")
if snapshot is None:
    st.info("Start by clicking ‘Fetch / refresh Florida colleges’ in the sidebar. No invented college statistics are included.")
    st.markdown("""The app includes a logo map, school comparisons, EDA, and direct LLM API summaries.

Only operating Florida institutions whose predominant award is an associate or bachelor’s degree are included. High schools, certificate-only providers, and graduate-only institutions are outside this version’s scope.

**Logos:** use the image loader after fetching data. It finds school website icons; full logos can be added in `data/overrides.csv`.

**Athletics:** NCAA I/II/III, NAIA, NJCAA, and other affiliations can be entered with sources in the same file. Membership is never guessed from the school’s name.""")
    st.stop()

frame = pd.DataFrame(snapshot["records"])
for column in NUMERIC:
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
reviewed = overrides()
frame["athletics"] = frame["id"].map(lambda key: reviewed.get(key, {}).get("athletics") or "Not verified")
frame["school"] = frame["name"] + " · " + frame["city"].fillna("") + " [" + frame["id"] + "]"
icons = cached_icons()
with st.sidebar:
    st.divider()
    st.header("Find colleges")
    search = st.text_input("School or city")
    st.divider()
    if st.button("Load school images", width="stretch"):
        with st.spinner("Finding and caching school website images…"):
            refresh_icons(snapshot["records"])
        st.rerun()
    st.caption("School website icons are used unless a sourced logo override is provided. Unavailable images use a graduation-cap marker.")

with st.popover("Options", width="stretch"):
    st.subheader("Show colleges that match your criteria")
    st.caption("All selected conditions must match. Missing values are excluded when their filter is enabled. Leave a category empty to include all values.")
    with st.form("college_options"):
        left, right = st.columns(2)
        with left:
            st.write("Location & school")
            cities = st.multiselect("City", sorted(frame["city"].dropna().unique()))
            types = st.multiselect("School type", sorted(frame["type"].unique()))
            levels = st.multiselect("Degree level", sorted(frame["level"].unique()))
            division_options = sorted(set(["NCAA Division I", "NCAA Division II", "NCAA Division III", "NAIA", "NJCAA", "Other", "Not verified"] + frame["athletics"].unique().tolist()))
            athletics = st.multiselect("Athletics division / association", division_options)
            st.caption("Division filters use the sourced athletics manifest. Unverified schools cannot match a specific division.")
            filter_tuition = st.checkbox("Filter by tuition", value=True)
            tuition = st.selectbox("Tuition measure", ["tuition_in", "tuition_out"], format_func=LABELS.get)
            minimum_tuition = st.number_input("Minimum annual tuition ($)", min_value=0, value=0, step=1000)
            budget = st.number_input("Maximum annual tuition ($)", min_value=0, value=100000, step=1000)
        with right:
            st.write("Admissions & outcomes")
            filter_acceptance = st.checkbox("Filter by acceptance rate", value=True)
            acceptance = st.slider("Acceptance rate range (%)", 0, 100, (0, 100))
            filter_enrollment = st.checkbox("Filter by enrollment")
            minimum_enrollment = st.number_input("Minimum undergraduate enrollment", min_value=0, value=0, step=100)
            maximum_enrollment = st.number_input("Maximum undergraduate enrollment", min_value=0, value=100000, step=100)
            filter_graduation = st.checkbox("Filter by graduation rate")
            graduation = st.slider("Graduation rate range (%)", 0, 100, (0, 100))
            filter_debt = st.checkbox("Filter by student debt")
            maximum_debt = st.number_input("Maximum median completer debt ($)", min_value=0, value=50000, step=1000)
            filter_earnings = st.checkbox("Filter by earnings")
            minimum_earnings = st.number_input("Minimum median earnings ($)", min_value=0, value=0, step=1000)
        st.form_submit_button("Apply filters", type="primary", width="stretch")

mask = pd.Series(True, index=frame.index)
active_filters = []
for field, selected_values, label in [("city", cities, "City"), ("type", types, "School type"), ("level", levels, "Degree level"), ("athletics", athletics, "Division")]:
    if selected_values:
        mask &= frame[field].isin(selected_values)
        active_filters.append(label + ": " + ", ".join(selected_values))
if search:
    mask &= (frame["name"].fillna("") + " " + frame["city"].fillna("")).str.contains(search, case=False, regex=False)
if filter_tuition:
    if minimum_tuition > budget:
        st.error("Minimum tuition must not exceed maximum tuition. Update Options and apply again.")
        st.stop()
    mask &= frame[tuition].between(minimum_tuition, budget)
    active_filters.append(f"Tuition: ${minimum_tuition:,}–${budget:,}")
if filter_acceptance:
    mask &= frame["acceptance"].between(acceptance[0] / 100, acceptance[1] / 100)
    active_filters.append(f"Acceptance: {acceptance[0]}–{acceptance[1]}%")
if filter_enrollment:
    if minimum_enrollment > maximum_enrollment:
        st.error("Minimum enrollment must not exceed maximum enrollment. Update Options and apply again.")
        st.stop()
    mask &= frame["enrollment"].between(minimum_enrollment, maximum_enrollment)
    active_filters.append(f"Enrollment: {minimum_enrollment:,}–{maximum_enrollment:,}")
if filter_graduation:
    mask &= frame["graduation"].between(graduation[0] / 100, graduation[1] / 100)
    active_filters.append(f"Graduation: {graduation[0]}–{graduation[1]}%")
if filter_debt:
    mask &= frame["debt"].le(maximum_debt)
    active_filters.append(f"Median debt ≤ ${maximum_debt:,}")
if filter_earnings:
    mask &= frame["earnings"].ge(minimum_earnings)
    active_filters.append(f"Median earnings ≥ ${minimum_earnings:,}")
filtered = frame[mask].copy()
st.caption("Active options · " + (" · ".join(active_filters) or "All colleges"))
st.caption(f"{len(filtered)} of {len(frame)} colleges match. Options apply to the map, comparisons, charts, AI selection, and downloads.")
st.caption(f"Source: U.S. Department of Education College Scorecard · Retrieved {snapshot['fetched_at'][:10]} · Latest available observations; metric years may differ.")
a, b, c, d = st.columns(4)
a.metric("Colleges in view", len(filtered))
b.metric("Median tuition", display(filtered[tuition].median(), "money"))
c.metric("Median acceptance", display(filtered["acceptance"].median(), "percent"))
d.metric("Images cached", f"{sum(key in icons for key in filtered['id'])} / {len(filtered)}")
if filtered.empty:
    st.warning("No colleges match these filters. Open Options, widen the ranges or disable a filter, then click Apply filters.")
    st.stop()

explore, compare, eda, ai, methods = st.tabs(["Explore the map", "Compare colleges", "Analyze the data", "AI insights", "Sources & methods"])

with explore:
    st.subheader("A campus for every direction")
    st.caption("Zoom to separate nearby campuses. Click a school image to see its data. Cluster counts expand on click.")
    mapped = filtered.dropna(subset=["lat", "lon"])
    markers = []
    for _, school in mapped.iterrows():
        asset = icons.get(school["id"], {})
        image = asset.get("data")
        name = html.escape(str(school["name"]))
        popup = f"<div style='font:14px sans-serif;min-width:220px'><h3>{name}</h3>"
        if image:
            popup += f"<img src='{image}' width='60' alt='{name}'><br><small>{html.escape(asset['kind'])}</small><br>"
        for field in ["acceptance", tuition, "enrollment", "graduation", "debt", "earnings"]:
            kind = "percent" if field in ("acceptance", "graduation") else "number" if field == "enrollment" else "money"
            popup += f"<p><b>{LABELS[field]}</b><br>{display(school[field], kind)}</p>"
        popup += f"<p>{html.escape(school['athletics'])}</p></div>"
        markers.append({"name": school["name"], "lat": school["lat"], "lon": school["lon"], "image": image, "popup": popup})
    st.iframe(map_html(markers), height=610, alt="Interactive Florida college map with school image markers")
    if len(mapped) != len(filtered):
        st.caption(f"{len(filtered) - len(mapped)} school(s) lack coordinates and remain available below.")
    st.dataframe(filtered[["name", "city", "type", "level", "athletics"] + METRICS].rename(columns=LABELS), hide_index=True, width="stretch")
    st.download_button("Download filtered college data", filtered.drop(columns=["school"]).to_csv(index=False), "florida_colleges.csv", "text/csv")

with compare:
    st.subheader("Put your shortlist side by side")
    selected = st.multiselect("Choose up to three colleges", filtered["school"].tolist(), max_selections=3)
    if selected:
        chosen = filtered[filtered["school"].isin(selected)]
        for column, (_, school) in zip(st.columns(len(chosen)), chosen.iterrows()):
            with column:
                asset = icons.get(school["id"], {})
                if asset.get("data"):
                    st.image(asset["data"], width=72)
                    st.caption(asset["kind"])
                st.subheader(school["name"])
                st.write(f"{school['city']} · {school['type']} · {school['level']}")
                for field in METRICS:
                    kind = "percent" if field in ("acceptance", "graduation") else "number" if field == "enrollment" else "money"
                    st.metric(LABELS[field], display(school[field], kind))
                st.write("Athletics: " + school["athletics"])
    else:
        st.info("Select colleges above to build your comparison.")

with eda:
    st.subheader("What do the numbers tell us?")
    st.caption("All charts use the current Options and search filters. Compare similar degree levels before drawing conclusions.")
    first, second = st.columns(2)
    with first:
        st.plotly_chart(px.histogram(filtered, x=tuition, color="type", nbins=20,
                                   labels=LABELS, title="Annual tuition distribution", barmode="overlay"), width="stretch")
        st.plotly_chart(px.box(filtered, x="type", y="acceptance", points="all", hover_name="name",
                             labels=LABELS, title="Acceptance rates by school type").update_yaxes(tickformat=".0%"), width="stretch")
    with second:
        st.plotly_chart(px.scatter(filtered, x=tuition, y="graduation", color="level", hover_name="name",
                                  labels=LABELS, title="Tuition and graduation rate").update_yaxes(tickformat=".0%"), width="stretch")
        st.plotly_chart(px.scatter(filtered, x="acceptance", y="graduation", color="type", hover_name="name",
                                  labels=LABELS, title="Selectivity and completion").update_xaxes(tickformat=".0%").update_yaxes(tickformat=".0%"), width="stretch")
    st.write("Descriptive statistics (rates are fractions from 0 to 1)")
    st.dataframe(filtered[METRICS].describe().rename(columns=LABELS), width="stretch")
    st.write("Pearson correlation · at least three paired observations")
    correlations = filtered[METRICS].corr(min_periods=3)
    st.plotly_chart(px.imshow(correlations.rename(index=LABELS, columns=LABELS), zmin=-1, zmax=1,
                              color_continuous_scale="RdBu", text_auto=".2f", aspect="auto"), width="stretch")
    available = filtered[METRICS].notna().astype(int)
    with st.expander("Pairwise sample sizes"):
        st.dataframe(available.T.dot(available).rename(index=LABELS, columns=LABELS))
    st.write("Missing data and outlier audit")
    st.dataframe(outlier_summary(filtered, METRICS), hide_index=True, width="stretch")
    st.info("Missing metrics are excluded only from calculations that need them; they are never replaced with zero. IQR outliers are flagged and retained because unusual tuition or enrollment may be valid. Invalid negative costs and rates outside 0–1 are treated as missing.")
    st.write(f"Among these {len(filtered)} institutions, {filtered['acceptance'].notna().sum()} report acceptance rates and {filtered['graduation'].notna().sum()} report the selected completion measure. Medians describe institutions equally, rather than weighting by enrollment.")

with ai:
    st.subheader("Turn your shortlist into a clear explanation")
    st.write("This feature makes a direct Gemini API call using selected public college metrics. It requires a separate API key.")
    gemini_key = st.text_input("Gemini API key", value=secret("GEMINI_API_KEY"), type="password")
    model = st.text_input("Gemini model", value=secret("GEMINI_MODEL", "gemini-2.5-flash"))
    ai_schools = st.multiselect("Colleges to explain (up to 10)", filtered["school"].tolist(), default=filtered["school"].head(3).tolist(), max_selections=10)
    question = st.text_area("What would you like to understand?", "Compare affordability, acceptance rates, and graduation outcomes. Explain tradeoffs and missing data.", max_chars=2000)
    if st.button("Generate AI comparison", disabled=not gemini_key or not ai_schools):
        context = filtered[filtered["school"].isin(ai_schools)][["id", "name", "type", "level", "athletics"] + METRICS]
        records = json.loads(context.to_json(orient="records"))
        try:
            with st.spinner("Requesting a grounded comparison…"):
                answer = summarize(records, question, gemini_key, model)
            st.session_state["ai_result"] = {"answer": answer, "question": question, "records": records, "model": model}
        except Exception as exc:
            st.error(str(exc) if isinstance(exc, (RuntimeError, ValueError)) else "AI request failed. Check your connection and retry.")
    if "ai_result" in st.session_state:
        result = st.session_state["ai_result"]
        st.caption("Saved response for: " + ", ".join(r["name"] for r in result["records"]) + ". Regenerate after changing the selection.")
        st.markdown(result["answer"])
        st.download_button("Download AI explanation", result["answer"], "college_comparison.md")
        with st.expander("Inspect the exact data sent to the model"):
            st.json({k: v for k, v in result.items() if k != "answer"})

with methods:
    st.subheader("Understand the source before the comparison")
    st.markdown("""**Scope:** operating Florida postsecondary institutions with predominantly associate or bachelor’s degrees. This includes community colleges and eligible private colleges. No high schools. Certificate-only and graduate-only schools are excluded.

**Data:** [College Scorecard](https://collegescorecard.ed.gov/data/) and its [API documentation](https://collegescorecard.ed.gov/data/api-documentation/). JSON is paginated and saved locally. Filters do not change the underlying snapshot. Refresh it before a presentation.

**Acceptance:** reported institutional admission rate, not an individual admission probability. Missing acceptance is ‘Not reported’; open admission is not inferred.

**Cost:** annual tuition and required fees, not total attendance cost or net price after financial aid.

**Completion:** 150%-of-normal-time completion measure, using the four-year or less-than-four-year measure based on predominant degree. The cohorts do not represent all students. Earnings are measured 10 years after entry for the source’s covered population, not guaranteed salaries for all graduates. Debt covers completers in the reported federal-loan population.

**Timing:** ‘latest’ fields can refer to different reporting years and cohorts. The retrieval date is not an academic year. Consult the source dictionary before interpreting comparisons; this app does not claim a common-year panel.

**Athletics:** maintained separately in `data/overrides.csv`. Use a college’s unique Scorecard ID, affiliation, official source, and verification date. NCAA I, II, III; NAIA; and NJCAA should be verified from official directories. Schools can have sport-specific exceptions. ‘Not verified’ does not mean no athletics.

**Images:** official-school website icons are labeled as icons, not full logos. Sourced raster logos in the override manifest take priority. Missing images use a neutral marker. Image availability and appearance should be checked before the demo.

**AI:** direct Gemini API call, triggered only by the user. Generated text can be wrong; verify its claims against the supplied records. API keys remain on the server and are not included in downloads or Git.
""")
    coverage = [{"id": row["id"], "School": row["name"], "Image": icons.get(row["id"], {}).get("kind", "Missing"),
                 "Image source": icons.get(row["id"], {}).get("source", ""),
                 "Athletics": row["athletics"], "Athletics source": reviewed.get(row["id"], {}).get("athletics_source", ""),
                 "Verified on": reviewed.get(row["id"], {}).get("verified_on", "")} for _, row in frame.iterrows()]
    st.dataframe(coverage, hide_index=True, width="stretch")
    st.download_button("Download logo and athletics coverage audit", pd.DataFrame(coverage).to_csv(index=False), "coverage_audit.csv", "text/csv")
