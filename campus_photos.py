"""Reviewed school photos for offline cards, with a maintainer-only Wikimedia refresh."""
import argparse
import base64
import hashlib
import html
import io
import json
import re
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

import requests
from PIL import Image, ImageOps

DATA = Path(__file__).resolve().parent / "data"
CATALOG = DATA / "campus_photos.json"
THUMBNAILS = DATA / "commons_photos"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "FloridaCampusAtlas/1.0 (https://github.com/lennertlemahieu/florida-college-explorer)"


def photo_catalog():
    return _load_catalog(CATALOG.stat().st_mtime_ns)


@lru_cache(maxsize=1)
def _load_catalog(modified):
    return json.loads(CATALOG.read_text(encoding="utf-8"))


@lru_cache(maxsize=256)
def _thumbnail_url(path):
    return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def campus_photo(school_id):
    photo = photo_catalog().get(str(school_id))
    if not photo or "commons_file" not in photo:
        return photo
    if not all(photo.get(k) for k in ("thumbnail", "artist", "source", "license", "license_url")):
        return None
    try:
        url = _thumbnail_url(THUMBNAILS / photo["thumbnail"])
    except FileNotFoundError:
        return None
    return {**photo, "url": url}


def campus_photo_credit(photo):
    def link(url, label):
        return f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(label)}</a>'
    if "commons_file" not in photo:
        return f'<p>{link(photo["source"], "Campus photo source")}</p>'
    source = link(photo["source"], photo["commons_file"])
    license_link = link(photo["license_url"], photo["license"])
    return (f'<p>Photo: {source} by {html.escape(photo["artist"])} on Wikimedia Commons '
            f'({license_link}). Resized and cropped for display.</p>')


def wiki_query(session, endpoint, **params):
    response = session.get(endpoint, params={"action": "query", "format": "json", "formatversion": 2, **params},
                           timeout=25)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise ValueError(payload["error"].get("info", "Wikimedia lookup failed"))
    return payload


def find_photos(session, article):
    continuation = {}
    while True:
        payload = wiki_query(session, WIKIPEDIA_API, titles=article, prop="images", redirects=1,
                             imlimit="max", **continuation)
        for page in payload["query"]["pages"]:
            for item in page.get("images", []):
                name = item["title"]
                if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    print("https://commons.wikimedia.org/wiki/" + quote(name.replace(" ", "_"), safe=":()"))
        continuation = payload.get("continue")
        if not continuation:
            return


def write_atomic(path, content):
    with NamedTemporaryFile(dir=path.parent, delete=False) as file:
        tmp = Path(file.name)
        try:
            file.write(content)
        except BaseException:
            file.close()
            tmp.unlink(missing_ok=True)
            raise
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def refresh_photo(session, school_id, photo):
    title = photo["commons_file"]
    payload = wiki_query(session, COMMONS_API, titles="File:" + title, prop="imageinfo",
                         iiprop="url|extmetadata", iiextmetadatalanguage="en", iiurlwidth=960, redirects=1)
    page = payload["query"]["pages"][0]
    if "imageinfo" not in page:
        raise ValueError(f"Missing Commons file for {school_id}: {title}")
    info = page["imageinfo"][0]
    meta = info["extmetadata"]

    def plain(key):
        raw = meta.get(key, {}).get("value", "")
        return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())

    license_name = plain("LicenseShortName")
    license_url = plain("LicenseUrl").replace("http://", "https://")
    artist = plain("Attribution") or plain("Artist")
    if license_name == "Public domain" and plain("License") == "pd" and plain("Copyrighted").lower() == "false":
        license_url = info["descriptionurl"] + "#Licensing"
    elif not (re.fullmatch(r"CC BY(?:-SA)? [1-4]\.0|CC0", license_name)
              and license_url.startswith("https://creativecommons.org/")):
        raise ValueError(f"Review credit and reuse terms for {title}")
    if not artist:
        raise ValueError(f"Missing photographer credit for {title}")
    thumb = session.get(info["thumburl"], timeout=30)
    thumb.raise_for_status()
    with Image.open(io.BytesIO(thumb.content)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((960, 960))
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=85)
    content = output.getvalue()
    filename = f"{school_id}-{hashlib.sha256(content).hexdigest()[:12]}.webp"
    THUMBNAILS.mkdir(exist_ok=True)
    write_atomic(THUMBNAILS / filename, content)
    return {**photo, "thumbnail": filename, "source": info["descriptionurl"], "artist": artist,
            "license": license_name, "license_url": license_url}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--find", metavar="WIKIPEDIA_ARTICLE", help="Print candidate file pages for human review")
    mode.add_argument("--refresh", action="store_true", help="Fetch only the Commons files approved in the catalog")
    args = parser.parse_args()
    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        if args.find:
            find_photos(session, args.find)
            return
        catalog = photo_catalog().copy()
        for school_id, photo in catalog.items():
            if "commons_file" in photo:
                catalog[school_id] = refresh_photo(session, school_id, photo)
        # Publish credits and thumbnail references together after every download succeeds.
        write_atomic(CATALOG, (json.dumps(catalog, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
