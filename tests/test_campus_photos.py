import base64
import io
import unittest
from unittest.mock import patch

from PIL import Image

from campus_photos import campus_photo, campus_photo_credit, photo_catalog, refresh_photo


class CampusPhotoTests(unittest.TestCase):
    def test_bundled_photos_decode_offline_and_show_credits(self):
        for school_id, record in photo_catalog().items():
            if "commons_file" not in record:
                continue
            with self.subTest(school=school_id):
                photo = campus_photo(int(school_id))
                self.assertTrue(photo["url"].startswith("data:image/webp;base64,"))
                with Image.open(io.BytesIO(base64.b64decode(photo["url"].split(",", 1)[1]))) as thumb:
                    self.assertEqual(thumb.format, "WEBP")
                    self.assertGreaterEqual(thumb.width, 300)
                credit = campus_photo_credit(photo)
                self.assertIn(photo["source"], credit)
                self.assertIn(photo["license_url"], credit)
                self.assertTrue(photo["artist"] and photo["alt"])

    def test_logo_fallback_and_incomplete_records(self):
        self.assertIsNone(campus_photo("132903"))  # UCF has a deliberately branded tile.
        self.assertIsNone(campus_photo("not-a-school"))
        with patch("campus_photos.photo_catalog", return_value={"1": {"commons_file": "candidate.jpg"}}):
            self.assertIsNone(campus_photo("1"))

    def test_unknown_rights_do_not_get_published(self):
        unlicensed = {"query": {"pages": [{"imageinfo": [{"extmetadata": {
            "Artist": {"value": "Photographer"}, "LicenseShortName": {"value": "Fair use"},
        }}]}]}}
        with patch("campus_photos.wiki_query", return_value=unlicensed):
            with self.assertRaisesRegex(ValueError, "reuse terms"):
                refresh_photo(None, "1", {"commons_file": "campus.jpg"})
