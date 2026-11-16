"""Load reviewed logo overrides and cache school website icons without guessing logos."""
import base64
import csv
import ipaddress
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).parent
ICON_DIR = ROOT / "data" / "icons"

def overrides():
    with (ROOT / "data" / "overrides.csv").open(encoding="utf-8-sig", newline="") as file:
        return {str(row["id"]): row for row in csv.DictReader(file)}

def public_url(url):
    """Refuse local/private destinations, including redirect destinations."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid public URL")
    if parsed.port not in (None, 80, 443):
        raise ValueError("Unsupported port")
    addresses = socket.getaddrinfo(parsed.hostname, None)
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError("Non-public address")
    return url

def download(url, limit):
    import requests
    for _ in range(5):
        public_url(url)
        with requests.get(url, timeout=10, allow_redirects=False, stream=True,
                          headers={"User-Agent": "FloridaCollegeExplorer/1.0 (academic project)"}) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["Location"])
                continue
            response.raise_for_status()
            chunks, count = [], 0
            for chunk in response.iter_content(16384):
                count += len(chunk)
                if count > limit:
                    raise ValueError("Asset exceeds size limit")
                chunks.append(chunk)
            return b"".join(chunks), response.headers.get("Content-Type", "").split(";")[0], url
    raise ValueError("Too many redirects")

class Icons(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "link" and "icon" in values.get("rel", "").lower() and values.get("href"):
            self.links.append(values["href"])

def load_icon(school, override):
    path = ICON_DIR / f"{school['id']}.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("override", "") == override.get("logo_url", ""):
            return cached
    website = school.get("website") or ""
    if website and not website.startswith(("http://", "https://")):
        website = "https://" + website
    candidates = []
    is_logo = bool(override.get("logo_url"))
    if is_logo:
        candidates.append(override["logo_url"])
    elif website:
        try:
            html, _, final_url = download(website, 1500000)
            parser = Icons()
            parser.feed(html.decode("utf-8", errors="replace"))
            candidates.extend(urljoin(final_url, link) for link in parser.links[:6])
        except Exception:
            pass
        candidates.append(urljoin(website, "/favicon.ico"))
    for candidate in candidates:
        try:
            content, mime, source = download(candidate, 500000)
            # Reject SVG/HTML and other active formats; browsers render raster images only.
            if mime not in ("image/png", "image/jpeg", "image/webp", "image/x-icon", "image/vnd.microsoft.icon", "image/gif"):
                continue
            result = {"data": f"data:{mime};base64," + base64.b64encode(content).decode(),
                      "source": source, "kind": "School logo" if is_logo else "School website icon",
                      "override": override.get("logo_url", "")}
            ICON_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result), encoding="utf-8")
            return result
        except Exception:
            continue
    return {}

def refresh_icons(records):
    reviewed = overrides()
    with ThreadPoolExecutor(max_workers=6) as executor:
        return list(executor.map(lambda school: load_icon(school, reviewed.get(school["id"], {})), records))

def cached_icons():
    if not ICON_DIR.exists():
        return {}
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in ICON_DIR.glob("*.json")}
