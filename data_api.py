"""College Scorecard retrieval, pagination, normalization and atomic snapshots."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.data.gov/ed/collegescorecard/v1/schools"
ROOT = Path(__file__).parent
SNAPSHOT = ROOT / "data" / "colleges.json"
FIELDS = {
    "id": "id", "name": "school.name", "city": "school.city",
    "state": "school.state", "website": "school.school_url",
    "ownership": "school.ownership", "degree": "school.degrees_awarded.predominant",
    "operating": "school.operating", "lat": "location.lat", "lon": "location.lon",
    "tuition_in": "latest.cost.tuition.in_state",
    "tuition_out": "latest.cost.tuition.out_of_state",
    "acceptance": "latest.admissions.admission_rate.overall",
    "enrollment": "latest.student.size",
    "completion_4yr": "latest.completion.completion_rate_4yr_150nt",
    "completion_2yr": "latest.completion.completion_rate_less_than_4yr_150nt",
    "debt": "latest.aid.median_debt.completers.overall",
    "earnings": "latest.earnings.10_yrs_after_entry.median",
}
NUMERIC = ["lat", "lon", "tuition_in", "tuition_out", "acceptance", "enrollment", "graduation", "debt", "earnings"]

def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None

def normalize(row):
    record = {name: row.get(field) for name, field in FIELDS.items()}
    record["id"] = str(record["id"])
    # Predominant associate/bachelor institutions only; no high schools or certificate-only providers.
    if record["state"] != "FL" or record["operating"] != 1 or record["degree"] not in (2, 3):
        return None
    record["graduation"] = record["completion_4yr"] if record["degree"] == 3 else record["completion_2yr"]
    for field in NUMERIC:
        record[field] = number(record.get(field))
        if record[field] is not None and field not in ("lat", "lon") and record[field] < 0:
            record[field] = None
    for field in ("acceptance", "graduation"):
        if record[field] is not None and not 0 <= record[field] <= 1:
            record[field] = None
    if record["lat"] is not None and not -90 <= record["lat"] <= 90:
        record["lat"] = None
    if record["lon"] is not None and not -180 <= record["lon"] <= 180:
        record["lon"] = None
    record["type"] = {1: "Public", 2: "Private nonprofit", 3: "Private for-profit"}.get(record["ownership"], "Unknown")
    record["level"] = "Four-year" if record["degree"] == 3 else "Two-year / community college"
    return record

def fetch_colleges(key, session=None):
    import requests
    client = session or requests.Session()
    records, page = [], 0
    while True:
        response = client.get(API, params={
            "api_key": key, "school.state": "FL", "school.operating": 1,
            "fields": ",".join(FIELDS.values()), "per_page": 100, "page": page, "sort": "id:asc",
        }, timeout=45)
        if response.status_code != 200:
            raise RuntimeError(f"College Scorecard returned HTTP {response.status_code}. Check your key, connection, or rate limit.")
        payload = response.json()
        if not isinstance(payload.get("results"), list) or "total" not in payload.get("metadata", {}):
            raise RuntimeError("Unexpected API response; existing snapshot has been preserved.")
        rows = payload["results"]
        records.extend(r for row in rows if (r := normalize(row)) is not None)
        page += 1
        if page * 100 >= payload["metadata"]["total"]:
            break
        if not rows or page > 100:
            raise RuntimeError("Pagination stopped unexpectedly; snapshot has been preserved.")
    records = list({r["id"]: r for r in records}.values())
    if not records:
        raise RuntimeError("No eligible colleges were returned; previous snapshot preserved.")
    snapshot = {"fetched_at": datetime.now(timezone.utc).isoformat(), "source": API,
                "period": "Latest available per metric; years and cohorts may differ", "records": records}
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    temporary = SNAPSHOT.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    temporary.replace(SNAPSHOT)
    return snapshot

def load_snapshot():
    if not SNAPSHOT.exists():
        return None
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))
