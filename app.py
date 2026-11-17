"""Run with: streamlit run app.py."""
import html
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import plotly.express as px
import streamlit as st

from ai import summarize
from analysis import outlier_summary
from assets import cached_icons, logo_background, overrides, refresh_icons
from data_api import NUMERIC, fetch_colleges, load_snapshot
from map_view import map_html

st.set_page_config(page_title="Florida Campus Atlas", page_icon="📍", layout="wide")
st.markdown("""<style>
.block-container {padding-top:3.6rem;max-width:1680px;padding-inline:clamp(1rem,3vw,3rem)}
h1,h2,h3 {letter-spacing:-.035em}
.stApp a[href="#matching-colleges"] {display:inline-block;color:#9cf0da;background:#193b39;
    padding:.45rem .7rem;border-radius:8px;text-decoration:none;font-weight:650}
.stApp a[href="#matching-colleges"]:hover {background:#24504b;text-decoration:underline}
[data-testid="stCaptionContainer"] p,[data-testid="stMetricLabel"] p {color:#c3d2d5}
.st-key-atlas_header h1 {display:flex;align-items:center;gap:.42em;font-size:clamp(1.8rem,4.5vw,3rem)}
.st-key-atlas_header h1::before {content:"";display:inline-block;flex:none;width:.77em;height:.77em;
    border-radius:55% 55% 55% 12%;transform:rotate(-45deg);background:radial-gradient(circle at center,#e7f8ed 0 16%,transparent 17%),#076952;
    box-shadow:0 0 0 .09em #c7e7d8}
.st-key-main_section [role="radiogroup"] {gap:.35rem;display:inline-flex;flex-wrap:wrap;padding:.28rem;
    background:#121c21;border:1px solid #304346;border-radius:12px}
.st-key-main_section [role="radiogroup"] label {padding:.45rem .7rem;margin:0;border-radius:8px}
.st-key-main_section label:has(input:checked) {background:#153c35}
[data-testid="stMetric"] {background:#121c21;border:1px solid #2a3c41;border-radius:12px;padding:12px 16px}
.college-grid {display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,290px),1fr));gap:22px;align-items:start}
.college-card {background:#121c21;color:#edf5f3;border:1px solid #2a3c41;border-radius:16px;overflow:hidden;
    transition:transform .16s ease,box-shadow .16s ease}
@media (hover:hover) and (prefers-reduced-motion:no-preference) {
    .college-card:hover {transform:translateY(-3px);box-shadow:0 8px 24px #2c7b6333}
}
.college-card summary {display:block;cursor:pointer;list-style:none}
.college-card summary::-webkit-details-marker {display:none}
.college-card summary:focus-visible {outline:3px solid #77dfc2;outline-offset:-3px}
.college-card summary:hover .college-name,.college-card a {color:#8ae8ce}
.college-cover {aspect-ratio:2.15;position:relative;display:grid;place-items:center;overflow:hidden;
    background:radial-gradient(ellipse at 85% 0,#fff3,transparent 60%),var(--cover-color,#175c59);color:#fff}
.college-mark-tile {display:grid;place-items:center;width:132px;height:75px;padding:10px;box-sizing:border-box;
    border-radius:12px;background:var(--mark-background,#fff)}
.college-mark-tile .college-mark {display:block;width:auto;height:auto;max-width:100%;max-height:55px;object-fit:contain}
.college-cover .campus-photo {position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.college-mark-badge {position:absolute;z-index:1;left:14px;bottom:12px;width:52px;height:44px;padding:6px;
    box-shadow:0 2px 8px #112e3640;border-radius:9px}
.college-mark-badge .college-mark {max-height:32px}
.college-mark-badge .college-initials {color:#123440;font-size:.8rem;letter-spacing:.02em}
.college-initials {font-size:2.35rem;font-weight:750;letter-spacing:.04em;line-height:1}
.college-card-header {display:grid;align-content:start;gap:6px;min-height:105px;padding:17px 44px 15px 17px;position:relative}
.college-name {font-weight:700;line-height:1.3}
.college-meta {color:#bccbc8;font-size:.88rem}
.college-chips {display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}
.college-chip {background:#183730;color:#a3e9d6;font-size:.76rem;font-weight:600;padding:2px 8px;border-radius:999px}
.college-card-header::after {content:'+';position:absolute;right:14px;top:13px;width:25px;height:25px;
    display:grid;place-items:center;border-radius:50%;background:#183730;color:#a3e9d6;font-size:1.1rem;line-height:1}
.college-card[open] .college-card-header::after {content:'−'}
.college-details {border-top:1px solid #263936;padding:12px 16px 16px}
.college-details dl {display:grid;grid-template-columns:1fr auto;gap:8px 12px;margin:0 0 10px;font-size:.86rem}
.college-details dd {font-weight:600;margin:0;text-align:right}
.college-details p {margin:8px 0 0;font-size:.83rem}
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
COVER_COLORS = ("#175c59", "#394f86", "#794960", "#326044", "#875132", "#315972")
with Path(__file__).with_name("data").joinpath("campus_photos.json").open(encoding="utf-8") as file:
    REVIEWED_PHOTOS = json.load(file)


def college_card(school, asset):
    name = html.escape(school["name"])
    location = html.escape(school["city"] if pd.notna(school["city"]) and school["city"] else "Florida")
    image = asset.get("data")
    school_id = school["id"]
    photo = REVIEWED_PHOTOS.get(school_id)
    background = logo_background(image)
    cover_color = COVER_COLORS[sum(map(ord, school["id"])) % len(COVER_COLORS)]
    initials = "".join(word[0] for word in school["name"].split() if len(word) > 2)[:4].upper()
    initials_mark = f'<span class="college-initials" aria-hidden="true">{html.escape(initials)}</span>'
    cover = f'<span class="college-mark-tile college-mark-badge">{initials_mark}</span>' if photo else initials_mark
    if background:
        badge = " college-mark-badge" if photo else ""
        cover = (f'<span class="college-mark-tile{badge}" style="--mark-background:{background}">'
                 f'<img class="college-mark" src="{html.escape(image)}" alt="" loading="lazy"></span>')
    credit = ""
    if photo:
        url, source = html.escape(photo["url"]), html.escape(photo["source"])
        cover += f'<img class="campus-photo" src="{url}" alt="Campus at {name}" loading="lazy">'
        credit = f'<p><a href="{source}" target="_blank" rel="noopener">Campus photo source</a></p>'

    fields = [("School type", school["type"]), ("Degree level", school["level"]), ("Athletics", school["athletics"])]
    for field in METRICS:
        kind = "percent" if field in ("acceptance", "graduation") else "number" if field == "enrollment" else "money"
        fields.append((LABELS[field], display(school[field], kind)))
    details = "".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>" for label, value in fields)
    website = str(school.get("website") or "").strip()
    site_link = ""
    if website:
        website = website if "://" in website else f"https://{website}"
        parsed = urlsplit(website)
        if parsed.scheme in ("http", "https") and parsed.hostname:
            site_link = f'<p><a href="{html.escape(website)}" target="_blank" rel="noopener">Visit school website ↗</a></p>'
    tuition = school["tuition_in"]
    tuition_chip = f'<span class="college-chip">{display(tuition, "money")} in-state</span>' if pd.notna(tuition) else ""
    return f'''<details class="college-card"><summary>
        <span class="college-cover" style="--cover-color:{cover_color}">{cover}</span>
        <span class="college-card-header"><span class="college-name">{name}</span><span class="college-meta">{location}</span>
        <span class="college-chips"><span class="college-chip">{html.escape(school["type"])}</span>{tuition_chip}</span></span>
        </summary><div class="college-details"><dl>{details}</dl>{site_link}{credit}</div></details>'''

with st.container(key="atlas_header"):
    st.title("Florida Campus Atlas")
section = st.radio("Sections", ["Map", "Compare", "Data", "AI"], horizontal=True,
                   label_visibility="collapsed", key="main_section")

search_slot = st.sidebar.container()
data_settings = st.sidebar.expander("Data and image settings")
with data_settings:
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
    st.info("Open Data and image settings in the sidebar and click Fetch / refresh Florida colleges to get started.")
    st.markdown("""The app includes a logo map, school comparisons, EDA, and direct LLM API summaries.

Only operating Florida institutions whose predominant award is an associate or bachelor’s degree are included. High schools, certificate-only providers, and graduate-only institutions are outside this version’s scope.

**School images:** after fetching data, use the image loader to find logos and website icons.

**Athletics:** NCAA I/II/III, NAIA, NJCAA, and other affiliations can be entered with sources in the same file. Membership is never guessed from the school’s name.""")
    st.stop()

frame = pd.DataFrame(snapshot["records"])
for column in NUMERIC:
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
reviewed = overrides()
affiliations = frame["id"].map(lambda key: (reviewed.get(key, {}).get("athletics") or "Not verified").split("|"))
frame["athletics"] = affiliations.str.join(" · ")
division_counts = affiliations.explode().value_counts()
frame["school"] = frame["name"] + " · " + frame["city"].fillna("") + " [" + frame["id"] + "]"
icons = cached_icons()
with search_slot:
    st.header("Find colleges")
    search = st.text_input("School or city")
with data_settings:
    if st.button("Load school images", width="stretch"):
        with st.spinner("Finding school logos and website icons…"):
            refresh_icons(snapshot["records"])
        st.rerun()
    st.caption("Pins use a school logo when available, then a website icon or graduation cap.")

with st.popover("Filters"):
    st.subheader("Show colleges that match your criteria")
    st.caption("All selected conditions must match. Missing values are excluded when their filter is enabled. Leave a category empty to include all values.")
    with st.form("college_options"):
        left, right = st.columns(2)
        with left:
            st.write("Location & school")
            cities = st.multiselect("City", sorted(frame["city"].dropna().unique()))
            types = st.multiselect("School type", sorted(frame["type"].unique()))
            levels = st.multiselect("Degree level", sorted(frame["level"].unique()))
            division_options = ["NCAA Division I", "NCAA Division II", "NCAA Division III", "NAIA", "NJCAA", "NCCAA", "USCAA"]
            division_options += sorted(set(division_counts.index) - set(division_options))
            athletics = st.multiselect("Athletics division / association", division_options,
                                       format_func=lambda division: f"{division} ({division_counts.get(division, 0)})")
            st.caption("Counts show schools in the atlas before other filters. Select multiple divisions to match any of them.")
            filter_tuition = st.checkbox("Filter by tuition")
            tuition = st.selectbox("Tuition measure", ["tuition_in", "tuition_out"], format_func=LABELS.get)
            minimum_tuition = st.number_input("Minimum annual tuition ($)", min_value=0, value=0, step=1000)
            budget = st.number_input("Maximum annual tuition ($)", min_value=0, value=100000, step=1000)
        with right:
            st.write("Admissions & outcomes")
            filter_acceptance = st.checkbox("Filter by acceptance rate")
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
for field, selected_values, label in [("city", cities, "City"), ("type", types, "School type"), ("level", levels, "Degree level")]:
    if selected_values:
        mask &= frame[field].isin(selected_values)
        active_filters.append(label + ": " + ", ".join(selected_values))
if athletics:
    selected_divisions = set(athletics)
    mask &= affiliations.map(lambda values: bool(selected_divisions.intersection(values)))
    active_filters.append("Athletics: " + ", ".join(athletics))
if search:
    mask &= (frame["name"].fillna("") + " " + frame["city"].fillna("")).str.contains(search, case=False, regex=False)
if filter_tuition:
    if minimum_tuition > budget:
        st.error("Minimum tuition must not exceed maximum tuition. Adjust it in Filters and apply again.")
        st.stop()
    mask &= frame[tuition].between(minimum_tuition, budget)
    active_filters.append(f"Tuition: ${minimum_tuition:,}–${budget:,}")
if filter_acceptance:
    mask &= frame["acceptance"].between(acceptance[0] / 100, acceptance[1] / 100)
    active_filters.append(f"Acceptance: {acceptance[0]}–{acceptance[1]}%")
if filter_enrollment:
    if minimum_enrollment > maximum_enrollment:
        st.error("Minimum enrollment must not exceed maximum enrollment. Adjust it in Filters and apply again.")
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
st.caption(" · ".join(active_filters) or "All colleges")
if section in ("Map", "Data"):
    a, b, c = st.columns(3)
    a.metric("Colleges in view", len(filtered))
    b.metric("Median tuition", display(filtered[tuition].median(), "money"))
    c.metric("Median acceptance", display(filtered["acceptance"].median(), "percent"))
if filtered.empty:
    if athletics and not any(division_counts.get(division, 0) for division in athletics):
        st.warning("No schools in the atlas have a verified affiliation for " + ", ".join(athletics) + ".")
    else:
        st.warning("No colleges match. Clear your search or open Filters to adjust your criteria.")
    st.stop()

if section == "Map":
    map_heading, map_control = st.columns([3, 1], vertical_alignment="center")
    map_heading.subheader("Campus map")
    map_heading.markdown("[Browse matching colleges](#matching-colleges)")
    expanded_map = map_control.toggle("Expand map", key="expanded_map")
    mapped = filtered.dropna(subset=["lat", "lon"])
    markers = []
    for _, school in mapped.iterrows():
        asset = icons.get(school["id"], {})
        image = asset.get("data")
        background = logo_background(image)
        name = html.escape(str(school["name"]))
        popup = f"<div style='font:14px sans-serif;min-width:220px'><h3>{name}</h3>"
        if background:
            popup += f"<img src='{image}' width='72' style='background:{background};padding:4px;border-radius:4px' alt='{name}'><br><small>{html.escape(asset['kind'])}</small><br>"
        for field in ["acceptance", tuition, "enrollment", "graduation", "debt", "earnings"]:
            kind = "percent" if field in ("acceptance", "graduation") else "number" if field == "enrollment" else "money"
            popup += f"<p><b>{LABELS[field]}</b><br>{display(school[field], kind)}</p>"
        popup += f"<p>{html.escape(school['athletics'])}</p></div>"
        markers.append({"name": school["name"], "lat": school["lat"], "lon": school["lon"], "image": image if background else None,
                        "darkBackground": background == "#123440", "popup": popup})
    st.iframe(map_html(markers), height=960 if expanded_map else 620, alt="Aerial map of Florida with interactive college pins")
    if len(mapped) != len(filtered):
        st.caption(f"{len(filtered) - len(mapped)} school(s) lack coordinates and remain available below.")
    st.subheader("Matching colleges")
    results = filtered.sort_values("name", key=lambda names: names.str.casefold())
    cards = "".join(college_card(school, icons.get(school["id"], {})) for school in results.to_dict("records"))
    st.html(f'<section class="college-grid" aria-label="Filtered college results">{cards}</section>')
    st.download_button("Download filtered college data", filtered.drop(columns=["school"]).to_csv(index=False), "florida_colleges.csv", "text/csv")

if section == "Compare":
    st.subheader("Compare schools")
    schools = filtered.sort_values("name", key=lambda names: names.str.casefold()).set_index("id", drop=False)
    duplicate_names = schools["name"].duplicated(keep=False)
    school_labels = schools["name"].where(~duplicate_names, schools["school"]).to_dict()
    saved_schools = st.session_state.setdefault("comparison_schools", {})
    for number, column in enumerate(st.columns(3), start=1):
        with column:
            options = schools.index.tolist()
            saved_id = saved_schools.get(number)
            widget_key = f"compare_school_{number}"
            if st.session_state.get(widget_key) not in schools.index:
                st.session_state[widget_key] = saved_id if saved_id in schools.index else None
            selected_id = st.selectbox(f"School {number}", options, index=None,
                                       format_func=school_labels.__getitem__, placeholder="Type a school name",
                                       key=widget_key)
            if selected_id is not None or saved_id in schools.index:
                saved_schools[number] = selected_id
            if selected_id is None:
                continue
            school = schools.loc[selected_id]
            asset = icons.get(selected_id, {})
            if asset.get("data"):
                st.image(asset["data"], width=72)
                st.caption(asset["kind"])
            st.subheader(school["name"])
            st.write(f"{school['city']} · {school['type']} · {school['level']}")
            for field in METRICS:
                kind = "percent" if field in ("acceptance", "graduation") else "number" if field == "enrollment" else "money"
                st.metric(LABELS[field], display(school[field], kind))
            st.write("Athletics: " + school["athletics"])

if section == "Data":
    st.subheader("Charts and statistics")
    st.caption("Charts reflect the current filters. Compare similar degree levels before drawing conclusions.")
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
    st.write("Pairwise sample sizes")
    st.dataframe(available.T.dot(available).rename(index=LABELS, columns=LABELS))
    st.write("Missing data and outlier audit")
    st.dataframe(outlier_summary(filtered, METRICS), hide_index=True, width="stretch")
    st.info("Missing metrics are excluded only from calculations that need them; they are never replaced with zero. IQR outliers are flagged and retained because unusual tuition or enrollment may be valid. Invalid negative costs and rates outside 0–1 are treated as missing.")
    st.write(f"Among these {len(filtered)} institutions, {filtered['acceptance'].notna().sum()} report acceptance rates and {filtered['graduation'].notna().sum()} report the selected completion measure. Medians describe institutions equally, rather than weighting by enrollment.")

if section == "AI":
    st.subheader("AI comparison")
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
        with st.popover("Inspect the exact data sent to the model"):
            st.json({k: v for k, v in result.items() if k != "answer"})

if section == "Data":
    st.subheader("Data sources and definitions")
    st.caption(f"U.S. Department of Education College Scorecard · Retrieved {snapshot['fetched_at'][:10]}")
    st.markdown("""**Scope:** operating Florida postsecondary institutions with predominantly associate or bachelor’s degrees. This includes community colleges and eligible private colleges. No high schools. Certificate-only and graduate-only schools are excluded.

**Data:** [College Scorecard](https://collegescorecard.ed.gov/data/) and its [API documentation](https://collegescorecard.ed.gov/data/api-documentation/). JSON is paginated and saved locally. Filters do not change the underlying snapshot. Refresh it before a presentation.

**Acceptance:** reported institutional admission rate, not an individual admission probability. Missing acceptance is ‘Not reported’; open admission is not inferred.

**Cost:** annual tuition and required fees, not total attendance cost or net price after financial aid.

**Completion:** 150%-of-normal-time completion measure, using the four-year or less-than-four-year measure based on predominant degree. The cohorts do not represent all students. Earnings are measured 10 years after entry for the source’s covered population, not guaranteed salaries for all graduates. Debt covers completers in the reported federal-loan population.

**Timing:** ‘latest’ fields can refer to different reporting years and cohorts. The retrieval date is not an academic year. Consult the source dictionary before interpreting comparisons; this app does not claim a common-year panel.

**Athletics:** affiliations are sourced from athletics organizations, conferences, and schools. Schools may appear in multiple categories. The University of West Florida appears under NCAA Division II and Division I while it reclassifies. Individual sports may compete at different levels. The coverage audit includes verification dates and sources.

**Images:** sourced logo overrides take priority, followed by identifiable logos from school websites and website icons. Pins without an image use a graduation cap. The coverage audit lists each image type and source.

**AI:** direct Gemini API call, triggered only by the user. Generated text can be wrong; verify its claims against the supplied records. API keys remain on the server and are not included in downloads or Git.
""")
    coverage = [{"id": row["id"], "School": row["name"], "Image": icons.get(row["id"], {}).get("kind", "Missing"),
                 "Image source": icons.get(row["id"], {}).get("source", ""),
                 "Athletics": row["athletics"], "Athletics source": reviewed.get(row["id"], {}).get("athletics_source", ""),
                 "Verified on": reviewed.get(row["id"], {}).get("verified_on", "")} for _, row in frame.iterrows()]
    st.dataframe(coverage, hide_index=True, width="stretch")
    st.download_button("Download logo and athletics coverage audit", pd.DataFrame(coverage).to_csv(index=False), "coverage_audit.csv", "text/csv")
