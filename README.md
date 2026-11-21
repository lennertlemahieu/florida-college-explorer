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

On **Interactive Map**, enter a ZIP code, choose a school, and click **Show shortest driving route**. Radius filters use straight-line distance. The route uses the [Valhalla public demo service](https://valhalla.github.io/valhalla/start/introduction/) and starts near the Census ZIP-area center. The app sends the start and school coordinates only when you request a route. The displayed drive time is an estimate.

## Keys and first use

1. Obtain a College Scorecard/data.gov key at https://api.data.gov/signup/. The default `DEMO_KEY` has strict rate limits.
2. Open **Data & Sources → Data and image settings**, enter the key, and click **Fetch / refresh Florida colleges**. The app retrieves and normalizes all pages into a local snapshot at `data/colleges.json`. A failed refresh leaves the previous snapshot available.
3. In the same settings panel, click **Load school images**. The app caches reviewed logo overrides, school logos it can identify, and website icons. The map uses a graduation cap when an image is unavailable.
4. To add a logo, enter its direct image URL and source in `data/overrides.csv` using the Scorecard school ID. Use **Load school images** to apply the update. The coverage audit in **Data** lists image types and sources.
5. Ask AI uses Gemini 3.1 Flash-Lite. The app owner can create a [Gemini API key](https://aistudio.google.com/apikey) in a project marked **Free tier** with billing disabled and set `GEMINI_API_KEY` in the app’s Streamlit secrets or environment.

Alternatively, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and enter your keys. Environment variables with the same names are supported. Never commit secrets. Gemini API usage is separate from any chat subscription.

For a ranking audit, set `ATLAS_DEVELOPER_MODE = true` in your local Streamlit secrets. Ranked Finder results then include **Check the score calculations**, with each school's priority scores, weights, and total. The student view hides this panel by default.

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
- Find a School shows matches as students set program, credential, school type, tuition, athletics, and distance requirements. The optional ranking step puts relevant filters first and offers up to five priority slots. Weights run from 5 for first place to 1 for fifth.
- Select **Master’s** in the degree filter to see schools with a reported master’s field. Add a subject under **Programs / majors** to match that subject at the master’s level. Open a school’s details to browse its graduate fields. The June 2026 [College Scorecard Field of Study release](https://ed-public-download.scorecard.network/downloads/Most-Recent-Cohorts-Field-of-Study_06102026.zip) lists 218 distinct master’s fields across 64 of the 124 colleges in the saved snapshot. Tuition and outcomes refer to undergraduate or institution-level cohorts. Check the school’s graduate catalog for exact degree titles and costs.
- The map and list share Finder requirements and offer additional filters. With a tuition cap, schools with unknown tuition are excluded by default. The acceptance filter includes unreported rates by default. The Map and Data & Sources filters can include schools with unreported programs.
- Compare up to five schools with Florida medians, a differences toggle, cost highlights, and shortcuts from school cards and the selected school's details on the map page. Matching colleges can be exported as CSV.
- Tuition histogram, acceptance boxplots, tuition/completion and acceptance/completion scatterplots.
- Descriptive statistics, Pearson correlations with pairwise sample sizes, missingness and IQR outlier audit.
- Gemini explains selected public school data. The page can show a built-in data summary when AI answers are unavailable.
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
- `campus_map.py`: Leaflet map HTML with clustered image markers.
- `ai.py`: direct Gemini API call and grounding instructions.
- `data/overrides.csv`: logo and athletics enrichment manifest.
- `data/campus_photos.json` maps exact school IDs to campus photos. Reviewed Wikimedia Commons images are bundled in `data/commons_photos/` and include their creator, license, and original file page in the school details.
- `tests/test_data.py`: offline API contract/data-quality tests.
- `PROJECT_REPORT_OUTLINE.md`, `DEMO.md`: submission preparation.

### Refresh campus photos

Run `python campus_photos.py --find "Eckerd College"` to list image candidates from the school's English Wikipedia article. Open the Commons file page to check the campus, building, viewpoint, and credit. For an approved image, set the school's entry in `data/campus_photos.json` to `{"commons_file": "Eckerd College Armacost Library.png", "alt": "Eckerd College's Armacost Library across the water"}`. Then run `python campus_photos.py --refresh` and save the updated catalog and thumbnails together. The refresh accepts credited CC BY, CC BY-SA, CC0, and explicitly marked public-domain images. Schools without a suitable photo use their logo tile. UCF uses its logo tile by design.

## Validation

```powershell
py -m unittest discover -s tests -v
py -m compileall -q app.py data_api.py assets.py ai.py analysis.py
```

Data contract tests use synthetic fixtures to check scope, missing values, invalid rates, completion cohorts, pagination, secret-free snapshots, and preservation after a failed refresh. Campus photo tests also verify that bundled Wikimedia images open offline and carry attribution.

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
