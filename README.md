# Florida Campus Atlas

A Programming for Data Science capstone for exploring Florida colleges on an aerial map, browsing campus-photo cards, comparing schools, and analyzing public College Scorecard data.

## Run on Windows

Install Python 3.11 or 3.12. Extract the project to a permanent folder, open PowerShell there, and run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL Streamlit prints, normally http://localhost:8501. A connection is needed to install dependencies, fetch data, download images, and use AI. The college snapshot and downloaded images are cached locally; map tiles still need network access.

## Keys and first use

1. Obtain a College Scorecard/data.gov key at https://api.data.gov/signup/. The default `DEMO_KEY` has strict rate limits.
2. Open **Data and image settings** in the sidebar, enter the key, and click **Fetch / refresh Florida colleges**. The app retrieves and normalizes all pages into a local snapshot at `data/colleges.json`. A failed refresh leaves the previous snapshot available.
3. In the same settings panel, click **Load school images**. The app caches reviewed logo overrides, school logos it can identify, and website icons. The map uses a graduation cap when an image is unavailable.
4. To add a logo, enter its direct image URL and source in `data/overrides.csv` using the Scorecard school ID. Use **Load school images** to apply the update. The coverage audit in **Data** lists image types and sources.
5. For AI comparisons, obtain a Gemini API key at https://aistudio.google.com/apikey and enter it in **AI**. Select colleges and generate a comparison. The model name is editable.

Alternatively, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and enter your keys. Environment variables with the same names are supported. Never commit secrets. The AI call is a real direct API integration, independent of any chat subscription; it is disabled until a key is supplied.

## Scope and athletics

Only operating Florida institutions with predominant associate or bachelor's degrees are shown. This includes community colleges and eligible public and private colleges and universities. No high schools are included. Certificate-only schools, graduate-only schools, and institutions outside College Scorecard's coverage are not included; do not describe this as every postsecondary institution in Florida.

NCAA Divisions I/II/III, NAIA, NJCAA, and other affiliations are a separate reviewed enrichment source. `data/overrides.csv` supports `athletics`, `athletics_source`, and `verified_on`. Use official membership directories:

- NCAA: https://www.ncaa.org/about-us/membership-directory/
- NAIA: https://www.naia.org/explore/schools/
- NJCAA: https://www.njcaa.org/member_colleges/Directory

The filter shows verified affiliation counts before other filters. A school may match more than one association or division, and individual sports may compete at different levels. Schools with no verified affiliation display **Not verified**.

## Features

- Aerial map with resizable viewing area, clustered college markers, and school popups.
- Expandable results cards with sourced campus photos where available, school marks, tuition, and other college details.
- School or city search and a **Filters** panel for athletics affiliation, tuition, acceptance rate, city, ownership, degree level, enrollment, graduation rate, debt, and earnings.
- Every enabled filter must match. Missing values are excluded only when the corresponding metric filter is enabled; disable that filter to include them. Empty category selections mean all values. The same filtered records drive map markers, comparisons, EDA, AI choices, and downloads.
- Three searchable, alphabetical comparison boxes and CSV export of matching colleges.
- Tuition histogram, acceptance boxplots, tuition/completion and acceptance/completion scatterplots.
- Descriptive statistics, Pearson correlations with pairwise sample sizes, missingness and IQR outlier audit.
- Gemini-generated comparisons using only the selected public data, plus an inspectable payload and downloadable response.
- Source/method documentation and image/athletics coverage export.

## Data and interpretation

Source: https://collegescorecard.ed.gov/data/

API documentation: https://collegescorecard.ed.gov/data/api-documentation/

The REST endpoint is `https://api.data.gov/ed/collegescorecard/v1/schools`. Responses are JSON with a `metadata` object and `results` array. Requests use state/operating filters, a specified field list, and pages of 100. `data_api.py:FIELDS` is the complete field mapping. Each record is keyed by institution ID. Snapshots record their retrieval timestamp and source without credentials.

The app uses latest-available values, which can have different reporting years. It is not a common-year panel. In-state/out-of-state tuition excludes other attendance expenses and financial aid. Completion uses the four-year or less-than-four-year 150%-time measure as appropriate. Rates are fractions in raw exports, formatted as percentages in the interface. Earnings are 10 years after entry for covered students; debt uses the reported completer population. These do not represent every student's outcome.

Missing/suppressed values stay missing. Invalid negative non-coordinate measurements and rates outside 0–1 become missing. Correlations use pairwise complete observations with at least three pairs. IQR outliers are retained and flagged, because large schools or expensive schools may be legitimate. No causal conclusions should be drawn. Missing acceptance rates do not establish open admissions.

## Files

- `app.py`: UI, filters, map, charts, comparisons.
- `data_api.py`: retrieval, scope filtering, normalization, atomic storage.
- `assets.py`: sourced logo overrides and bounded website-icon retrieval.
- `analysis.py`: missingness/outlier audit.
- `map_view.py`: Leaflet map HTML with clustered image markers.
- `ai.py`: direct Gemini API call and grounding instructions.
- `data/overrides.csv`: logo and athletics enrichment manifest.
- `data/campus_photos.json`: reviewed campus photo URLs and source pages.
- `tests/test_data.py`: offline API contract/data-quality tests.
- `PROJECT_REPORT_OUTLINE.md`, `DEMO.md`: submission preparation.

## Validation

```powershell
py -m unittest discover -s tests -v
py -m compileall -q app.py data_api.py assets.py ai.py analysis.py
```

Tests use synthetic fixtures only. They verify scope, missing/suppressed values, invalid rates, completion cohorts, pagination, secret-free snapshots, and preservation after failed refresh. They do not establish real-world data accuracy.

The local college snapshot, image cache, and secret settings are excluded from version control. A fresh checkout needs a College Scorecard refresh and image load for its local cache.

## GitHub collaboration and deployment

Clone the GitHub repository to make changes from a working copy. Keep API keys in local environment variables or Streamlit secrets.

On Streamlit Community Cloud, select the repository, branch, and `app.py`. Add the secrets using the example keys. Requirements are installed from `requirements.txt`. Local snapshot storage is a cache, not durable cloud storage: refresh data after a restart or add a vetted public snapshot to the repository for deployment. Do not commit API keys.

## Submission checklist

- Validate live data, AI response, filter edge cases, and map behavior.
- Complete/verify logo coverage and sourced athletics enrichment.
- Capture actual screenshots and write the 2–3 page results report.
- Include meaningful commits from each teammate.
- Submit repository URL, app URL if hosted, and report PDF/Word.
