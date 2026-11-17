"""Cache sourced school logos and website icons for the college map."""
import base64
import csv
import ipaddress
import io
import json
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin, urlparse
from PIL import Image, ImageOps

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
        self.logos = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "link" and values.get("href"):
            rel = (values.get("rel") or "").lower()
            if "apple-touch-icon" in rel:
                self.links.insert(0, values["href"])
            elif "icon" in rel:
                self.links.append(values["href"])
        src = values.get("data-src") or values.get("src")
        if tag == "img" and src:
            alt = (values.get("alt") or "").lower()
            identity = " ".join(values.get(key) or "" for key in ("class", "id", "src")).lower()
            if "logo" in alt or "logo" in identity:
                self.logos.append((src, alt, "custom-logo" in (values.get("class") or "").split()))

def school_images(school, website):
    html, _, homepage = download(website, 2500000)
    parser = Icons()
    parser.feed(html.decode("utf-8", errors="replace"))
    generic = {"university", "college", "campus", "school", "institute", "logo"}
    keywords = set(re.findall(r"[a-z0-9]{3,}", school["name"].lower())) - generic
    homepage_host = urlparse(homepage).hostname
    for src, alt, site_logo in parser.logos:
        url = urljoin(homepage, src)
        identifiers = set(re.findall(r"[a-z0-9]{3,}", alt + " " + urlparse(url).path.lower().rsplit("/", 1)[-1]))
        named_logo = keywords and len(keywords & identifiers) >= min(2, len(keywords))
        if urlparse(url).hostname == homepage_host and (site_logo or named_logo):
            yield url, "School logo"
    for link in parser.links[:8]:
        yield urljoin(homepage, link), "School website icon"

def image_data(content, mime):
    if mime == "image/svg+xml":
        from resvg_py import svg_to_bytes

        content = svg_to_bytes(svg_string=content.decode("utf-8-sig"), width=128, skip_system_fonts=True)
        mime = "image/png"
    if mime not in ("image/png", "image/jpeg", "image/webp", "image/x-icon", "image/vnd.microsoft.icon", "image/gif", "application/octet-stream"):
        raise ValueError("Unsupported image format")
    with Image.open(io.BytesIO(content), formats=["PNG", "JPEG", "WEBP", "ICO", "GIF"]) as image:
        if image.width * image.height > 4000000:
            raise ValueError("Image exceeds pixel limit")
        image = image.convert("RGBA")
        image.thumbnail((128, 128))
        output = io.BytesIO()
        image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")

@lru_cache(maxsize=256)
def logo_background(data, minimum_size=0):
    """Choose a contrasting pin background at the logo's rendered size."""
    if not data:
        return None
    try:
        content = base64.b64decode(data.split(",", 1)[1])
        with Image.open(io.BytesIO(content)) as image:
            if max(image.size) < minimum_size:
                return None
            logo = ImageOps.contain(image.convert("RGBA"), (27, 27))
    except (OSError, ValueError, IndexError):
        return None

    scores = {}
    for color in ("#ffffff", "#123440"):
        background = Image.new("RGBA", logo.size, color)
        rgb = background.getpixel((0, 0))[:3]
        background.alpha_composite(logo)
        scores[color] = sum(
            max(abs(channel - base) for channel, base in zip(pixel[:3], rgb)) >= 65
            for pixel in background.getdata()
        )
    if scores["#ffffff"] >= 25:
        return "#ffffff"
    best = max(scores, key=scores.get)
    return best if scores[best] >= 8 else None

def load_icon(school, override):
    path = ICON_DIR / f"{school['id']}.json"
    cached = {}
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("kind") == "School logo" and cached.get("override", "") == override.get("logo_url", ""):
            return cached
    website = school.get("website") or ""
    if website and not website.startswith(("http://", "https://")):
        website = "https://" + website
    candidates = []
    if override.get("logo_url"):
        candidates.append((override["logo_url"], "School logo"))
    if website:
        try:
            candidates.extend(school_images(school, website))
        except Exception:
            pass
        candidates.append((urljoin(website, "/favicon.ico"), "School website icon"))
    for candidate, kind in dict.fromkeys(candidates):
        if kind == "School website icon" and cached:
            return cached
        try:
            content, mime, source = download(candidate, 500000)
            result = {"data": image_data(content, mime), "source": source, "kind": kind,
                      "override": candidate if candidate == override.get("logo_url") else ""}
            ICON_DIR.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=ICON_DIR, delete=False) as file:
                json.dump(result, file)
            temporary_path = Path(file.name)
            try:
                temporary_path.replace(path)
            finally:
                temporary_path.unlink(missing_ok=True)
            return result
        except Exception:
            continue
    return cached

def refresh_icons(records):
    reviewed = overrides()
    with ThreadPoolExecutor(max_workers=6) as executor:
        return list(executor.map(lambda school: load_icon(school, reviewed.get(school["id"], {})), records))

def cached_icons():
    if not ICON_DIR.exists():
        return {}
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in ICON_DIR.glob("*.json")}
