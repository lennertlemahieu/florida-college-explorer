"""Run with: streamlit run app.py."""
import html
import json
import math
import os
import re
from functools import partial
from itertools import combinations
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from requests import RequestException

from ai import (DAILY_AI_LIMIT, DEFAULT_GEMINI_MODEL, SESSION_AI_LIMIT, DailyQuota,
                GeminiError, college_data_summary, summarize)
from analysis import METRIC_NAMES, descriptive_table, outlier_summary, paired_takeaway
from assets import cached_icons, logo_background, overrides, refresh_icons
from campus_location import CENSUS_SOURCE, DrivingRouteError, driving_url, miles_between, shortest_driving_route, zip_centroids
from campus_photos import campus_photo, campus_photo_credit
from data_api import MASTERS_CREDENTIAL, NUMERIC, credential_label, fetch_colleges, load_program_catalog, load_snapshot, program_matches
from fit import CRITERIA, PRIORITY_HELP, SIZE_RANGES, fit_explanation, join_phrases, match_statistics, rank_reason, rank_schools
from campus_map import map_html

st.set_page_config(page_title="Florida Campus Atlas", page_icon="📍", layout="wide",
                   initial_sidebar_state=265)
ATLAS_LOGO = str(Path(__file__).with_name("florida-campus-atlas-logo.png"))
st.logo(ATLAS_LOGO, size="large")
st.markdown("""<style>
html,body,[data-testid="stAppViewContainer"] {overflow-x:clip}
[data-testid="stMain"] {min-width:0;overflow-x:hidden}
[data-testid="stMainBlockContainer"] {align-self:center;box-sizing:border-box;width:100%;min-width:0;max-width:92rem;
    margin-inline:auto;padding-top:3rem;padding-inline:clamp(1rem,2.4vw,2.25rem)}
h1,h2,h3 {letter-spacing:-.035em}
[data-testid="stMain"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"] p,
[data-testid="stMain"] [data-testid="stMetricLabel"] p {color:#294758;opacity:1}
.st-key-atlas_header {position:relative;background:#142C3B;border-radius:16px;padding:.35rem .9rem}
.st-key-atlas_header [data-testid="stHeading"] {position:absolute;width:1px;height:1px;
    overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.st-key-atlas_header img {display:block;width:min(100%,735px);aspect-ratio:5.4;height:auto;max-height:136px;
    object-fit:cover;margin-inline:auto}
.st-key-explore_map h3,.st-key-explore_results h3 {color:#142c3b}
.st-key-explore_results h3 {font-size:1.7rem}
.finder-hero {position:relative;isolation:isolate;overflow:hidden;border-radius:16px;background:#123440;color:#f7fbfa;
    padding:clamp(1.3rem,3vw,2.7rem);min-height:10.5rem;display:grid;align-content:center}
.finder-hero > img {position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center 51%;z-index:-2}
.finder-hero::before {content:"";position:absolute;inset:0;background:linear-gradient(90deg,#102d37fa 4%,#102d37df 49%,#102d3760 100%);z-index:-1}
.finder-hero h1 {margin:0 0 .4rem;padding:0;font-size:clamp(1.9rem,4.2vw,3.25rem);line-height:1.08;color:#fff}
.finder-hero p {margin:0;max-width:36rem;color:#f4faf9;font-size:1rem;line-height:1.48}
.finder-photo-credit {font-size:.56rem;line-height:1.35;color:#365468;padding:0 .3rem;text-align:right}
.finder-photo-credit p,.finder-photo-credit a {font-size:inherit}
.finder-photo-credit p {margin:0}
.finder-hero .finder-results-link {display:inline-flex;align-items:center;gap:.45rem;margin-top:1rem;
    border-radius:8px;padding:.55rem .9rem;background:#d6f5ed;color:#104d43;font-weight:700;text-decoration:none}
.finder-hero .finder-results-link:hover {background:#fff;color:#104d43}
.finder-hero .finder-results-link:focus-visible {outline:2px solid white;outline-offset:3px}
@media(max-width:45rem) {.finder-hero::before {background:#102d37dd}}
.st-key-finder_priorities {background:#f4fafd;container-type:inline-size}
#finder-best-matches {scroll-margin-top:3.7rem}
.st-key-finder_priorities [data-testid="stCaptionContainer"] p {color:#29485b}
.st-key-must_have_count {background:#d5eee7;border-left:4px solid #087869;border-radius:6px;padding:.45rem .8rem}
.st-key-must_have_count p {font-size:1.1rem;color:#134e45;font-weight:700}
.st-key-finder_priorities button[kind="primary"] {min-height:2.7rem;font-weight:650}
.st-key-finder_filters summary p,.st-key-finder_filters [data-testid="stWidgetLabel"] p {
    font-size:1rem;font-weight:600;color:#142c3b}
:is(.st-key-finder_filters,.st-key-finder_order) summary:not(details details summary) p {
    font-size:1.5rem;line-height:1.25;font-weight:700}
.st-key-finder_filters details:not([open]) > summary:not(details details summary) p {white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.st-key-finder_filters summary:not(details details summary) [data-testid="stMarkdownContainer"] {min-width:0;overflow:hidden}
.st-key-finder_filters [data-testid="stSliderThumbValue"],
.st-key-finder_filters [data-testid="stSliderTickBar"] div {color:#365468;font-size:.95rem}
.st-key-filter_actions [data-testid="stCaptionContainer"] p {font-size:.95rem;color:#142c3b;font-weight:600}
.st-key-active_college_filters button {border-radius:999px;background:#193b39;color:#bdf9e9}
.st-key-explore_map h3 {padding-block:.35rem}
.st-key-map_view_mode [role="radiogroup"] {display:inline-flex;gap:4px;border:1px solid #9dbbc9;
    border-radius:10px;background:#f5fafc;padding:4px}
.st-key-map_view_mode [role="radiogroup"] label {margin:0;padding:.42rem .95rem;min-width:5.5rem;
    border-radius:7px;font-weight:650}
.st-key-map_view_mode [role="radiogroup"] label:has(:checked) {background:#d2eee6;color:#064d44}
.map-school-heading {display:flex;align-items:center;gap:1rem}
.map-school-heading h3 {padding:0;margin:0;font-size:1.3rem}
.map-school-heading p {margin:2px 0 0;color:#375665}
.map-school-logo {display:grid;place-items:center;width:84px;height:62px;padding:6px;box-sizing:border-box;
    flex:none;border:1px solid #c7dbe4;border-radius:10px;background:#fff;color:#164a48;font-weight:700}
.map-school-logo img {width:auto;height:auto;max-width:100%;max-height:48px;object-fit:contain}
.st-key-atlas_pages {margin-inline:-.35rem}
.st-key-atlas_pages a {min-height:2.6rem;padding:.42rem .6rem}
.st-key-atlas_pages a [data-testid="stMarkdownContainer"] {min-width:0}
.st-key-atlas_pages a p {white-space:normal;line-height:1.25;color:#edf5f3;font-size:1rem;font-weight:650}
.st-key-atlas_pages a[aria-current="page"] {background:#16463d}
.st-key-atlas_pages [data-testid="stCaptionContainer"] p {color:#abc6ca;font-size:.82rem;font-weight:650}
[data-testid="stSidebarHeader"]:has([data-testid="stSidebarLogo"]) {position:relative;min-height:108px;
    margin-inline:-.9rem;padding-inline:.6rem}
[data-testid="stSidebarHeader"]:has([data-testid="stSidebarLogo"]) [data-testid="stSidebarCollapseButton"] {
    position:absolute;top:.4rem;right:.4rem}
[data-testid="stSidebarLogo"] {width:100%;height:96px;max-width:none;
    object-fit:contain;object-position:left center}
[data-testid="stMetric"] {background:#fff;border:1px solid #d8e3de;border-radius:12px;padding:12px 16px}
.college-card {background:#fff;color:#142c3b;border:1px solid #d8e3de;border-radius:16px;overflow:hidden;
    transition:transform .16s ease,box-shadow .16s ease}
.college-card-shortlisted {border-color:#087869}
.college-shortlist-badge {position:absolute;z-index:2;top:12px;right:12px;background:#0d3935;color:#bdf9e9;
    border:1px solid #61ddc1;border-radius:999px;padding:3px 9px;font-size:.78rem;font-weight:650}
@media (hover:hover) and (prefers-reduced-motion:no-preference) {
    .college-card:hover {transform:translateY(-3px);box-shadow:0 8px 24px #2c7b6333}
}
.college-card summary {display:block;cursor:pointer;list-style:none}
.college-card summary::-webkit-details-marker {display:none}
.college-card summary:focus-visible {outline:3px solid #77dfc2;outline-offset:-3px}
.college-card summary:hover .college-name,.college-card a {color:#076b61}
.college-cover {display:block;width:100%;height:160px;position:relative;overflow:hidden;
    background:linear-gradient(115deg,#f5f7f2,#e1ece7);color:#123440}
.college-cover.ucf-colors {background:linear-gradient(115deg,#fff9e9,#ead5a3)}
.college-mark-tile {display:grid;place-items:center;position:absolute;inset:0;z-index:1;
    padding:20px 26px;box-sizing:border-box}
.college-mark-tile .college-mark {display:block;width:min(100%,220px);height:100%;min-width:0;min-height:0;object-fit:contain}
.college-cover .campus-photo {position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0}
.college-cover .campus-photo.is-loaded {opacity:1}
.college-cover:has(.campus-photo.is-loaded) .college-mark-tile {inset:auto auto 10px 12px;width:86px;height:60px;
    padding:6px;background:white;box-shadow:0 2px 8px #112e3640;border-radius:9px}
.college-cover:has(.campus-photo.is-loaded) .college-initials {font-size:.8rem;letter-spacing:.02em}
.college-mark-dark {background:#123440;border-radius:6px;padding:4px;box-sizing:border-box}
.college-initials {font-size:2.35rem;font-weight:750;letter-spacing:.04em;line-height:1}
.college-card-header {display:grid;grid-template-rows:auto 1fr auto;gap:6px;min-height:12rem;padding:15px 17px}
.college-identity {display:grid;align-content:start;gap:.25rem}
.college-tuition {display:flex;flex-wrap:wrap;align-items:baseline;gap:.3rem .45rem;
    margin:.35rem 0 .2rem;color:#375665;font-size:.84rem;line-height:1.35}
.college-tuition strong {color:#104d43;font-size:1.15rem;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.college-tuition-missing {color:#536574}
.college-rank-badge {position:absolute;z-index:2;top:10px;left:10px;border-radius:8px;
    padding:.24rem .48rem;background:#073f39;color:white;font-size:1.05rem;font-weight:750;line-height:1.2}
.college-card-ranked .college-card-header {display:flex;flex-direction:column;gap:.55rem}
.college-card-ranked .college-chips {min-height:0;margin:0}
.college-score-row {display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}
.college-fit {display:inline-flex;align-items:baseline;gap:.35rem;border-radius:8px;padding:.26rem .55rem;
    background:#0c5049;color:white;font-size:.85rem;font-weight:650}
.college-fit strong {font-size:1.55rem;line-height:1.1;font-variant-numeric:tabular-nums}
.college-close-tag {display:inline-flex;align-items:center;border-radius:999px;border:1px solid #8abcb4;
    background:#e3f2ee;color:#174b44;font-size:.76rem;font-weight:650;padding:.13rem .44rem}
.college-fit-note {font-size:.88rem;line-height:1.35;color:#375665}
.college-score-block {display:grid;align-content:start;gap:.25rem}
.college-stat-heading {display:block;font-weight:700;font-size:.98rem;color:#173d48}
.college-fit-explanation {display:grid;gap:.25rem;line-height:1.42;font-size:.94rem}
.college-rank-reason {border-left:3px solid #77b8a9;padding-left:.55rem;color:#254b49}
.college-stat-list {display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.2rem .6rem;
    align-items:baseline;margin:.2rem 0;padding:.55rem 0;border-block:1px solid #c9dce4;
    font-size:.92rem;line-height:1.4}
.college-stat-list strong {text-align:right;font-variant-numeric:tabular-nums}
.college-card .missing-value {color:#536971;text-decoration:none}
.college-priority-bars {display:grid;gap:.42rem}
.college-priority {display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:baseline;
    gap:.12rem .4rem;color:#284958;font-size:.87rem;line-height:1.3}
.college-priority strong {font-variant-numeric:tabular-nums}
.college-bar-track {grid-column:1/-1;overflow:hidden;height:6px;background:#d5e4e9;border-radius:6px}
.college-bar-track > span {height:100%;display:block;border-radius:inherit;background:#16786a}
.college-priority-unreported .college-bar-track {background:none;border-top:1px dashed #93abb5;border-radius:0}
.college-name {font-size:1.2rem;font-weight:700;line-height:1.25}
.college-meta {color:#365468;font-size:.95rem}
.college-program {color:#115d57;font-size:.95rem;font-weight:650}
.college-chips {display:flex;gap:6px;flex-wrap:wrap;margin-top:4px;min-height:3.25rem;
    align-content:start;align-items:flex-start}
.st-key-finder_grid[data-testid="stVerticalBlock"] {
    display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,max(265px,calc((100% - 3rem)/4))),1fr));
    align-items:stretch;gap:1rem}
.st-key-finder_grid > * {min-width:0}
.st-key-finder_grid [class*="st-key-school_tile_"] {height:100%}
.st-key-finder_grid [class*="st-key-school_tile_"] > :has(> [data-testid="stHtml"]) {flex:1}
.st-key-finder_grid [data-testid="stHtml"],.st-key-finder_grid .college-card {height:100%}
.st-key-finder_grid [class*="st-key-school_actions_"] {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
    gap:5px;align-items:stretch;width:100%}
.st-key-finder_grid [class*="st-key-school_actions_"] > * {min-width:0}
.st-key-finder_grid [class*="st-key-school_actions_"] [data-testid="stButton"],
.st-key-finder_grid [class*="st-key-school_actions_"] button {width:100%;height:100%}
.st-key-finder_grid [class*="st-key-school_actions_"] button {min-height:2.45rem;padding:.28rem .17rem}
.st-key-finder_grid [class*="st-key-school_actions_"] button p {font-size:.81rem;line-height:1.2;
    overflow-wrap:anywhere;white-space:normal}
/* Share the heights of the card sections across each responsive row. */
@supports (grid-template-rows:subgrid) {
    .st-key-finder_grid:has(.college-card-ranked) {row-gap:0}
    .st-key-finder_grid > [data-testid="stLayoutWrapper"]:has(.college-card-ranked),
    .st-key-finder_grid [class*="st-key-school_tile_"]:has(.college-card-ranked) {
        display:grid;grid-template-rows:subgrid;grid-row:span 11;row-gap:0}
    .st-key-finder_grid [class*="st-key-school_tile_"]:has(.college-card-ranked) {padding-bottom:1rem}
    .st-key-finder_grid [data-testid="stElementContainer"]:has(> [data-testid="stHtml"] > .college-card-ranked),
    .st-key-finder_grid [data-testid="stHtml"]:has(> .college-card-ranked),
    .st-key-finder_grid .college-card-ranked,
    .st-key-finder_grid .college-card-ranked > details {
        display:grid;grid-template-rows:subgrid;grid-row:1/span 9;row-gap:0}
    .st-key-finder_grid .college-card-ranked > details > summary {
        display:grid;grid-template-rows:subgrid;grid-row:1/span 8;row-gap:0}
    .st-key-finder_grid .college-card-ranked > details::details-content {grid-row:9}
    .st-key-finder_grid .college-card-ranked .college-card-header {
        display:grid;grid-template-rows:subgrid;grid-row:2/span 7;gap:0;align-items:start}
    .college-card-ranked .college-card-header > * + * {margin-top:.55rem}
    .st-key-finder_grid [class*="st-key-school_tile_"]:has(.college-card-ranked)
        > [data-testid="stLayoutWrapper"] {grid-row:10;padding-top:.35rem}
}
.college-chip {background:#d8eee9;color:#155b4f;font-size:.9rem;line-height:1.2;font-weight:600;padding:3px 9px;border-radius:999px}
.college-details-label {color:#076b61;font-size:.92rem;font-weight:600;margin-top:4px}
.college-card details[open] .college-details-label-closed,
.college-card details:not([open]) .college-details-label-open {display:none}
.college-details {border-top:1px solid #c5dce7;padding:12px 16px 16px}
.college-details dl {display:grid;grid-template-columns:1fr auto;gap:8px 12px;margin:0 0 10px;font-size:.86rem}
.college-details dd {font-weight:600;margin:0;text-align:right}
.college-details p {margin:8px 0 0;font-size:.83rem}
.college-details .program-list {margin:.75rem 0;color:#115d57}
.college-details .program-list summary {text-decoration:underline;font-weight:650}
.st-key-compare_notes [data-testid="stCaptionContainer"] p {color:#365468}
[class*="st-key-compare_chart_"][data-testid="stVerticalBlock"] {
    background:#fff;border:1px solid #c9dce4;border-radius:10px;padding:.85rem}
.compare-scroll {width:100%;max-width:100%;overflow-x:auto;border-radius:10px}
.compare-table {border-collapse:separate;border-spacing:0;width:100%;min-width:var(--compare-width,540px);background:#fff;color:#142c3b;font-size:1rem}
.compare-table th,.compare-table td {text-align:left;padding:.65rem .85rem;border:1px solid #c9dce4;color:#142c3b}
.compare-table thead th {vertical-align:bottom;min-width:145px;font-size:1.08rem;line-height:1.25}
.compare-table thead th:first-child,.compare-table th[scope="row"] {
    position:sticky;left:0;z-index:1;background:#f4fafd;min-width:145px;max-width:190px;
    box-shadow:2px 0 0 #a9c0cb}
.compare-color {display:inline-block;width:.9em;height:.9em;border-radius:50%;margin-right:.45em;
    vertical-align:-.03em;box-shadow:inset 0 0 0 1px #0003;print-color-adjust:exact}
.compare-table .compare-group th {background:#d9e8ed;color:#204653;font-size:.86rem}
.compare-table .compare-missing {color:#506979;font-size:1rem;font-weight:600}
.compare-table .compare-best {background:#c3eade;font-weight:700}
.compare-direction {margin-left:.45rem;font-size:.72rem;color:#104d40}
.compare-table .compare-benchmark {background:#e5eef2;border-left:2px solid #88a3b1;font-weight:500}
.compare-table thead .compare-benchmark {min-width:140px;white-space:nowrap}
.compare-school-tools {display:flex;align-items:flex-start;justify-content:space-between;gap:.45rem;margin:0 0 .65rem}
.compare-logo {box-sizing:border-box;display:grid;place-items:center;width:100px;height:64px;border-radius:9px;
    border:1px solid #c6d9e2;background:#fff;padding:5px;color:#14343a;font-weight:700}
.compare-logo img {width:100%;height:52px;object-fit:contain;border-radius:4px;box-sizing:border-box}
.compare-logo img.light-mark {background:#193e49;padding:4px}
.compare-remove {display:grid;place-items:center;width:2rem;height:2rem;flex-shrink:0;border:1px solid #a1bcc7;
    background:#fff;color:#345263;border-radius:50%;font:inherit;cursor:pointer}
.compare-remove:hover,.compare-remove:focus-visible {background:#d8eee9;color:#084940;border-color:#076b61}
.compare-priority {display:block;width:fit-content;margin-top:.3rem;font-size:.73rem;font-weight:650;color:#155b4f;
    background:#d8eee9;border-radius:4px;padding:.08rem .35rem}
.st-key-compare_takeaways {background:#fff;border:1px solid #d8e3de;border-radius:12px;padding:.8rem 1rem}
.compare-takeaways {margin:0;padding-left:1.3rem;color:#294758;line-height:1.45}
.compare-takeaways li + li {margin-top:.3rem}
.compare-location {display:block;color:#365468;font-weight:400;font-size:.85rem;margin-top:.28rem}
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
    if kind == "miles":
        return f"{value:,.1f} mi"
    return f"{value:,.0f}"

LABELS = {"tuition_in": "In-state tuition ($)", "tuition_out": "Out-of-state tuition ($)",
          "acceptance": "Acceptance rate", "enrollment": "Undergraduate enrollment",
          "graduation": "Graduation rate (150% of normal time)", "debt": "Median completer debt ($)",
          "earnings": "Median earnings 10 years after entry ($)"}
METRICS = list(LABELS)


MAX_COMPARE = 5
CARD_PAGE_SIZE = 12
CHART_COLORS = ("#55cdb6", "#ffbf73", "#a6afff", "#f898bb", "#b7df77")

CARD_MEASURES = {
    "distance_miles": ("Straight-line distance", "miles"),
    "tuition_in": ("Annual in-state tuition", "money"),
    "tuition_out": ("Annual out-of-state tuition", "money"),
    "graduation": ("Graduation rate", "percent"),
    "earnings": ("Earnings 10 years after entry", "money"),
    "debt": ("Median student debt", "money"),
    "acceptance": ("Acceptance rate", "percent"),
    "enrollment": ("Undergraduate enrollment", "number"),
}


def ranked_card_summary(school, fit):
    missing = '<abbr class="missing-value" title="Not reported" aria-label="Not reported">–</abbr>'
    metrics = []
    priorities = sorted(fit["weights"], key=fit["weights"].get, reverse=True)
    for field in dict.fromkeys([*priorities, "graduation", "earnings"]):
        if field == "distance_miles":
            continue
        label, kind = CARD_MEASURES[field]
        value = school[field]
        shown = display(value, kind) if pd.notna(value) else missing
        metrics.append(f'<span>{label}</span><strong>{shown}</strong>')

    criteria = fit["criteria"]
    bars = []
    for field in priorities:
        label = html.escape(CRITERIA[field][0])
        value = criteria.get(field)
        if value is None:
            bars.append(f'<span class="college-priority college-priority-unreported"><span>{label}</span>'
                        f'{missing}<span class="college-bar-track" aria-hidden="true"></span></span>')
        else:
            bars.append(f'<span class="college-priority"><span>{label}</span><strong>{value:.0f}</strong>'
                        f'<span class="college-bar-track" aria-hidden="true"><span style="width:{value:.4f}%"></span></span></span>')

    score_text = f'{fit["score"]:.0f}' if criteria else "–"
    score_description = f"Fit score {score_text}, relative to your matches" if criteria else "Fit score unavailable"
    coverage = f"Based on {len(criteria)} of {len(bars)} priorities"
    if len(bars) == 1:
        coverage = "Based on one reported priority" if criteria else "No reported priorities"
    close = (f'<span class="college-close-tag" title="{html.escape(fit["close_note"])}" '
             f'role="img" aria-label="{html.escape(fit["close_note"])}">Very close</span>'
             if fit.get("close_note") else "")
    lines = "".join(f'<span>{html.escape(line)}</span>' for line in fit["explanation"].splitlines() if line)
    if fit.get("rank_reason"):
        lines += f'<span class="college-rank-reason">{html.escape(fit["rank_reason"])}</span>'
    measures = (f'<span class="college-score-block"><span class="college-score-row">'
                f'<span class="college-fit" title="Relative to your matches" role="img" aria-label="{score_description}">'
                f'Fit score <strong>{score_text}</strong></span>{close}</span>'
                f'<span class="college-fit-note">{coverage}</span></span>'
                f'<span class="college-priority-bars">{"".join(bars)}</span>'
                f'<span><span class="college-stat-heading">School-wide figures</span>'
                f'<span class="college-stat-list">{"".join(metrics)}</span></span>')
    return measures, f'<span class="college-fit-explanation">{lines}</span>'


def college_card(school, asset, shortlisted=False, matched_programs=(), fit=None, *, details_only=False, zip_code=""):
    name = html.escape(school["name"])
    location = html.escape(school["city"] if pd.notna(school["city"]) and school["city"] else "Florida")
    image = asset.get("data")
    school_id = school["id"]
    photo = campus_photo(school_id)
    background = logo_background(image)
    if image and school_id == "485768":  # Atlantis University's light logo needs a dark tile.
        background = "#123440"
    initials = "".join(word[0] for word in school["name"].split() if len(word) > 2)[:4].upper()
    initials_mark = f'<span class="college-initials" aria-hidden="true">{html.escape(initials)}</span>'
    mark_class = "college-mark college-mark-dark" if background == "#123440" else "college-mark"
    mark = (f'<img class="{mark_class}" src="{html.escape(image)}" alt="" loading="lazy">'
            if background else initials_mark)
    cover = f'<span class="college-mark-tile">{mark}</span>'
    if fit:
        cover += f'<span class="college-rank-badge" aria-label="Rank {fit["rank"]}">#{fit["rank"]}</span>'
    if shortlisted:
        cover += '<span class="college-shortlist-badge">✓ In comparison</span>'
    credit = ""
    if photo:
        url = html.escape(photo["url"])
        alt = html.escape(photo.get("alt") or f'Campus at {school["name"]}')
        cover += f'<img class="campus-photo" src="{url}" alt="{alt}" loading="lazy">'
        credit = campus_photo_credit(photo)
    miles_label = ""
    if pd.notna(miles := school.get("distance_miles")):
        location_suffix = f" from {html.escape(zip_code)}" if zip_code else ""
        miles_label = f'<span class="college-chip" title="Straight-line distance">{miles:.1f} mi{location_suffix}</span>'

    fields = [("School type", school["type"]), ("Predominant degree level", school["level"]), ("Athletics", school["athletics"])]
    for field in METRICS:
        kind = "percent" if field in ("acceptance", "graduation") else "number" if field == "enrollment" else "money"
        fields.append((LABELS[field], display(school[field], kind)))
    details = "".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>" for label, value in fields)
    program_summary = ""
    program_details = ""
    if matched_programs:
        extra = f" (+{len(matched_programs) - 1} more)" if len(matched_programs) > 1 else ""
        program_summary = f'<span class="college-program">{html.escape(matched_programs[0])}{extra}</span>'
        program_items = "".join(f"<li>{html.escape(program)}</li>" for program in matched_programs)
        program_details = f"<p><strong>Matching programs</strong></p><ul>{program_items}</ul>"
    elif school.get("programs_unreported", False):
        program_summary = '<span class="college-meta">Program availability unreported</span>'
    masters_fields = masters_by_school.get(school_id, ())
    if masters_fields:
        items = "".join(f"<li>{html.escape(field)}</li>" for field in masters_fields)
        program_details += (f'<details class="program-list"><summary>View master’s fields of study ({len(masters_fields)})</summary>'
                            f'<ul>{items}</ul><p>Check current program titles, tuition and admission requirements in the school’s graduate catalog.</p></details>')
    website = str(school.get("website") or "").strip()
    site_link = ""
    if website:
        website = website if "://" in website else f"https://{website}"
        parsed = urlsplit(website)
        if parsed.scheme in ("http", "https") and parsed.hostname:
            site_link = f'<p><a href="{html.escape(website)}" target="_blank" rel="noopener">Visit school website ↗</a></p>'
    detail_panel = (f'<div class="college-details">{program_details}<span class="college-stat-heading">School-wide figures</span>'
                    f'<dl>{details}</dl>{site_link}{"" if details_only else credit}</div>')
    if details_only:
        return detail_panel
    tuition_amount = school[tuition]
    tuition_line = (f'<span class="college-tuition"><strong>{display(tuition_amount, "money")}</strong>'
                    f'<span>annual {tuition_label.lower()}</span></span>'
                    if pd.notna(tuition_amount) else '<span class="college-tuition college-tuition-missing">Tuition not reported</span>')
    card_class = "college-card college-card-shortlisted" if shortlisted else "college-card"
    fit_summary = narrative = ""
    if fit:
        fit_summary, narrative = ranked_card_summary(school, fit)
        card_class += " college-card-ranked"
        tuition_line = ""
    level_chip = ("" if matched_programs else
                  f'<span class="college-chip">{html.escape(school["level"])}</span>')
    cover_class = "college-cover"
    if school_id == "132903":
        cover_class += " ucf-colors"
    return f'''<article class="{card_class}"><details><summary>
        <span class="{cover_class}">{cover}</span>
        <span class="college-card-header"><span class="college-identity"><span class="college-name">{name}</span>
        <span class="college-meta">{location}</span>{program_summary}{miles_label}{tuition_line}</span>{fit_summary}
        <span class="college-chips"><span class="college-chip">{html.escape(school["type"])}</span>
        {level_chip}</span>{narrative}
        <span><span class="college-details-label college-details-label-closed">View details</span>
        <span class="college-details-label college-details-label-open">Hide details</span></span></span>
        </summary>{detail_panel}</details>
        </article>'''


COMPARE_METRICS = {
    "tuition_in": ("Cost", "Annual in-state tuition", "money", min),
    "tuition_out": ("Cost", "Annual out-of-state tuition", "money", min),
    "debt": ("Cost", "Less student debt", "money", min),
    "acceptance": ("Admissions", "Easier to get into", "percent", None),
    "enrollment": ("Admissions", "Undergraduate enrollment", "number", None),
    "graduation": ("Outcomes", "Higher graduation rate", "percent", max),
    "earnings": ("Outcomes", "Higher earnings after college", "money", max),
    "type": ("School profile", "School type", "text", None),
    "level": ("School profile", "Degree level", "text", None),
    "athletics": ("School profile", "Athletics", "text", None),
}


def comparison_groups(priorities, tuition_field, preset):
    priorities = list(dict.fromkeys(tuition_field if field in TUITION_BASES else field for field in priorities))
    priority_numbers = {field: index for index, field in enumerate(priorities, 1)}
    groups = {}
    for field in dict.fromkeys([*priorities, *COMPARE_METRICS]):
        if field not in COMPARE_METRICS or (field in TUITION_BASES and field != tuition_field):
            continue
        section_name = COMPARE_METRICS[field][0]
        if preset not in ("All metrics", section_name):
            continue
        group = "Your priorities" if field in priority_numbers else section_name
        groups.setdefault(group, []).append(field)
    return groups, priority_numbers


def comparison_takeaways(chosen, priorities, tuition_field, preset):
    groups, _ = comparison_groups(priorities, tuition_field, preset)
    visible = [field for fields in groups.values() for field in fields if field in CARD_MEASURES]
    default_fields = [tuition_field, "graduation", "debt", "earnings"] if preset == "All metrics" else visible
    metrics = list(dict.fromkeys([*groups.get("Your priorities", []), *default_fields]))
    differences, ties, gaps = [], [], []
    for field in metrics:
        label, kind = CARD_MEASURES[field]
        reported = chosen[field].dropna()
        if len(reported) < 2:
            gaps.append(label.lower())
            continue
        low, high = reported.min(), reported.max()
        shown_low, shown_high = display(low, kind), display(high, kind)
        coverage = f" {len(reported)} of {len(chosen)} schools report this figure." if len(chosen) > 2 else ""
        if shown_low == shown_high:
            ties.append(f"{label} is {shown_low} at each school with a reported figure.{coverage}")
        elif len(chosen) == 2:
            lower_first = field in ("tuition_in", "tuition_out", "debt")
            first, second = (reported.idxmin(), reported.idxmax()) if lower_first else (reported.idxmax(), reported.idxmin())
            direction = "lower" if lower_first else "higher"
            differences.append(f"{label} is {direction} at {chosen.at[first, 'name']} "
                               f"({display(reported[first], kind)}) than at {chosen.at[second, 'name']} "
                               f"({display(reported[second], kind)}).")
        else:
            extremes = []
            for value in (low, high):
                names = chosen.loc[reported.index[reported.eq(value)], "name"].tolist()
                extremes.append(f"{display(value, kind)} at {join_phrases(names)}")
            differences.append(f"{label} ranges from {extremes[0]} to {extremes[1]}.{coverage}")
    lines = (differences + ties)[:2 if gaps else 3]
    if gaps:
        lines.append(f"Too few schools report {join_phrases(gaps)} for a comparison.")
    return lines


def comparison_table(chosen, statewide, icons, differences_only, colors, preset, priorities, tuition_field):
    headers = []
    for school_id, school in chosen.iterrows():
        image = icons.get(school_id, {}).get("data")
        background = logo_background(image)
        name = html.escape(school["name"])
        initials = "".join(word[0] for word in school["name"].split() if len(word) > 2)[:4].upper()
        logo = html.escape(initials)
        if background:
            light = ' class="light-mark"' if background != "#ffffff" else ""
            logo = f'<img src="{html.escape(image, quote=True)}"{light} alt="">'
        location = school["city"] if pd.notna(school["city"]) and school["city"] else "Florida"
        headers.append(f'<th scope="col"><div class="compare-school-tools"><span class="compare-logo" aria-hidden="true">{logo}</span>'
                       f'<button type="button" class="compare-remove" data-remove-school="{html.escape(str(school_id), quote=True)}" '
                       f'title="Remove {name} from comparison" aria-label="Remove {name} from comparison">×</button></div>'
                       f'<span class="compare-color" style="background:{colors[school_id]}" aria-hidden="true">&nbsp;</span>'
                       f'{name}<span class="compare-location">'
                       f'{html.escape(location)}</span></th>')
    groups, priority_numbers = comparison_groups(priorities, tuition_field, preset)
    rows = []
    empty_metrics = []
    for group, fields in groups.items():
        group_rows = []
        for field in fields:
            _, label, kind, best = COMPARE_METRICS[field]
            values = chosen[field].tolist()
            if field == "athletics" and all(value == "Not verified" for value in values):
                continue
            reported = [v for v in values if pd.notna(v)]
            if not reported:
                empty_metrics.append(CARD_MEASURES[field][0] if field in CARD_MEASURES else label)
                continue
            shown = [str(v) if kind == "text" else display(v, kind) for v in values]
            if differences_only and len(set(shown)) == 1:
                continue
            winner = best(reported) if best and len(reported) >= 2 and min(reported) != max(reported) else None
            cells = []
            for value, rendered in zip(values, shown):
                is_best = winner is not None and value == winner
                css = ' class="compare-best"' if is_best else ""
                missing = "Not verified" if field == "athletics" and value == "Not verified" else ""
                if pd.isna(value):
                    missing = "Not reported"
                cell = (f'<span class="compare-missing" title="{missing}" aria-label="{missing}">–</span>'
                        if missing else html.escape(rendered))
                if is_best:
                    direction, description = ("▼", "Lowest reported value") if best is min else ("▲", "Highest reported value")
                    cell += f'<span class="compare-direction" title="{description}" aria-label="{description}">{direction}</span>'
                cells.append(f"<td{css}>{cell}</td>")
            observed = statewide[field].dropna()
            benchmark = display(observed.median(), kind) if kind != "text" and not observed.empty else "—"
            definition = PRIORITY_HELP.get(field)
            label_help = f' title="{html.escape(definition, quote=True)}"' if definition else ""
            priority = f'<span class="compare-priority">Priority {priority_numbers[field]}</span>' if field in priority_numbers else ""
            group_rows.append(f'<tr><th scope="row"{label_help}>{html.escape(label)}{priority}</th>{"".join(cells)}'
                              f'<td class="compare-benchmark">{benchmark}</td></tr>')
        if group_rows:
            rows.append(f'<tr class="compare-group"><th colspan="{len(chosen) + 2}">{group}</th></tr>')
            rows.extend(group_rows)
    if not rows:
        return "", empty_metrics
    return (f'<div class="compare-scroll" tabindex="0" role="region" aria-label="School comparison">'
            f'<table class="compare-table" style="--compare-width:{max(540, 150 + 155 * (len(chosen) + 1))}px"><thead>'
            f'<tr><th scope="col">Metric</th>{"".join(headers)}'
            f'<th scope="col" class="compare-benchmark">Florida median</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>',
            empty_metrics)


def comparison_chart(chosen, statewide, labels, colors, fields, differences_only):
    metrics = []
    single_reports = []
    for field in fields:
        label, kind = CARD_MEASURES[field]
        reported = chosen[field].dropna()
        if len(reported) >= 2:
            if differences_only and len(reported) == len(chosen) and len({display(v, kind) for v in reported}) == 1:
                continue
            metrics.append((field, label))
        elif len(reported) == 1:
            school = labels[reported.index[0]]
            value = display(reported.iloc[0], kind)
            single_reports.append(f"Only {school} has reported {label.lower()} ({value}).")
    if not metrics:
        return None, single_reports

    horizontal = len(chosen) == MAX_COMPARE
    panels = [(field, index if horizontal else 1, 1 if horizontal else index)
              for index, (field, _) in enumerate(metrics, start=1)]
    chart = make_subplots(rows=len(metrics) if horizontal else 1, cols=1 if horizontal else len(metrics),
                          subplot_titles=[label for _, label in metrics], horizontal_spacing=.16,
                          vertical_spacing=.21)
    missing = []
    for rank, (school_id, school) in enumerate(chosen.iterrows()):
        absent = [label.lower() for field, label in metrics if pd.isna(school[field])]
        name = labels[school_id]
        if absent:
            missing.append(f"{name}: {' and '.join(absent)} not reported")
        in_legend = False
        for field, row, column in panels:
            amount = school[field]
            if pd.isna(amount):
                chart.add_annotation(x=0 if horizontal else rank, y=rank if horizontal else 0,
                                     xshift=16 if horizontal else 0, yshift=0 if horizontal else 12,
                                     text="n/a", showarrow=False, font=dict(size=16, color="#365468"),
                                     row=row, col=column)
                continue
            kind = CARD_MEASURES[field][1]
            value_label = display(amount, kind)
            if kind == "money" and amount >= 1000:
                value_label = f"${amount / 1000:.1f}".removesuffix(".0") + "k"
            chart.add_trace(go.Bar(name=name, x=[amount if horizontal else rank], y=[rank if horizontal else amount],
                                   orientation="h" if horizontal else "v", width=.65, marker_color=colors[school_id],
                                   marker_line=dict(width=1, color="#536d79"),
                                   text=[value_label], textposition="inside" if amount > 0 else "outside",
                                   insidetextanchor="end", insidetextfont=dict(size=20, color="#102324"),
                                   outsidetextfont=dict(size=20, color="#142c3b"), cliponaxis=False,
                                   legendgroup=school_id, legendrank=rank, showlegend=not in_legend,
                                   customdata=[display(amount, kind)],
                                   hovertemplate="%{fullData.name}<br>%{customdata}<extra></extra>"),
                            row=row, col=column)
            in_legend = True
    for field, row, column in panels:
        observed = statewide[field].dropna()
        peak = chosen[field].max()
        upper = 0 if pd.isna(peak) else peak
        if not observed.empty:
            median = observed.median()
            upper = max(upper, median)
            line_style = dict(row=row, col=column, exclude_empty_subplots=False,
                              layer="below", line_dash="dash", line_color="#426577", line_width=2)
            if horizontal:
                chart.add_vline(x=median, **line_style)
            else:
                chart.add_hline(y=median, **line_style)
        rank_axis = chart.update_yaxes if horizontal else chart.update_xaxes
        value_axis = chart.update_xaxes if horizontal else chart.update_yaxes
        ranks = [-.65, len(chosen) - .35]
        rank_axis(range=ranks[::-1] if horizontal else ranks, showticklabels=False, row=row, col=column)
        kind = CARD_MEASURES[field][1]
        axis_max = min(1, max(.1, upper * 1.28)) if kind == "percent" else max(1, upper * 1.28)
        value_axis(tickprefix="$" if kind == "money" else "", tickformat={"money": "~s", "percent": ".0%", "number": ",d"}[kind],
                   tickfont_size=17, range=[0, axis_max], row=row, col=column)
    chart.update_annotations(selector=dict(showarrow=False, yref="paper"), font_size=20)
    chart.update_layout(template="plotly_white", paper_bgcolor="#fff", plot_bgcolor="#fff",
                        height=620 if horizontal and len(metrics) == 2 else 470,
                        margin=dict(l=70, r=25, t=55, b=135), font=dict(size=18, color="#142c3b"),
                        legend=dict(font=dict(size=18), orientation="h", traceorder="normal", yanchor="top", y=-.12))
    if missing:
        single_reports.append("; ".join(missing) + ".")
    return chart, single_reports

def render_data_settings(snapshot):
    if st.session_state.pop("atlas_data_refreshed", False):
        st.success("College data refreshed.")
    with st.expander("Data and image settings", expanded=snapshot is None):
        score_key = st.text_input("College Scorecard API key", value=secret("COLLEGE_SCORECARD_API_KEY", "DEMO_KEY"),
                                  type="password")
        st.caption("DEMO_KEY is rate-limited. Get your own key at api.data.gov/signup/.")
        if st.button("Fetch / refresh Florida colleges", type="primary"):
            try:
                with st.spinner("Fetching every page and saving a snapshot…"):
                    fetch_colleges(score_key)
            except Exception as exc:
                st.error(str(exc) if isinstance(exc, RuntimeError)
                         else "Data request failed. Check your connection and try again.")
            else:
                st.session_state.atlas_data_refreshed = True
                st.rerun()
        if snapshot is not None:
            if st.button("Load school images"):
                with st.spinner("Finding school logos and website icons…"):
                    refresh_icons(snapshot["records"])
                st.rerun()
            st.caption("Pins use a school logo when available, then a website icon or graduation cap.")


try:
    snapshot = load_snapshot()
except (OSError, ValueError):
    snapshot = None
    st.error("The saved snapshot could not be read. Refresh data to replace it.")
if snapshot is None:
    st.title("Florida Campus Atlas")
    st.info("Use Fetch / refresh Florida colleges below to get started.")
    st.markdown("""The app includes a logo map, school comparisons, EDA, and direct LLM API summaries.

Only operating Florida institutions whose predominant award is an associate or bachelor’s degree are included. High schools, certificate-only providers, and graduate-only institutions are outside this version’s scope.

**School images:** after fetching data, use the image loader to find logos and website icons.

**Athletics:** NCAA I/II/III, NAIA, NJCAA, and other affiliations can be entered with sources in the same file. Membership is never guessed from the school’s name.""")
    render_data_settings(snapshot)
    st.stop()

frame = pd.DataFrame(snapshot["records"])
try:
    program_catalog = load_program_catalog()
except (OSError, ValueError):
    program_catalog = None
program_catalog = program_catalog or {"schools": {}, "programs": {}, "levels": {}}
programs_by_school = program_catalog["schools"]
program_names = program_catalog["programs"]
program_levels = program_catalog["levels"]
available_programs = sorted(
    {program for school_id in frame["id"] for program in programs_by_school.get(school_id, {})},
    key=lambda code: program_names[code].casefold(),
)
masters_by_school = {}
for school_id in frame["id"]:
    subjects = [program_names[code] for code, awards in programs_by_school.get(school_id, {}).items()
                if MASTERS_CREDENTIAL in awards]
    if subjects:
        masters_by_school[school_id] = sorted(subjects, key=str.casefold)
for column in NUMERIC:
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
frame["enrollment"] = frame["enrollment"].mask(frame["enrollment"].eq(0))
reviewed = overrides()
affiliations = frame["id"].map(lambda key: (reviewed.get(key, {}).get("athletics") or "Not verified").split("|"))
frame["athletics"] = affiliations.str.join(" · ")
division_counts = affiliations.explode().value_counts()
frame["school"] = frame["name"] + " · " + frame["city"].fillna("") + " [" + frame["id"] + "]"
icons = cached_icons()
schools = frame.sort_values("name", key=lambda names: names.str.casefold()).set_index("id", drop=False)
duplicate_names = schools["name"].duplicated(keep=False)
school_labels = schools["name"].where(~duplicate_names, schools["name"] + " · " + schools["city"].fillna("")).to_dict()
SECTIONS = {"Home": "home", "Finder": "finder", "Map": "map", "Compare": "compare",
            "AI": "ai", "Data": "data"}
PAGE_GROUPS = {"Find": ("Finder", "AI"), "Explore": ("Map", "Compare", "Data"), "Info": ("Home",)}
PAGE_ICONS = {"Finder": ":material/school:", "AI": ":material/chat_bubble_outline:",
              "Map": ":material/map:", "Compare": ":material/compare_arrows:",
              "Data": ":material/bar_chart:", "Home": ":material/info:"}


def update_shortlist(ids):
    st.session_state.comparison_ids = list(dict.fromkeys(value for value in ids if value in schools.index))[:MAX_COMPARE]


def toggle_school(school_id):
    ids = st.session_state.comparison_ids
    if school_id in ids:
        update_shortlist([value for value in ids if value != school_id])
    elif len(ids) < MAX_COMPARE:
        update_shortlist([*ids, school_id])


update_shortlist(st.session_state.get("comparison_ids", st.query_params.get("schools", "").split(",")))
selected_ids = st.session_state.comparison_ids
nav_names = {"Home": "About this app", "Finder": "Find a School", "Compare": f"Compare Schools · {len(selected_ids)}",
             "Map": "Interactive Map", "AI": "Ask AI", "Data": "Data & Sources"}
routes = {name: st.Page(partial(st.session_state.__setitem__, "main_section", name),
                        title=nav_names[name], url_path=slug, default=name == "Finder")
          for name, slug in SECTIONS.items()}
page = st.navigation({group: [routes[name] for name in names] for group, names in PAGE_GROUPS.items()},
                     position="hidden")
current_query = {key: st.query_params.get_all(key) for key in st.query_params}
query = {key: values for key, values in current_query.items() if key not in ("view", "schools", "priorities", "tuition")}
if selected_ids:
    query["schools"] = [",".join(selected_ids)]
# Older shared links specify the page in ?view=. Accept them on any route.
legacy_page = next((name for name, slug in SECTIONS.items() if slug == st.query_params.get("view")), None)
destination = st.session_state.pop("requested_section", None) or legacy_page
if destination in routes and page.url_path != routes[destination].url_path:
    route_query = dict(query)
    if destination == "Compare":
        route_query.update({k: current_query[k] for k in ("priorities", "tuition") if k in current_query})
    st.switch_page(routes[destination], query_params=route_query)
page.run()
section = st.session_state.main_section
if section == "Compare":
    if not st.session_state.get("comparison_link_loaded"):
        raw_fields = st.query_params.get("priorities", "").split(",")
        fields = ["tuition_in" if field == "tuition_out" else field for field in raw_fields if field in CRITERIA]
        if fields:
            st.session_state.fit_priorities = list(dict.fromkeys(fields))[:5]
        if st.query_params.get("tuition") in ("in", "out"):
            st.session_state.setdefault("college_filters", {})["filter_tuition_basis"] = (
                "tuition_out" if st.query_params["tuition"] == "out" else "tuition_in")
        st.session_state.comparison_link_loaded = True
    if fields := st.session_state.get("fit_priorities", []):
        query["priorities"] = [",".join(fields)]
    if st.session_state.get("college_filters", {}).get("filter_tuition_basis") == "tuition_out":
        query["tuition"] = ["out"]
if section != "Map":
    st.session_state.pop("map_comparison_ids", None)
if query != current_query:
    st.query_params.from_dict(query)
# Carry the shortlist in each destination URL, including the browser history entry.
with st.sidebar.container(key="atlas_pages", gap="small"):
    for group, names in PAGE_GROUPS.items():
        st.caption(group)
        for name in names:
            nav_query = query if name == "Compare" else {k: v for k, v in query.items() if k not in ("priorities", "tuition")}
            st.page_link(routes[name], label=nav_names[name], icon=PAGE_ICONS[name], query_params=nav_query, width="stretch")
# Streamlit updates the address on reruns. Back and Forward need a fresh
# session when they restore a different page or shortlist.
history_key = html.escape(urlencode(query, doseq=True), quote=True)
st.html(f"""<span id="atlas-history" data-view="{SECTIONS[section]}" data-query="{history_key}" hidden></span>
<script>
(() => {{
const atlasPage = document.getElementById("atlas-history").dataset.view;
if (window.atlasPage && window.atlasPage !== atlasPage) {{
    requestAnimationFrame(() => {{
        document.querySelector('[data-testid="stMain"]')?.scrollTo(0, 0);
        window.scrollTo(0, 0);
    }});
}}
window.atlasPage = atlasPage;
if (!window.atlasHistoryListener) {{
    window.atlasHistoryListener = true;
    document.addEventListener("click", event => {{
        if (!(event.target instanceof Element) || !event.target.closest(".finder-results-link")) return;
        const results = document.getElementById("finder-best-matches");
        if (!results) return;
        event.preventDefault();
        results.scrollIntoView({{block: "start"}});
    }});
    window.addEventListener("popstate", () => {{
        const rendered = document.getElementById("atlas-history");
        if (!rendered) return;
        const previous = new URLSearchParams(rendered.dataset.query);
        const current = new URLSearchParams(window.location.search);
        if (["view", "schools", "priorities", "tuition"].some(key => (current.get(key) || "") !== previous.get(key))) {{
            window.location.reload();
        }}
    }});
}}
}})();
</script>""", unsafe_allow_javascript=True)

if section == "Home":
    with st.container(key="atlas_header", gap=None):
        st.title("Florida Campus Atlas")
        st.image(ATLAS_LOGO, width="stretch")
    st.subheader("About this app")
    st.markdown("Florida Campus Atlas helps students and families build a shortlist of Florida colleges. "
                "Start with the major, budget, or distance that matters to you. Compare the schools you find and see where the data is incomplete.")
    st.caption(f"{len(frame):,} eligible Florida schools in the saved U.S. Department of Education "
               f"[College Scorecard snapshot](https://collegescorecard.ed.gov/data/), retrieved {snapshot['fetched_at'][:10]}.")
    st.subheader("Choose what to explore")
    destinations = (
        ("Finder", "Filter schools to see your matches, then rank them if you want a more personalized order."),
        ("Compare", f"Compare up to {MAX_COMPARE} schools side by side and share your shortlist."),
        ("Map", "Enter a ZIP to find nearby campuses and see road miles and estimated drive times."),
        ("AI", "Ask Gemini to explain tradeoffs using the selected schools’ reported figures."),
        ("Data", "Explore distributions, correlations, missing data, and outliers."),
    )
    for destination, description in destinations:
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.button(nav_names[destination].split(" · ")[0], key=f"home_{destination}",
                      on_click=st.session_state.__setitem__, args=("requested_section", destination))
            st.write(description)
    with st.expander("How the fit score works"):
        st.write("Your filters decide which schools appear. Ranking is optional and uses the order of priorities you select.")
        st.write("For each priority, the score is the percentage of reporting schools in your filtered matches that "
                 "the school equals or beats. Schools tied on a measure earn the same points. "
                 "School size scores 100 if it matches your preferred range and 0 otherwise. "
                 "Your first priority has weight 5, your second 4, and so on down to 1 for your fifth. Schools missing your first priority appear after "
                 "schools that report all top priorities.")
        st.write("For example, if you choose tuition first and graduation rate second, a school scoring 90 for tuition "
                 "and 60 for graduation earns (90 × 5 + 60 × 4) ÷ 9, or about 77. Only reported values enter the average.")
    with st.expander("Data sources and coverage"):
        st.write("The College Scorecard API supplies institution records. Separate Scorecard field-of-study files supply program and credential data. "
                 "The app joins these records by school ID and stores the prepared data in local snapshot files.")
        st.write("Tuition covers annual tuition and required fees. Your net price after financial aid can differ. "
                 "Acceptance rate describes past admissions. Graduation uses 150% of normal time. Earnings are "
                 "measured 10 years after entry. Median debt covers completers with reported federal loans.")
        st.write("Metrics can come from different reporting years. The app shows missing figures as unreported and uses reported values in calculations. "
                 "Check current program availability and costs with the school.")
    with st.expander("AI and location privacy"):
        st.write("A Gemini request sends your question and the selected public school figures. Review important claims against the college data.")
        st.write("ZIP lookup runs locally. Drawing a route sends the ZIP-center and campus coordinates to Valhalla. "
                 "Opening Google Maps sends it the ZIP and destination.")
        st.markdown(f"Built with Streamlit, Leaflet, Plotly, and Gemini. [Census ZIP-area coordinates]({CENSUS_SOURCE})")

FILTER_KEYS = ("filter_school_types", "filter_degree_levels", "filter_max_tuition",
               "filter_athletics", "filter_acceptance_range", "filter_graduation_range",
               "filter_enrollment_size", "filter_max_debt", "filter_min_earnings", "filter_programs")
TUITION_BASES = {"tuition_in": "In-state tuition", "tuition_out": "Out-of-state tuition"}
NO_TUITION_LIMIT = "No limit"
saved_filters = st.session_state.setdefault("college_filters", {})
tuition = saved_filters.get("filter_tuition_basis", "tuition_in")
tuition_label = TUITION_BASES[tuition]
reported_tuition = frame[tuition].dropna()
tuition_budgets = set()
if not reported_tuition.empty:
    low, high = math.floor(reported_tuition.min()), math.ceil(reported_tuition.max())
    tuition_budgets.update((low, high))
    tuition_budgets.update(range((low // 1000 + 1) * 1000, high, 1000))
# A student's dollar limit still applies when switching to a different price range.
if isinstance(saved_filters.get("filter_max_tuition"), (int, float)):
    tuition_budgets.add(saved_filters["filter_max_tuition"])
FILTER_DEFAULTS = dict(zip(FILTER_KEYS, ([], [], NO_TUITION_LIMIT, [], (0, 100), (0, 100), "Any size", 100000, 0, [])))
FILTER_DEFAULTS["college_search"] = ""
FILTER_DEFAULTS["filter_tuition_basis"] = "tuition_in"
FILTER_DEFAULTS.update({"filter_zip": "", "filter_radius": "Any distance", "filter_unknown_programs": False,
                        "filter_unknown_acceptance": True, "filter_unknown_tuition": False})
BROWSE_FILTERS = {"college_search", "filter_unknown_acceptance", *FILTER_KEYS[4:9]}
MUST_HAVES = [key for key in FILTER_DEFAULTS if key not in BROWSE_FILTERS]
DEGREE_CREDENTIALS = {"Certificate": "1", "Two-year / community college": "2", "Four-year": "3", "Master’s": MASTERS_CREDENTIAL}


if section != "Finder" and "card_sort" in st.session_state:
    st.session_state.card_sort = st.session_state.card_sort


def reset_card_count():
    st.session_state.visible_cards = CARD_PAGE_SIZE


PRIORITY_SLOTS = ("1st priority", "2nd priority", "3rd priority", "4th priority", "5th priority")


def change_priority(position):
    priorities = list(st.session_state.fit_priorities)
    choice = st.session_state[f"fit_priority_{position + 1}"]
    if choice is None:
        del priorities[position:position + 1]
    elif position >= len(priorities):
        if choice not in priorities:
            priorities.append(choice)
    elif choice in priorities:
        previous_position = priorities.index(choice)
        priorities[position], priorities[previous_position] = priorities[previous_position], priorities[position]
    else:
        priorities[position] = choice
    st.session_state.fit_priorities = priorities
    st.session_state.pop("fit_submitted", None)
    reset_card_count()


def finish_must_haves(must_haves):
    st.session_state.finder_summary = " · ".join(str(label) for _, _, label in must_haves) or "All Florida schools in the atlas"
    st.session_state.finder_filters = False
    st.session_state.scroll_to_matches = True
    reset_card_count()


def remember_fit_size():
    st.session_state.fit_preferred_size = st.session_state.fit_campus_size


def render_fit_priorities(match_count, must_have_signature, filter_priorities):
    priorities = st.session_state.setdefault("fit_priorities", [])
    if must_have_signature:
        st.write("**Your Step 1 filters**")
        st.write(" · ".join(label for _, _, label in must_have_signature))
        st.caption("Your filters decide which schools appear. Ranking orders those schools by differences such as price or distance.")
    available = [*filter_priorities, *(field for field in CRITERIA
                  if field not in filter_priorities and field not in ("tuition_out", "distance_miles"))]
    priorities = [field for field in priorities if field in available]
    st.session_state.fit_priorities = priorities
    st.caption("Put what matters most first. Choose an existing priority in another slot to swap their order.")

    def priority_picker(column, position):
        selected = priorities[position] if position < len(priorities) else None
        key = f"fit_priority_{position + 1}"
        if st.session_state.get(key) != selected:
            st.session_state[key] = selected
        options = available if selected else [field for field in available if field not in priorities]
        definitions = PRIORITY_HELP[tuition if selected == "tuition_in" else selected] if selected else "\n\n".join(
            f"**{CRITERIA[field][0]}.** {PRIORITY_HELP[tuition if field == 'tuition_in' else field]}" for field in options
        )
        column.selectbox(
            PRIORITY_SLOTS[position], options, index=None, key=key,
            format_func=lambda field: CRITERIA[field][0], placeholder="Choose a priority" if position == 0 else "Optional",
            help=f"This choice carries a weight of {5 - position} out of 5.\n\n{definitions}",
            on_change=change_priority, args=(position,),
        )

    visible = min(len(priorities) + 1, len(PRIORITY_SLOTS), len(available))
    with st.container(key="priority_inputs", horizontal=True, gap="small"):
        for position in range(visible):
            priority_picker(st, position)
    if "tuition_in" in priorities and "debt" in priorities:
        st.caption("Tuition is the yearly price. Debt is what graduates borrowed. Choosing both gives cost more weight in your ranking.")
    size = None
    if "enrollment" in priorities:
        previous_size = st.session_state.get("fit_preferred_size")
        if st.session_state.get("fit_campus_size") != previous_size:
            st.session_state.fit_campus_size = previous_size
        size = st.selectbox(
            "Preferred campus size", list(SIZE_RANGES), index=None, key="fit_campus_size",
            format_func=lambda label: label.split(" (", 1)[0], placeholder="Choose a size",
            help="Small has fewer than 2,000 undergraduates. Medium has 2,000–9,999. Large has 10,000 or more.",
            on_change=remember_fit_size,
        )
    signature = (tuple(priorities), size, must_have_signature)
    if st.session_state.get("fit_submitted") != signature:
        st.session_state.pop("fit_submitted", None)
    can_submit = match_count > 0 and bool(priorities) and ("enrollment" not in priorities or size is not None)
    if not priorities:
        st.caption("Choose a first priority to see your best matches.")
    elif "enrollment" in priorities and size is None:
        st.caption("Choose a campus size to see your best matches.")
    submitted = st.button("Rank matching schools", type="primary", key="find_best_matches",
                          disabled=not can_submit, on_click=finish_must_haves, args=(must_have_signature,))
    if submitted and can_submit:
        st.session_state.fit_submitted = signature
    if can_submit and st.session_state.get("fit_submitted") == signature:
        return {tuition if field == "tuition_in" else field: 5 - index for index, field in enumerate(priorities)}, size
    return {}, None


def filter_widget_key(key):
    return key if section == "Finder" else f"{section.lower()}_{key}"


def store_filter(key, value):
    if key in MUST_HAVES:
        st.session_state.pop("finder_summary", None)
        if section == "Finder":
            st.session_state.finder_filters = True
    if value == FILTER_DEFAULTS[key]:
        saved_filters.pop(key, None)
    else:
        saved_filters[key] = value


def set_filter(key, value):
    store_filter(key, value)
    st.session_state[filter_widget_key(key)] = value


def remember_filter(key):
    if st.session_state.main_section == section:
        store_filter(key, st.session_state[filter_widget_key(key)])
        reset_card_count()


def reset_filters():
    keys = MUST_HAVES if section == "Finder" else FILTER_DEFAULTS.keys() - {"college_search"}
    for key in keys:
        if key in saved_filters:
            set_filter(key, FILTER_DEFAULTS[key])
    reset_card_count()


def clear_search_and_filters():
    if section != "Finder":
        set_filter("college_search", FILTER_DEFAULTS["college_search"])
    reset_filters()


def remove_filter(key, value=None):
    if value is None:
        set_filter(key, FILTER_DEFAULTS[key])
    else:
        remaining = [selected for selected in saved_filters.get(key, []) if selected != value]
        set_filter(key, remaining)
    reset_card_count()


def clear_map_zip():
    set_filter("filter_zip", "")
    set_filter("filter_radius", "Any distance")
    reset_card_count()


def render_zip_location(zip_slot, radius_slot=None, clear_slot=None):
    zip_code = zip_slot.text_input("ZIP code", max_chars=5, placeholder="Enter your ZIP code",
                                   key=filter_widget_key("filter_zip"), on_change=remember_filter,
                                   args=("filter_zip",)).strip()
    if clear_slot is not None:
        clear_slot.button("Clear ZIP", on_click=clear_map_zip, disabled=not zip_code)
    radius = "Any distance"
    if radius_slot is not None:
        radius = radius_slot.selectbox("Distance from ZIP (straight-line)",
                                       ["Any distance", "25 miles", "50 miles", "100 miles"],
                                       index=None, key=filter_widget_key("filter_radius"),
                                       on_change=remember_filter, args=("filter_radius",),
                                       help="Driving can take longer, especially across water.")
    origin = None
    if zip_code and not re.fullmatch(r"[0-9]{5}", zip_code):
        st.warning("Enter a five-digit ZIP code, such as 34243.")
    elif zip_code:
        try:
            origin = zip_centroids().get(zip_code)
            if origin is None:
                st.warning(f"ZIP {zip_code} was not found in the Census ZIP-area data.")
            elif not 320 <= int(zip_code[:3]) <= 349:
                st.caption("This ZIP is outside Florida. Results still show Florida schools.")
        except OSError:
            st.warning("The ZIP lookup data could not be loaded.")
    elif radius != "Any distance":
        st.caption("Enter a ZIP code to apply the distance filter.")
    return zip_code, origin, radius


def relax_must_haves(keys):
    for key in keys:
        set_filter(key, FILTER_DEFAULTS[key])
    reset_card_count()


def matching_must_haves(choices, *, keep_unreported_tuition):
    """Use the same eligibility rules for the live results and filter suggestions."""
    mask = pd.Series(True, index=frame.index)
    majors = choices.get("filter_programs", [])
    degrees = choices.get("filter_degree_levels", [])
    matches = program_matches(program_catalog, majors, {DEGREE_CREDENTIALS[level] for level in degrees})
    if majors:
        mask &= frame["id"].isin(matches) | (include_unknown_programs & ~reported_programs)
    else:
        # Without a major, the degree picker offers only school-level choices.
        degrees = [level for level in degrees if level in school_levels]
        if degrees:
            degree_match = frame["level"].isin(degrees)
            if "Master’s" in degrees:
                degree_match |= frame["id"].isin(masters_by_school)
            mask &= degree_match
    if choices.get("filter_school_types"):
        mask &= frame["type"].isin(choices["filter_school_types"])
    if choices.get("filter_athletics"):
        divisions = set(choices["filter_athletics"])
        mask &= affiliations.map(lambda values: not divisions.isdisjoint(values))
    if choices.get("filter_max_tuition", NO_TUITION_LIMIT) != NO_TUITION_LIMIT:
        mask &= frame[tuition].le(choices["filter_max_tuition"]) | (keep_unreported_tuition & frame[tuition].isna())
    if choices.get("filter_radius", "Any distance") != "Any distance" and origin:
        mask &= frame["distance_miles"].le(int(choices["filter_radius"].split()[0]))
    return mask, matches


def suggest_broader_matches(choices, current_matches):
    """Try the fewest changes first, preserving selected degree and subject on ties."""
    labels = {"filter_school_types": "allow any school type", "filter_athletics": "allow any athletics division",
              "filter_max_tuition": "remove the tuition cap", "filter_radius": "include any distance",
              "filter_degree_levels": "allow any degree level", "filter_programs": "include all majors"}
    if len(choices.get("filter_school_types", [])) == 1:
        labels["filter_school_types"] = f"remove the {choices['filter_school_types'][0]} requirement"
    for number in range(1, len(choices) + 1):
        candidates = []
        for keys in combinations(choices, number):
            remaining = {key: value for key, value in choices.items() if key not in keys}
            mask, _ = matching_must_haves(remaining, keep_unreported_tuition=include_unknown_tuition)
            predicted = int(mask.sum())
            if predicted > len(current_matches) and mask.loc[current_matches.index].all():
                candidates.append((keys, predicted))
        if candidates:
            # Prefer reaching five results, then the closest count to five.
            keys, predicted = min(candidates, key=lambda item: (
                item[1] < 5, abs(item[1] - 5), "filter_programs" in item[0], "filter_degree_levels" in item[0]))
            action = " and ".join(labels[key] for key in keys)
            noun = "school" if predicted == 1 else "schools"
            st.button(f"Show {predicted:,} {noun} · {action}", key="broaden_matches",
                      on_click=relax_must_haves, args=(keys,))
            return


def show_school_on_map(school_id=None, comparison_ids=None):
    if section == "Finder":
        st.session_state.pop("map_comparison_ids", None)
        for key in BROWSE_FILTERS:
            saved_filters.pop(key, None)
    if comparison_ids is not None:
        st.session_state.map_comparison_ids = list(comparison_ids)
    st.session_state.pending_map_focus = school_id
    st.session_state.map_view_mode = "Map"
    st.session_state.requested_section = "Map"


def ask_about_schools(ids, fit_context=None):
    st.session_state.pop("ai_result", None)
    st.session_state.ai_browse_ids = ids
    st.session_state.ai_fit_context = fit_context or {}
    if fit_context:
        question = ("Explain the strengths and tradeoffs of each match in two short lines. "
                    "Use the supplied figures and ranks and say when a school has no fit score.")
    elif len(ids) == 1:
        question = "What should I know about this school's costs and outcomes?"
    else:
        question = "How do these schools compare on costs and outcomes?"
    st.session_state.ai_question = question
    st.session_state.requested_section = "AI"


def score_calculations(results, breakdown, weights):
    panel = st.expander("Check the score calculations", key="fit_score_audit", on_change="rerun")
    if not panel.open:
        return
    panel.caption("Multiply each priority score by its weight. Divide the sum of those weighted points by "
                  "the total weight of the reported priorities. Calculations use full precision.")
    rows = []
    for rank, (_, school) in enumerate(results.iterrows(), 1):
        scores = breakdown[school["id"]]
        reported_weight = sum(weights[field] for field in scores)
        for field, weight in weights.items():
            score = scores.get(field)
            kind = CARD_MEASURES[field][1]
            rows.append({"Rank": rank, "School": school["name"], "Priority": CRITERIA[field][0],
                         "Reported value": display(school[field], kind), "Priority score": score,
                         "Weight": weight, "Weighted points": score * weight if score is not None else None,
                         "Total reported weight": reported_weight, "Fit score": school["fit_score"]})
    panel.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                    column_config={key: st.column_config.NumberColumn(format="%.3f")
                                   for key in ("Priority score", "Weighted points", "Fit score")})


map_view_mode = "Map"
weights, size = {}, None
if section == "Map":
    map_intro = st.container(key="map_intro", gap="small")
    with map_intro.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center", gap="small"):
        st.subheader("Interactive Map", width="content")
        map_view_mode = st.radio("School results view", ["Map", "List"], horizontal=True, key="map_view_mode",
                                 label_visibility="collapsed", width="content")
    if "map_school_mode" not in st.session_state:
        st.session_state.map_school_mode = "Schools I choose" if st.session_state.get("map_comparison_ids") else "Schools matching my filters"
    mode = map_intro.radio("Which schools would you like to see?",
                          ["Schools matching my filters", "Schools I choose"],
                          horizontal=True, key="map_school_mode", label_visibility="collapsed")
comparison_map = section == "Map" and mode == "Schools I choose"
if comparison_map:
    map_intro.caption("Choose up to five schools. Enter your starting ZIP code to compare driving routes.")
    choices = map_intro.multiselect("Schools to compare", frame.sort_values("name")["id"].tolist(),
                                    default=st.session_state.get("map_comparison_ids", selected_ids)[:MAX_COMPARE],
                                    max_selections=MAX_COMPARE,
                                    format_func=school_labels.__getitem__, key="map_picked_schools",
                                    placeholder="Type a school name")
    st.session_state.map_comparison_ids = choices
    if not choices:
        map_intro.info("Choose your first school above to see it on the map.")
        st.stop()
    filtered = frame[frame["id"].isin(choices)].copy()
    count = len(filtered)
    levels, matched_programs_by_school = [], {}
    radius_miles = None
    with st.container(horizontal=True, vertical_alignment="center"):
        st.write(f"Showing {count} selected {'school' if count == 1 else 'schools'}.")
        st.button("Return to all matching schools", on_click=st.session_state.__setitem__,
                  args=("map_school_mode", "Schools matching my filters"))
    zip_key = filter_widget_key("filter_zip")
    if st.session_state.get(zip_key) != saved_filters.get("filter_zip", ""):
        st.session_state[zip_key] = saved_filters.get("filter_zip", "")
    zip_slot, clear_slot = st.columns([3, 1], vertical_alignment="bottom")
    zip_code, origin, _ = render_zip_location(zip_slot, clear_slot=clear_slot)
    if origin:
        filtered["distance_miles"] = [miles_between(origin, lat, lon) for lat, lon in zip(filtered["lat"], filtered["lon"])]
    map_slot = st.container(key="explore_map", gap="xsmall")
elif section in ("Finder", "Map", "Data"):
    if FILTER_KEYS[9] in saved_filters:
        saved_filters[FILTER_KEYS[9]] = [code for code in saved_filters[FILTER_KEYS[9]] if code in available_programs]
    school_levels = sorted(frame["level"].unique())
    if masters_by_school:
        school_levels.append("Master’s")
    level_options = ([level for level, code in DEGREE_CREDENTIALS.items() if code in program_levels]
                     if saved_filters.get(FILTER_KEYS[9]) else school_levels)
    if FILTER_KEYS[1] in saved_filters:
        saved_filters[FILTER_KEYS[1]] = [level for level in saved_filters[FILTER_KEYS[1]] if level in level_options]
    for key, default in FILTER_DEFAULTS.items():
        value = saved_filters.get(key, default)
        widget_key = filter_widget_key(key)
        if st.session_state.get(widget_key) != value:
            st.session_state[widget_key] = value
    if section == "Finder":
        photo = campus_photo("262129")
        background = f'<img src="{html.escape(photo["url"], quote=True)}" alt="">' if photo else ""
        credit = f'<div class="finder-photo-credit">{campus_photo_credit(photo)}</div>' if photo else ""
        st.html(f'<section class="finder-hero" aria-labelledby="finder-title">{background}'
                '<div><h1 id="finder-title">Find a School</h1>'
                '<p>Explore Florida colleges by major, degree, cost, or distance from home. '
                'See matching schools as you filter. Rank the results if you want a more personalized order.</p>'
                '<a class="finder-results-link" href="#finder-best-matches">See matching schools <span aria-hidden="true">↓</span></a>'
                '</div></section>'
                f'{credit}')
        summary = st.session_state.get("finder_summary")
        filter_panel = st.expander(f"Step 1 · **Edit must-haves** · {summary}" if summary else "Step 1 · Set your must-haves",
                                   expanded=summary is None, key="finder_filters", on_change="rerun")
    search = ""
    if section == "Map":
        with map_intro.container(key="map_location", gap="xsmall"):
            if map_view_mode == "Map":
                school_slot, zip_slot, radius_slot, clear_slot = st.columns([3.1, 1.5, 2.4, 1], vertical_alignment="bottom")
                focus_slot = school_slot.empty()
            else:
                zip_slot, radius_slot, clear_slot = st.columns([2, 2, 1], vertical_alignment="bottom")
            zip_code, origin, radius = render_zip_location(zip_slot, radius_slot, clear_slot)
        filter_panel = map_intro.expander("School filters", expanded=False)
        if map_view_mode == "List":
            map_count_slot = map_intro.empty()
        map_slot = map_intro.container(key="explore_map", gap="xsmall")
        active_slot = st.container()
        metrics_slot = st.container()
    elif section == "Data":
        metrics_slot = st.container()
        filter_panel = st.popover("Filters")
    with filter_panel:
        if section != "Finder":
            if section == "Data":
                search = st.text_input("School or city", key=filter_widget_key("college_search"),
                                       on_change=remember_filter, args=("college_search",))
            with st.container(key="filter_actions", horizontal=True, vertical_alignment="center", gap="small"):
                if section == "Data":
                    filter_count = st.empty()
                st.button("Reset filters", on_click=reset_filters, help="Resets these filters and keeps your search.")
        major_slot, level_slot = st.columns([3, 2]) if section != "Data" else (st, st)
        programs = major_slot.multiselect("Programs / majors", available_programs, key=filter_widget_key(FILTER_KEYS[9]),
                                  format_func=program_names.__getitem__, on_change=remember_filter, args=(FILTER_KEYS[9],),
                                  placeholder="Choose a major or leave open",
                                  disabled=not available_programs,
                                  help="Leave empty if you’re undecided. The College Scorecard groups related programs together. Check the school’s website for the exact major and its entry requirements.")
        level_names = {level: credential_label(DEGREE_CREDENTIALS[level], program_levels) if programs else level
                       for level in level_options}
        if programs:
            level_counts = {level: int(frame["id"].isin(program_matches(program_catalog, programs, {DEGREE_CREDENTIALS[level]})).sum())
                            for level in level_options}
        else:
            level_counts = frame["level"].value_counts().to_dict()
            level_counts["Master’s"] = int(frame["id"].isin(masters_by_school).sum())
        levels = level_slot.multiselect("Credential in selected majors" if programs else "Degree level", level_options,
                                        format_func=lambda level: f"{level_names[level]} ({level_counts.get(level, 0)})",
                                        key=filter_widget_key(FILTER_KEYS[1]),
                                        on_change=remember_filter, args=(FILTER_KEYS[1],),
                                        help="A certificate is a credential for completing a focused course of study, often for a specific career skill. It does not award an associate’s or bachelor’s degree. Counts are before other filters.")
        if "Master’s" in levels:
            st.caption("Master’s matches use reported graduate fields. The tuition filter and match scores use undergraduate or institution-level data. Check the graduate catalog for program costs and admissions.")
        reporting_ids = {school_id for school_id, offerings in programs_by_school.items() if offerings}
        reported_programs = frame["id"].isin(reporting_ids)
        include_unknown_programs = False
        if available_programs:
            st.caption(f"Program data covers {int(reported_programs.sum())} of {len(frame)} schools.")
            if programs and not reported_programs.all():
                key = "filter_unknown_programs"
                if section == "Finder":
                    include_unknown_programs = saved_filters.get(key, False)
                else:
                    include_unknown_programs = st.checkbox("Include schools that don’t report programs",
                                                           key=filter_widget_key(key), on_change=remember_filter, args=(key,),
                                                           help="These schools are labeled so you can check the major and degree with the school.")
        else:
            st.caption("Program data is unavailable for this school snapshot.")
        type_slot, division_slot = st.columns(2) if section != "Data" else (st, st)
        type_counts = frame["type"].value_counts()
        types = type_slot.multiselect("School type", sorted(type_counts.index), key=filter_widget_key(FILTER_KEYS[0]),
                                      format_func=lambda name: f"{name} ({type_counts[name]})",
                                      on_change=remember_filter, args=(FILTER_KEYS[0],), help="Counts are before other filters.")
        division_options = ["NCAA Division I", "NCAA Division II", "NCAA Division III", "NAIA", "NJCAA", "NCCAA", "USCAA"]
        division_options += sorted(set(division_counts.index) - set(division_options))
        athletics = division_slot.multiselect("Athletics division / association", division_options, key=filter_widget_key(FILTER_KEYS[3]), on_change=remember_filter, args=(FILTER_KEYS[3],),
                                   format_func=lambda division: f"{division} ({division_counts.get(division, 0)})",
                                   help="Counts are before other filters. Select multiple divisions to match any of them.")
        st.radio("Which tuition should we use?", TUITION_BASES.keys(), horizontal=True,
                 format_func=TUITION_BASES.__getitem__, key=filter_widget_key("filter_tuition_basis"),
                 on_change=remember_filter, args=("filter_tuition_basis",),
                 help="Public colleges usually charge Florida residents a lower rate. Select the rate that applies to you.")
        budget = NO_TUITION_LIMIT
        if tuition_budgets:
            budget = st.select_slider("Maximum yearly tuition", [*sorted(tuition_budgets), NO_TUITION_LIMIT],
                                      format_func=lambda value: value if value == NO_TUITION_LIMIT else f"${value:,}",
                                      key=filter_widget_key(FILTER_KEYS[2]),
                                      on_change=remember_filter, args=(FILTER_KEYS[2],),
                                      help=f"Annual undergraduate {tuition_label.lower()} and required fees before financial aid. No limit also includes schools with unreported tuition.")
        include_unknown_tuition = budget == NO_TUITION_LIMIT
        if budget != NO_TUITION_LIMIT:
            key = "filter_unknown_tuition"
            include_unknown_tuition = st.checkbox("Include schools that don’t report tuition",
                                                 key=filter_widget_key(key), on_change=remember_filter, args=(key,),
                                                 help="Keep schools with an unknown price as possible matches. Check their tuition before deciding whether they fit your budget.")
        tuition_coverage = st.empty()
        acceptance = graduation = (0, 100)
        include_unknown_acceptance = True
        enrollment, debt, earnings = "Any size", 100000, 0
        if section != "Finder":
            acceptance = st.slider("Acceptance rate range (%)", 0, 100, format="%d%%", key=filter_widget_key(FILTER_KEYS[4]),
                                   on_change=remember_filter, args=(FILTER_KEYS[4],))
            key = "filter_unknown_acceptance"
            include_unknown_acceptance = st.checkbox("Include schools that don’t report acceptance rate",
                                                     key=filter_widget_key(key), on_change=remember_filter, args=(key,))
            st.caption(f"{int(frame['acceptance'].notna().sum())} of {len(frame)} schools report an acceptance rate.")
            with st.expander("Outcomes and enrollment"):
                graduation = st.slider("Graduation rate (%)", 0, 100, format="%d%%",
                                       key=filter_widget_key(FILTER_KEYS[5]), on_change=remember_filter, args=(FILTER_KEYS[5],))
                enrollment = st.selectbox("Undergraduate enrollment", ["Any size", *SIZE_RANGES], index=None,
                                          key=filter_widget_key(FILTER_KEYS[6]), on_change=remember_filter, args=(FILTER_KEYS[6],))
                debt = st.slider("Maximum median debt", 0, 100000, step=1000, format="$%,d",
                                 key=filter_widget_key(FILTER_KEYS[7]), on_change=remember_filter, args=(FILTER_KEYS[7],))
                earnings = st.slider("Minimum median earnings", 0, 150000, step=1000, format="$%,d",
                                     key=filter_widget_key(FILTER_KEYS[8]), on_change=remember_filter, args=(FILTER_KEYS[8],))
        if section != "Map":
            with st.expander("Location and distance"):
                zip_code, origin, radius = render_zip_location(st, st)
        if section == "Finder" and any(key in saved_filters for key in MUST_HAVES):
            st.button("Reset must-haves", on_click=reset_filters)

    if section != "Map":
        active_slot = st.container()

    radius_miles = int(radius.split()[0]) if origin and radius != "Any distance" else None
    if origin:
        frame["distance_miles"] = [miles_between(origin, lat, lon) for lat, lon in zip(frame["lat"], frame["lon"])]
    # Put degree and subject last so an equally useful suggestion preserves them.
    must_have_choices = {
        "filter_school_types": types, "filter_athletics": athletics, "filter_max_tuition": budget,
        "filter_radius": radius if origin else "Any distance", "filter_degree_levels": levels, "filter_programs": programs,
    }
    must_have_choices = {k: v for k, v in must_have_choices.items() if v != FILTER_DEFAULTS[k]}
    # Keep schools with unknown prices until we can count how many pass every other filter.
    mask, matched_programs_by_school = matching_must_haves(must_have_choices, keep_unreported_tuition=True)
    if search:
        mask &= (frame["name"].fillna("") + " " + frame["city"].fillna("")).str.contains(search, case=False, regex=False)
    if acceptance != (0, 100) or not include_unknown_acceptance:
        mask &= frame["acceptance"].between(acceptance[0] / 100, acceptance[1] / 100) | (include_unknown_acceptance & frame["acceptance"].isna())
    if graduation != (0, 100):
        mask &= frame["graduation"].between(graduation[0] / 100, graduation[1] / 100)
    if enrollment in SIZE_RANGES:
        low, high = SIZE_RANGES[enrollment]
        mask &= frame["enrollment"].between(low, high, inclusive="left")
    if debt < 100000:
        mask &= frame["debt"].le(debt)
    if earnings:
        mask &= frame["earnings"].ge(earnings)
    unreported_tuition = int((mask & frame[tuition].isna()).sum())
    if not include_unknown_tuition:
        mask &= frame[tuition].notna()
    tuition_note = ""
    if not reported_tuition.empty:
        scope = "Florida median" if section == "Map" else "Median"
        tuition_note = f"{scope} {tuition_label.lower()} is ${reported_tuition.median():,.0f} per year."
    if unreported_tuition and section == "Map":
        effect = "includes" if include_unknown_tuition else "excludes"
        noun = "school" if unreported_tuition == 1 else "schools"
        tuition_note += f" This view {effect} {unreported_tuition:,} {noun} with unreported tuition."
    elif unreported_tuition:
        subject = "1 school matches" if unreported_tuition == 1 else f"{unreported_tuition:,} schools match"
        effect = "Included in results." if include_unknown_tuition else "Hidden by your tuition cap."
        tuition_note += f" {subject} your other filters with no reported {tuition_label.lower()}. {effect}"
    if tuition_note:
        tuition_coverage.caption(tuition_note.strip())
    filtered = frame[mask].copy()
    if include_unknown_programs:
        filtered["programs_unreported"] = ~reported_programs.loc[filtered.index]
    count = len(filtered)
    if section == "Finder":
        with st.container(key="must_have_count"):
            st.write("1 school matches your must-haves" if count == 1 else f"{count:,} schools match your must-haves")
    else:
        if section == "Map":
            count_text = "1 college matches" if count == 1 else f"{count:,} colleges match"
            if map_view_mode == "List":
                map_count_slot.caption(count_text)
            metrics_slot.caption(f"Statistics for these {count:,} {'match' if count == 1 else 'matches'}")
        else:
            filter_count.caption("1 college matches" if count == 1 else f"{count:,} colleges match")
        a, b, c = metrics_slot.columns(3)
        a.metric("Colleges in view", count)
        b.metric(f"Median {tuition_label.lower()}", display(filtered[tuition].median(), "money"))
        c.metric("Median acceptance", display(filtered["acceptance"].median(), "percent"))
        if section == "Map":
            b.caption(f"{filtered[tuition].count():,} of {count:,} report tuition.")
            c.caption(f"{filtered['acceptance'].count():,} of {count:,} report acceptance.")
    active = [(FILTER_KEYS[i], value, value) for i, values in ((0, types), (3, athletics))
              for value in values]
    active.extend((FILTER_KEYS[1], level, level_names[level]) for level in levels)
    active.extend((FILTER_KEYS[9], code, program_names[code]) for code in programs)
    for enabled, key, label in (
        (bool(search), "college_search", f"Search: {search}"),
        (tuition == "tuition_out", "filter_tuition_basis", tuition_label),
        (budget != NO_TUITION_LIMIT, FILTER_KEYS[2], f"Max tuition ${budget:,}" if budget != NO_TUITION_LIMIT else ""),
        (budget != NO_TUITION_LIMIT and include_unknown_tuition, "filter_unknown_tuition", "Include unreported tuition"),
        (acceptance != (0, 100), FILTER_KEYS[4], f"Acceptance {acceptance[0]}–{acceptance[1]}%"),
        (graduation != (0, 100), FILTER_KEYS[5], f"Graduation {graduation[0]}–{graduation[1]}%"),
        (enrollment in SIZE_RANGES, FILTER_KEYS[6], enrollment),
        (include_unknown_programs, "filter_unknown_programs", "Include unreported programs"),
        (not include_unknown_acceptance, "filter_unknown_acceptance", "Reported acceptance only"),
        (debt < 100000, FILTER_KEYS[7], f"Max debt ${debt:,}"),
        (earnings > 0, FILTER_KEYS[8], f"Min earnings ${earnings:,}"),
        (bool(origin), "filter_zip", f"ZIP {zip_code}"),
        (radius_miles is not None, "filter_radius", f"Within {radius}"),
    ):
        if enabled:
            active.append((key, None, label))
    if active:
        with active_slot.container(key="active_college_filters", horizontal=True, vertical_alignment="center", gap="xsmall"):
            st.caption("Active filters", width="content")
            for key, value, label in active:
                st.button(f"{label} ×", key=f"remove_{key}_{value}", help=f"Remove {label}",
                          on_click=remove_filter, args=(key, value))
    if filtered.empty:
        if section == "Finder":
            st.html('<span id="finder-best-matches"></span>')
        if athletics and not any(division_counts.get(division, 0) for division in athletics):
            st.warning("No schools in the atlas have a verified affiliation for " + ", ".join(athletics) + ".")
        else:
            st.warning("No colleges match. Try a broader search or loosen your filters.")
        if section == "Finder":
            suggest_broader_matches(must_have_choices, filtered)
        st.button("Clear must-haves" if section == "Finder" else "Clear search and filters", on_click=clear_search_and_filters)
        if section == "Data":
            render_data_settings(snapshot)
        st.stop()

    if section == "Finder":
        filter_priorities = []
        if budget != NO_TUITION_LIMIT or tuition == "tuition_out":
            filter_priorities.append("tuition_in")
        if origin:
            filter_priorities.append("distance_miles")
        with st.container(key="finder_priorities", gap="small"):
            with st.expander("Step 2 · Rank your matches (optional)", key="finder_order"):
                weights, size = render_fit_priorities(count, tuple(active), filter_priorities)
        if count < 5 and not weights:
            suggest_broader_matches(must_have_choices, filtered)

if section == "Map" and map_view_mode == "Map":
    with map_slot:
        if comparison_map:
            map_controls = st
        else:
            picker = focus_slot
            match_count, map_controls = st.columns([4, 1], vertical_alignment="bottom")
            match_count.caption(count_text)
        mapped = filtered.dropna(subset=["lat", "lon"])
        mapped_ids = mapped.sort_values("name")["id"].tolist()
        if comparison_map:
            focus_id = st.session_state.pop("pending_map_focus", None)
            if focus_id not in mapped_ids:
                focus_id = mapped_ids[0] if len(mapped_ids) == 1 else None
        else:
            if "pending_map_focus" in st.session_state:
                st.session_state.map_school = st.session_state.pop("pending_map_focus")
            if st.session_state.get("map_school") not in mapped_ids:
                st.session_state.map_school = None
            focus_id = picker.selectbox("School", mapped_ids, index=None, placeholder="Type a school name",
                                       format_func=school_labels.__getitem__, key="map_school")
        expanded_map = map_controls.toggle("Expand map", key="expanded_map")
        selected = mapped.loc[mapped["id"].eq(focus_id)].iloc[0] if focus_id else None
        route_key = (zip_code, focus_id, selected["lat"], selected["lon"]) if origin and focus_id else None
        saved_route_key, driving_route = st.session_state.get("map_driving_route", (None, None))
        if saved_route_key != route_key:
            st.session_state.pop("map_driving_route", None)
            driving_route = None
        comparison_routes = []
        if comparison_map and origin and mapped_ids:
            colors = ["#68e6ff", "#ffae52", "#df94ff", "#aeef66", "#ff8095"]
            cache = st.session_state.setdefault("comparison_route_cache", {})
            destinations = mapped.set_index("id")
            draw = st.button("Show driving routes", key="map_draw_routes", type="primary")
            for i, school_id in enumerate(choices):
                if school_id not in destinations.index:
                    continue
                campus = destinations.loc[school_id]
                key = (zip_code, school_id, campus["lat"], campus["lon"])
                if draw and key not in cache:
                    try:
                        with st.spinner(f"Finding the route to {campus['name']}"):
                            cache[key] = shortest_driving_route(origin, (campus["lat"], campus["lon"]))
                    except DrivingRouteError as error:
                        st.warning(f"{campus['name']}: {error}")
                if key in cache:
                    route = cache[key]
                    label = f"{campus['name']} · {route['miles']:.1f} road miles · {round(route['minutes'])} min"
                    comparison_routes.append({"label": label, "color": colors[i], "points": route["points"]})
                    st.html(f'<span style="color:{colors[i]};background:#183340;padding:0 .3em">━</span> {html.escape(label)}')
            st.caption("Each route starts near your ZIP code’s center. Driving times are estimates.")
        elif comparison_map:
            if not origin:
                st.caption("Enter your starting ZIP code above to see driving routes.")
        elif route_key:
            with st.container(horizontal=True, gap="small", vertical_alignment="center"):
                if st.button("Show shortest driving route", key="map_draw_route", type="primary"):
                    if not driving_route:
                        try:
                            with st.spinner("Finding the shortest road route…"):
                                driving_route = shortest_driving_route(origin, (selected["lat"], selected["lon"]))
                            st.session_state.map_driving_route = (route_key, driving_route)
                        except DrivingRouteError as error:
                            st.warning(str(error))
                if driving_route:
                    hours, minutes = divmod(max(1, round(driving_route["minutes"])), 60)
                    duration = f"{hours} hr {minutes} min" if hours else f"{minutes} min"
                    st.markdown(f"**About {duration}** driving · {driving_route['miles']:.1f} road miles")
            st.caption("Starts near your ZIP’s center. Valhalla receives the start and campus coordinates when you request a route. Drive time is an estimate.")
        elif focus_id:
            st.caption("Enter a valid ZIP above to draw a driving route to this school.")
        markers = []
        for _, school in mapped.iterrows():
            asset = icons.get(school["id"], {})
            image = asset.get("data")
            background = logo_background(image)
            name = html.escape(str(school["name"]))
            popup = f'<section class="campus-popup"><h3>{name}</h3>'
            matched_programs = matched_programs_by_school.get(school["id"], ())
            if matched_programs:
                popup += f'<div class="popup-program">{html.escape(matched_programs[0])}</div>'
                if len(matched_programs) > 1:
                    others = "".join(f"<li>{html.escape(label)}</li>" for label in matched_programs[1:])
                    popup += f"<details><summary>More matching programs ({len(matched_programs) - 1})</summary><ul>{others}</ul></details>"
            elif school.get("programs_unreported", False):
                popup += "<p>Program availability unreported</p>"
            popup += f'<dl><dt>{tuition_label}</dt><dd>{display(school[tuition], "money")}</dd>'
            if pd.notna(distance := school.get("distance_miles")):
                popup += f"<dt>From your ZIP</dt><dd>{distance:.1f} mi straight-line</dd>"
            directions = html.escape(driving_url(school, zip_code if origin else ""), quote=True)
            if origin and not comparison_map and school["id"] != focus_id:
                popup += "</dl><p>Choose this school above to draw its route on the map.</p>"
            else:
                popup += "</dl>"
            popup += f'<a href="{directions}" target="_blank" rel="noopener">Get directions</a></section>'
            markers.append({"id": school["id"], "name": school["name"], "lat": school["lat"], "lon": school["lon"], "image": image if background else None,
                            "darkBackground": background == "#123440", "shortlisted": school["id"] in selected_ids,
                            "popup": popup})
        st.iframe(map_html(markers, focus_id, origin, radius_miles, route=driving_route["points"] if driving_route and not comparison_map else None,
                           routes=comparison_routes),
                  height=1080 if expanded_map else 760,
                  alt="Aerial map of Florida with interactive college pins")
        if len(mapped) != len(filtered):
            st.caption(f"{len(filtered) - len(mapped)} school(s) lack coordinates and are available in Find a School.")
        if focus_id:
            asset = icons.get(focus_id, {})
            image = asset.get("data")
            background = logo_background(image)
            name = html.escape(str(selected["name"]))
            mark = (f'<img src="{html.escape(image, quote=True)}" alt="">' if background
                    else html.escape("".join(word[0] for word in selected["name"].split() if len(word) > 2)[:4].upper()))
            location_text = html.escape(selected["city"]) if pd.notna(selected["city"]) else "Florida"
            if pd.notna(distance := selected.get("distance_miles")):
                location_text += f" · {distance:.1f} miles from your ZIP (straight-line)"
            with st.container(border=True, gap="small"):
                st.html(f'<div class="map-school-heading"><span class="map-school-logo" style="background:{background or "#fff"}">'
                        f'{mark}</span><div><h3>{name}</h3><p>{location_text}</p></div></div>')
                with st.container(horizontal=True, gap="small"):
                    st.link_button("Open driving directions in Google Maps", driving_url(selected, zip_code if origin else ""))
                    st.button("Remove from compare" if focus_id in selected_ids else "Add to compare",
                              key="map_shortlist_button", on_click=toggle_school, args=(focus_id,),
                              disabled=len(selected_ids) >= MAX_COMPARE and focus_id not in selected_ids)
                    st.button("Ask AI about this school", key="map_ask_school", on_click=ask_about_schools, args=([focus_id],))
                with st.expander("School details"):
                    st.html(college_card(selected, asset, matched_programs=matched_programs_by_school.get(focus_id, ()),
                                         details_only=True))
    st.button("Browse matching colleges", on_click=st.session_state.__setitem__, args=("map_view_mode", "List"))

if section == "Finder" or (section == "Map" and map_view_mode == "List"):
    st.container(key="explore_results").subheader("Your best matches" if weights else "Matching colleges",
                                                 anchor="finder-best-matches" if section == "Finder" else None)
    if weights and count < 5:
        suggest_broader_matches(must_have_choices, filtered)
    if "Master’s" in levels:
        st.caption("These schools match your master’s program filter. Tuition and outcomes shown are undergraduate or schoolwide figures. Check the graduate program for its own costs and outcomes.")
    breakdown = {}
    fit_by_school = {}
    ai_fit_records = {}
    sorts = {
        "School name: A to Z": ("name_order", True),
        "Tuition: low to high": (tuition, True),
        "Tuition: high to low": (tuition, False),
        "Acceptance rate: low to high": ("acceptance", True),
        "Acceptance rate: high to low": ("acceptance", False),
        "Graduation rate: high to low": ("graduation", False),
        "Graduation rate: low to high": ("graduation", True),
    }
    if weights:
        st.write("Fit scores compare schools only within your matches.")
        with st.expander("How fit scores work"):
            st.write("Each priority bar shows the percentage of matches with data that the school equals or beats. "
                     "The first priority has weight 5, followed by 4, 3, 2, and 1. The fit score averages the available "
                     "bars using those weights. Schools missing your first priority come after schools that report it.")
            if "enrollment" in weights:
                st.write("For school size, a campus in your preferred range earns 100 points. A campus outside it earns 0.")
            st.caption("Very close marks neighboring schools within three displayed points that have the same first-priority coverage.")
        results, breakdown = rank_schools(filtered, frame, weights, size)
        match_stats = match_statistics(results, weights)
        leader = results.iloc[0]
        reversal_explained = False
        close_ranks = {}
        scores = list(results[["fit_score", "fit_priority_covered"]].itertuples(index=False, name=None))
        for rank, ((left, covered), (right, next_covered)) in enumerate(zip(scores, scores[1:]), 1):
            if covered == next_covered and pd.notna(left) and pd.notna(right) and abs(round(left) - round(right)) <= 3:
                close_ranks.setdefault(rank, []).append(rank + 1)
                close_ranks.setdefault(rank + 1, []).append(rank)
        for rank, (_, row) in enumerate(results.iterrows(), 1):
            school_id = row["id"]
            explanation = fit_explanation(row, breakdown[school_id], weights, size, match_stats)
            reason = ""
            if rank > 1 and not reversal_explained:
                reason = rank_reason(leader, row, breakdown, weights)
                reversal_explained = bool(reason)
            neighbors = " and ".join(f"#{neighbor}" for neighbor in close_ranks.get(rank, []))
            fit_by_school[school_id] = {"rank": rank, "score": row["fit_score"], "criteria": breakdown[school_id],
                                        "priority_count": len(weights), "explanation": explanation, "weights": weights,
                                        "rank_reason": reason,
                                        "close_note": f"Very close to {neighbors} (within 3 displayed points)." if neighbors else ""}
            if breakdown[school_id]:
                ai_fit_records[school_id] = {
                    "computed_rank": rank, "match_score": round(float(row["fit_score"]), 1),
                    "explanation": explanation, "rank_reason": reason,
                    "criterion_scores": {CRITERIA[field][0]: value for field, value in breakdown[school_id].items()},
                    "weights": {CRITERIA[field][0]: weight for field, weight in weights.items()},
                    "preferred_size": size,
                    "tuition_basis": tuition_label,
                    "all_top_priorities_reported": bool(row["fit_priority_covered"]),
                }
        top_ids = results["id"].head(3).tolist()
        with st.container(horizontal=True, gap="small"):
            if len(top_ids) >= 2:
                top_query = urlencode({**query, "schools": [",".join(top_ids)],
                                      "priorities": [",".join(st.session_state.fit_priorities)],
                                      "tuition": ["out" if tuition == "tuition_out" else "in"]}, doseq=True)
                st.link_button(f"Compare top {len(top_ids)}", f"./compare?{top_query}", type="primary",
                               help="Open these matches in a new tab. Your current shortlist stays here.")
            if top_ids:
                st.button("Ask AI about the top matches", on_click=ask_about_schools,
                          args=(top_ids, {school_id: ai_fit_records[school_id] for school_id in top_ids
                                          if school_id in ai_fit_records}))
            st.button("View these on the map", on_click=show_school_on_map)
        if str(secret("ATLAS_DEVELOPER_MODE", False)).strip().lower() in {"true", "1", "yes"}:
            score_calculations(results, breakdown, weights)
    else:
        if origin:
            sorts["Distance: nearest first"] = ("distance_miles", True)
        if st.session_state.get("card_sort") not in (None, *sorts):
            st.session_state.pop("card_sort", None)
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="bottom"):
            sort = st.selectbox("Sort matching colleges", sorts, key="card_sort", on_change=reset_card_count, width=280)
            st.button("View these on the map", on_click=show_school_on_map)
        field, ascending = sorts[sort]
        results = filtered.assign(name_order=filtered["name"].str.casefold())
        sort_fields = [field] if field == "name_order" else [field, "name_order"]
        results = results.sort_values(sort_fields, ascending=[ascending] + [True] * (len(sort_fields) - 1),
                                      na_position="last")
    visible_count = st.session_state.setdefault("visible_cards", CARD_PAGE_SIZE)
    shown = results.head(visible_count).to_dict("records")
    full = len(selected_ids) >= MAX_COMPARE
    if full:
        st.caption(f"Compare holds up to {MAX_COMPARE} schools. Remove one to add another.")
    with st.container(key="finder_grid"):
        for school in shown:
            with st.container(key=f"school_tile_{school['id']}", gap="xsmall"):
                school_id = school["id"]
                added = school_id in selected_ids
                matched_programs = matched_programs_by_school.get(school_id, ())
                st.html(college_card(school, icons.get(school_id, {}), added, matched_programs,
                                     fit_by_school.get(school_id), zip_code=zip_code if origin else ""))
                geolocated = pd.notna(school["lat"]) and pd.notna(school["lon"])
                with st.container(key=f"school_actions_{school_id}"):
                    st.button("Remove from compare" if added else "Add to compare", key=f"shortlist_{school_id}",
                              help=school["name"], width="stretch", disabled=full and not added,
                              type="secondary" if added else "primary", on_click=toggle_school, args=(school_id,))
                    st.button("Show on map", key=f"map_school_{school_id}", on_click=show_school_on_map, args=(school_id,),
                              width="stretch", disabled=not geolocated, help=None if geolocated else "This campus has no reported coordinates.")
                    st.button("Ask AI", key=f"ask_school_{school_id}", on_click=ask_about_schools, width="stretch",
                              args=([school_id], {school_id: ai_fit_records[school_id]} if school_id in ai_fit_records else None))
                if origin and geolocated:
                    st.link_button(f"Directions to {school['name']}", driving_url(school, zip_code))
    with st.container(horizontal=True, horizontal_alignment="center", vertical_alignment="center"):
        st.html("""<script>
(() => {
    const showPhoto = img => {
        if (img.matches(".campus-photo") && img.complete && img.naturalWidth > 0) {
            img.classList.add("is-loaded");
        }
    };
    if (!window.atlasPhotoListener) {
        window.atlasPhotoListener = true;
        document.addEventListener("load", event => {
            if (event.target instanceof HTMLImageElement) showPhoto(event.target);
        }, true);
    }
    document.querySelectorAll(".campus-photo").forEach(showPhoto);
})();
</script>""", unsafe_allow_javascript=True)
        st.caption(f"Showing {len(shown)} of {len(results)} matching colleges.")
        if len(results) > visible_count and st.button("Show more", type="primary"):
            st.session_state.visible_cards += CARD_PAGE_SIZE
            st.rerun()
    if weights and st.session_state.pop("scroll_to_matches", False):
        st.html("""<script>
            requestAnimationFrame(() => requestAnimationFrame(() => {
                const heading = document.getElementById("finder-best-matches");
                if (heading) {
                    heading.scrollIntoView({block: "start"});
                }
            }));
        </script>""", unsafe_allow_javascript=True)

if section == "Compare":
    st.subheader("Compare schools")
    def save_comparison():
        update_shortlist(st.session_state.compare_picker)

    def clear_comparison():
        update_shortlist([])
        st.session_state.compare_picker = []

    def remove_compared_school(school_id):
        update_shortlist([value for value in st.session_state.comparison_ids if value != school_id])
        st.session_state.compare_picker = st.session_state.comparison_ids

    if st.session_state.get("compare_picker") != selected_ids:
        st.session_state.compare_picker = selected_ids
    selections = st.multiselect("Schools to compare", schools.index.tolist(), max_selections=MAX_COMPARE,
                                format_func=school_labels.__getitem__, placeholder="Search for a school",
                                key="compare_picker", on_change=save_comparison)
    with st.container(horizontal=True, gap="small", vertical_alignment="center"):
        st.button("Clear all", on_click=clear_comparison, disabled=not selected_ids)
        if selected_ids:
            st.html("""<div class="compare-share">
                <button id="compare-copy-link" type="button">Copy link</button>
                <span role="status" aria-live="polite"></span>
            </div>
            <script>
            const copy = document.getElementById("compare-copy-link");
            copy.onclick = async () => {
                const status = copy.nextElementSibling;
                try {
                    await navigator.clipboard.writeText(window.location.href);
                    status.textContent = "Link copied.";
                } catch {
                    const address = document.createElement("input");
                    address.readOnly = true;
                    address.value = window.location.href;
                    address.setAttribute("aria-label", "Comparison link");
                    status.replaceChildren(address);
                    address.focus();
                    address.select();
                }
            };
            </script>""", unsafe_allow_javascript=True)

    if len(selections) >= 2:
        chosen = schools.loc[selections]
        colors = dict(zip(chosen.index, CHART_COLORS))
        compare_priorities = st.session_state.get("fit_priorities", [])
        compare_tuition_field = st.radio("Tuition shown", list(TUITION_BASES), index=list(TUITION_BASES).index(tuition),
                                         format_func=TUITION_BASES.get, horizontal=True, key="compare_filter_tuition_basis",
                                         on_change=remember_filter, args=("filter_tuition_basis",))
        with st.container(key="compare_remove_actions"):
            for school_id in selections:
                st.button(f"Remove {school_labels[school_id]}", key=f"compare_remove_{school_id}",
                          on_click=remove_compared_school, args=(school_id,))
        st.html("""<style>
        .st-key-compare_remove_actions {display:none}
        .compare-share {display:flex;align-items:center;gap:.65rem}
        .compare-share button {font:inherit;color:#173a46;background:white;border:1px solid #9db7c1;
            padding:.4rem .85rem;border-radius:.5rem;cursor:pointer;min-height:2.5rem}
        </style>
        <script>
        if (!window.atlasCompareRemove) {
            window.atlasCompareRemove = true;
            document.addEventListener("click", event => {
                const button = event.target.closest("button[data-remove-school]");
                if (button) document.querySelector(".st-key-compare_remove_" +
                    CSS.escape(button.dataset.removeSchool) + " button")?.click();
            });
        }
        </script>""", unsafe_allow_javascript=True)
        preset = st.radio("Compare by", ["All metrics", "Cost", "Admissions", "Outcomes"],
                          horizontal=True, key="compare_preset")
        differences_only = st.toggle("Show only differences")
        with st.container(key="compare_takeaways", gap="xsmall"):
            st.markdown("#### Key differences")
            takeaways = comparison_takeaways(chosen, compare_priorities, compare_tuition_field, preset)
            st.html('<ul class="compare-takeaways">' + "".join(f"<li>{html.escape(line)}</li>" for line in takeaways) + "</ul>")
        st.markdown("#### School-wide figures")
        st.caption("Figures describe each school across programs. Florida medians use all schools in the atlas that report the measure.")
        table, empty_metrics = comparison_table(chosen, frame, icons, differences_only, colors, preset,
                                               compare_priorities, compare_tuition_field)
        if table:
            st.html(table)
            with st.container(key="compare_notes"):
                st.caption("– means not reported or unverified.")
                st.caption("Highlights require at least two different reported values. ▼ marks lower tuition or debt. ▲ marks higher graduation or earnings.")
        elif differences_only:
            st.info("The selected schools have the same displayed values.")
        gap_notes = ["No reported values for " + ", ".join(empty_metrics) + "."] if empty_metrics else []
        chart_groups, _ = comparison_groups([], compare_tuition_field, preset)
        charts = {}
        for group, fields in chart_groups.items():
            if group == "School profile":
                continue
            chart, notes = comparison_chart(chosen, frame, school_labels, colors, fields, differences_only)
            gap_notes.extend(notes)
            if chart is not None:
                charts[group] = chart
        if gap_notes:
            st.caption("**Data gaps** · " + " ".join(gap_notes))
        if charts:
            st.caption("Dashed lines show the Florida median for each metric.")
        for group, chart in charts.items():
            with st.container(key=f"compare_chart_{group.lower()}"):
                st.subheader(f"{group} comparison")
                st.plotly_chart(chart, width="stretch", theme=None)
        with st.container(horizontal=True, gap="small"):
            st.button("Ask AI about these schools", key="compare_ask", on_click=ask_about_schools,
                      args=(list(selections),))
            st.button("Show on map", key="compare_map", on_click=show_school_on_map,
                      kwargs={"comparison_ids": list(selections)})
    elif selections:
        st.info("Add at least one more school to compare.")
    else:
        st.info("Choose two to five schools, or add them from a school card or the selected school’s details on the map page.")


if section == "Data":
    st.subheader("Charts and statistics")
    st.download_button("Download filtered college data",
                       filtered.drop(columns=["school", "distance_miles"], errors="ignore").to_csv(index=False),
                       "florida_colleges.csv", "text/csv")
    st.caption("Charts reflect the current filters. Compare similar degree levels before drawing conclusions.")

    def reporting_count(*fields):
        return f"{len(filtered.dropna(subset=list(fields))):,} of {len(filtered):,} schools"

    chart_labels = {**METRIC_NAMES, "name": "School", "type": "School type", "level": "Degree level"}
    chart_categories = {field: sorted(frame[field].dropna().unique()) for field in ("type", "level")}
    chart_options = dict(labels=chart_labels, color_discrete_sequence=CHART_COLORS,
                         category_orders=chart_categories)

    def show_data_chart(figure):
        figure.update_layout(template="plotly_white", font=dict(size=15, color="#142c3b"),
                             margin=dict(l=12, r=12, t=54, b=12), title_font_size=19,
                             legend=dict(orientation="h", yanchor="top", y=-.23, title_text=""))
        figure.update_xaxes(automargin=True)
        figure.update_yaxes(automargin=True)
        st.plotly_chart(figure, width="stretch", theme=None)

    first, second = st.columns(2)
    with first:
        tuition_values = filtered[tuition].dropna()
        if not tuition_values.empty:
            st.write(f"The median annual {tuition_label.lower()} here is {display(tuition_values.median(), 'money')}.")
        st.caption(f"{reporting_count(tuition)} report {tuition_label.lower()}.")
        if not tuition_values.empty:
            show_data_chart(px.histogram(filtered, x=tuition, color="type", nbins=20, **chart_options,
                                         title=f"Annual {tuition_label.lower()}", barmode="overlay", opacity=.8)
                            .update_xaxes(tickprefix="$", tickformat="~s").update_yaxes(title="Schools"))
        accepted = filtered["acceptance"].dropna()
        if not accepted.empty:
            st.write(f"Reported acceptance rates range from {display(accepted.min(), 'percent')} to {display(accepted.max(), 'percent')}.")
        st.caption(f"{reporting_count('acceptance')} report an acceptance rate.")
        if not accepted.empty:
            show_data_chart(px.box(filtered.dropna(subset=["acceptance"]), x="type", y="acceptance", color="type",
                                   points="all", hover_name="name", **chart_options, title="Acceptance by school type")
                            .update_yaxes(tickformat=".0%").update_layout(showlegend=False))
    with second:
        for field, label, category, heading in (
            (tuition, tuition_label.lower(), "level", "Tuition and graduation"),
            ("acceptance", "acceptance rates", "type", "Acceptance and graduation"),
        ):
            paired = filtered.dropna(subset=[field, "graduation"])
            st.write(paired_takeaway(paired, field, "graduation", label, "graduation rates"))
            st.caption(f"{reporting_count(field, 'graduation')} report both measures.")
            if not paired.empty:
                scatter = px.scatter(paired, x=field, y="graduation", color=category, hover_name="name",
                                     **chart_options, title=heading)
                scatter.update_xaxes(tickformat=".0%" if field == "acceptance" else "~s",
                                     tickprefix="" if field == "acceptance" else "$")
                scatter.update_yaxes(tickformat=".0%")
                show_data_chart(scatter)
    correlations = filtered[METRICS].corr(min_periods=3)
    pairs = [(correlations.at[field, other], field, other) for i, field in enumerate(METRICS)
             for other in METRICS[i + 1:] if pd.notna(correlations.at[field, other])]
    if pairs:
        value, field, other = max(pairs, key=lambda pair: abs(pair[0]))
        n = len(filtered.dropna(subset=[field, other]))
        st.write(f"The strongest linear relationship here is between {METRIC_NAMES[field].lower()} "
                 f"and {METRIC_NAMES[other].lower()} (r = {value:.2f} across {n:,} schools).")
        st.caption("Each correlation uses schools reporting both measures. See pairwise sample sizes below.")
        axis_labels = [METRIC_NAMES[field] for field in METRICS]
        heatmap = px.imshow(correlations.rename(index=METRIC_NAMES, columns=METRIC_NAMES), zmin=-1, zmax=1,
                            color_continuous_scale=[CHART_COLORS[1], "#f6f9fa", CHART_COLORS[0]],
                            text_auto=".2f", aspect="auto", title="How school measures relate",
                            labels=dict(color="Pearson r"))
        heatmap.update_xaxes(tickmode="array", tickvals=axis_labels, tickangle=0, side="bottom",
                             ticktext=[label.replace(" tuition", "<br>tuition") for label in axis_labels])
        show_data_chart(heatmap)
    else:
        st.caption("Correlations need at least three schools with both measures and variation in each measure.")
    with st.expander("Descriptive statistics"):
        st.caption("Each school has equal weight. Rate variability is in percentage points (pp). A dash means the statistic is unavailable.")
        st.dataframe(descriptive_table(filtered), hide_index=True, width="stretch")
    with st.expander("Pairwise sample sizes"):
        available = filtered[METRICS].notna().astype(int)
        sample_sizes = available.T.dot(available).rename(index=METRIC_NAMES, columns=METRIC_NAMES)
        st.caption("Each cell counts schools reporting both measures. The diagonal counts schools reporting that measure.")
        st.dataframe(sample_sizes.rename_axis("Metric").reset_index(), hide_index=True, width="stretch")
    with st.expander("Missing data and outliers"):
        st.dataframe(outlier_summary(filtered, METRICS), hide_index=True, width="stretch")
        st.caption("Calculations use available values. The audit flags and retains IQR outliers. Negative costs and rates outside 0–1 count as missing.")
        zero_graduation = filtered.loc[filtered["graduation"].eq(0), "name"].sort_values()
        if not zero_graduation.empty:
            st.write("Schools reporting 0% graduation for the measured cohort include "
                     + ", ".join(zero_graduation) + ".")

@st.cache_resource
def ai_quota():
    return DailyQuota(DAILY_AI_LIMIT)


def tuition_extreme(question):
    text = question.casefold()
    lowest = re.search(r"\b(cheapest|least expensive|lowest (?:in-state |out-of-state )?tuition)\b", text)
    highest = re.search(r"\b(most expensive|highest (?:in-state |out-of-state )?tuition)\b", text)
    if bool(lowest) == bool(highest):
        return None
    return min if lowest else max


if section == "AI":
    st.subheader("Ask AI about your schools")
    gemini_key = secret("GEMINI_API_KEY")
    model = secret("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    def save_ai_selection():
        if "ai_browse_ids" in st.session_state:
            st.session_state.ai_browse_ids = st.session_state.ai_picker
        else:
            update_shortlist(st.session_state.ai_picker)

    def return_to_shortlist():
        st.session_state.pop("ai_browse_ids", None)
        st.session_state.pop("ai_fit_context", None)
        st.session_state.ai_question = ""

    ai_defaults = [school_id for school_id in st.session_state.get("ai_browse_ids", selected_ids) if school_id in schools.index]
    if "ai_browse_ids" in st.session_state:
        st.button("Use my comparison shortlist", on_click=return_to_shortlist)
    if st.session_state.get("ai_picker") != ai_defaults:
        st.session_state.ai_picker = ai_defaults
    ai_schools = st.multiselect("Schools to ask about", schools.index.tolist(), max_selections=MAX_COMPARE,
                                format_func=school_labels.__getitem__, key="ai_picker", on_change=save_ai_selection)
    if not ai_schools:
        st.caption("Leave this empty to find the highest or lowest tuition across the atlas. Select schools for other questions.")
    questions = (
        ("Compare tuition", "Which schools have the lowest tuition?"),
        ("Compare outcomes", "How do graduation rates and earnings compare?"),
        ("Check missing data", "What data is missing?"),
    )
    with st.container(horizontal=True, gap="small", key="ai_suggestions"):
        for label, prompt in questions:
            st.button(label, on_click=st.session_state.__setitem__, args=("ai_question", prompt))
    question = st.text_area("What would you like to understand?", key="ai_question", max_chars=2000)
    action = st.container()
    quota = ai_quota()
    attempts = st.session_state.get("ai_attempts", 0)
    daily_message = "Daily AI limit reached. Try again tomorrow."
    reason = ""
    if not quota.available():
        reason = daily_message
    elif attempts >= SESSION_AI_LIMIT:
        reason = "You’ve reached the AI request limit for this session."
    elif not gemini_key.strip():
        reason = "AI answers are currently unavailable. You can still view a school data summary."
    submit = action.button("Show data summary" if reason and ai_schools else "Ask", type="primary")
    if reason:
        action.caption(reason)
    statewide_extreme = tuition_extreme(question) if not ai_schools else None
    if submit and not question.strip() and (not reason or not ai_schools):
        action.warning("Enter a question or choose one of the suggestions above.")
    elif submit and statewide_extreme:
        requested_tuition = tuition
        if re.search(r"\bout[- ]of[- ]state\b", question, re.I):
            requested_tuition = "tuition_out"
        elif re.search(r"\bin[- ]state\b", question, re.I):
            requested_tuition = "tuition_in"
        reported = schools[requested_tuition].dropna()
        if reported.empty:
            action.warning(f"No schools report {TUITION_BASES[requested_tuition].lower()}.")
        else:
            amount = statewide_extreme(reported)
            matching = schools.loc[reported.index[reported.eq(amount)], ["id", "name", requested_tuition]]
            names = join_phrases(matching["name"].tolist())
            direction = "highest" if statewide_extreme is max else "lowest"
            answer = (f"**{names}** {'has' if len(matching) == 1 else 'share'} the {direction} reported annual "
                      f"{TUITION_BASES[requested_tuition].lower()} at **{display(amount, 'money')}**. "
                      f"This compares {len(reported)} of {len(schools)} schools in the atlas with reported tuition.")
            st.session_state.ai_result = {"question": question, "model": None, "answer": answer, "statewide": True,
                                          "records": json.loads(matching.to_json(orient="records"))}
    elif submit and not ai_schools:
        action.warning("Select at least one school above for this question.")
    elif submit:
        context = schools.loc[ai_schools, ["id", "name", "type", "level", "athletics"] + METRICS]
        records = json.loads(context.to_json(orient="records"))
        fit_context = st.session_state.get("ai_fit_context", {})
        for record in records:
            record["selected_tuition_basis"] = tuition_label
            if record["id"] in fit_context:
                record["computed_fit"] = fit_context[record["id"]]
        result = {"question": question, "records": records, "model": None}
        if not reason and quota.available(reserve=True):
            st.session_state.ai_attempts = attempts + 1
            try:
                with st.spinner("Requesting a comparison…"):
                    result["answer"] = summarize(records, question, gemini_key.strip(), model.strip())
                    result["model"] = model.strip()
            except GeminiError as error:
                result["notice"] = str(error)
            except (RequestException, ValueError):
                result["notice"] = "Gemini could not be reached or returned an invalid response. Try again later."
        elif not reason:
            result["notice"] = daily_message
        if result["model"] is None:
            result["answer"] = college_data_summary(records, tuition)
        st.session_state.ai_result = result
    if "ai_result" in st.session_state:
        result = st.session_state["ai_result"]
        st.caption("Schools in this answer · " + ", ".join(record["name"] for record in result["records"]))
        if notice := result.get("notice"):
            st.warning(notice)
        with st.container(border=True):
            heading = "Tuition across the atlas" if result.get("statewide") else "School data summary · generated locally"
            if result["model"]:
                heading = "Gemini answer"
            st.markdown(f"**{heading}**")
            st.markdown(result["answer"])
            if result["model"]:
                st.caption("AI can make mistakes. Check the answer against the college data.")
if section == "Data":
    methods = st.expander("Methods and sources")
    methods.caption(f"U.S. Department of Education College Scorecard · Retrieved {snapshot['fetched_at'][:10]}")
    if available_programs:
        methods.markdown(
            f"**Programs:** [College Scorecard Field of Study, {program_catalog['release_date']}]({program_catalog['source']}). "
            "Fields are grouped by subject and award: undergraduate certificate, associate’s, bachelor’s, or master’s. "
            f"{len(masters_by_school)} of the {len(frame)} colleges report master’s fields. "
            "Tuition and outcomes shown here describe the undergraduate or institutional reporting cohort. "
            "Confirm current degree titles and graduate costs in the school’s catalog."
        )
    methods.markdown("""**Scope:** operating Florida postsecondary institutions with predominantly associate or bachelor’s degrees. This includes community colleges and eligible private colleges. No high schools. Certificate-only and graduate-only schools are excluded.

**Data:** [College Scorecard](https://collegescorecard.ed.gov/data/) and its [API documentation](https://collegescorecard.ed.gov/data/api-documentation/). JSON is paginated and saved locally. Filters do not change the underlying snapshot. Refresh it before a presentation.

**Acceptance:** reported institutional admission rate, not an individual admission probability. Missing acceptance is ‘Not reported’; open admission is not inferred.

**Cost:** annual tuition and required fees, not total attendance cost or net price after financial aid.

**Completion:** 150%-of-normal-time completion measure, using the four-year or less-than-four-year measure based on predominant degree. The cohorts do not represent all students. Earnings are measured 10 years after entry for the source’s covered population, not guaranteed salaries for all graduates. Debt covers completers in the reported federal-loan population.

**Timing:** ‘latest’ fields can refer to different reporting years and cohorts. The retrieval date is not an academic year. Consult the source dictionary before interpreting comparisons; this app does not claim a common-year panel.

**Athletics:** affiliations are sourced from athletics organizations, conferences, and schools. Schools may appear in multiple categories. The University of West Florida appears under NCAA Division II and Division I while it reclassifies. Individual sports may compete at different levels. The coverage audit includes verification dates and sources.

**Images:** sourced logo overrides take priority, followed by identifiable logos from school websites and website icons. Pins without an image use a graduation cap. The coverage audit lists each image type and source.

**AI:** The app sends questions and selected school data to Gemini when a user requests an AI answer. Verify generated answers against the college data.
""")
    coverage = [{"id": row["id"], "School": row["name"], "Image": icons.get(row["id"], {}).get("kind", "Missing"),
                 "Image source": icons.get(row["id"], {}).get("source", ""),
                 "Athletics": row["athletics"], "Athletics source": reviewed.get(row["id"], {}).get("athletics_source", ""),
                 "Verified on": reviewed.get(row["id"], {}).get("verified_on", "")} for _, row in frame.iterrows()]
    methods.dataframe(coverage, hide_index=True, width="stretch")
    methods.download_button("Download logo and athletics coverage audit", pd.DataFrame(coverage).to_csv(index=False), "coverage_audit.csv", "text/csv")

if section == "Data":
    render_data_settings(snapshot)
