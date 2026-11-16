import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import generer as g


class TestFlux(unittest.TestCase):
    def test_html_titres_et_dates(self):
        html = (g.ROOT / "examples/liste-exemple.html").read_text(encoding="utf-8")
        items = g.parse_html_listing(html)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Galaxie Aventure — exemple fictif")
        self.assertEqual(items[1]["url"], "https://www.skidrowreloaded.com/simulateur-fictif-v2/")
        self.assertIn("2026-11-16", items[0]["published"])

    def test_html_ignore_downloads_et_liens_externes(self):
        html = '''<main><article class="post">
        <h2><a href="https://example.com/file.exe">Executable</a></h2></article>
        <article class="post"><h2><a href="/page/3/">Page 3</a></h2></article>
        <article class="post"><h2><a href="/mon-jeu/">Mon Jeu</a></h2></article></main>'''
        self.assertEqual(len(g.parse_html_listing(html)), 1)

    def test_rss_parse_without_downloads(self):
        rss = '''<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Titre de jeu</title><link>https://www.skidrowreloaded.com/un-jeu/</link>
        <enclosure url="https://example.com/fichier.zip"/>
        <pubDate>Mon, 16 Nov 2026 12:10:00 GMT</pubDate></item></channel></rss>'''
        items = g.parse_xml_feed(rss)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["published"], "2026-11-16T12:10:00+00:00")
        self.assertNotIn("fichier.zip", str(items))

    def test_atom_parse(self):
        atom = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
        <title>Un titre</title><link href="https://www.skidrowreloaded.com/nouvelle-publication/"/>
        <updated>2026-11-16T10:00:00Z</updated></entry></feed>'''
        self.assertEqual(g.parse_xml_feed(atom)[0]["title"], "Un titre")

    def test_merges_without_losing_old(self):
        old = [{"title": "Ancien", "url": "https://www.skidrowreloaded.com/ancien/", "published": "", "first_seen": "2026-11-15T12:00:00Z"}]
        new = [{"title": "Nouveau", "url": "https://www.skidrowreloaded.com/nouveau/", "published": ""}]
        merged = g.merge_entries(new, old, "2026-11-16T12:00:00Z")
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[1]["title"], "Ancien")

    def test_feed_xml_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(g, "OUT", Path(temp)):
                g.write_feed([{"title": "Test & Exemple", "url": "https://www.skidrowreloaded.com/jeu/", "published": ""}],
                             "https://example.github.io/rss/", "2026-11-16T12:00:00+00:00")
                root = ET.parse(Path(temp) / "feed.xml").getroot()
                self.assertEqual(root.find("channel/item/title").text, "Test & Exemple")
                self.assertEqual(root.find("channel/item/pubDate"), None)

    def test_robots_forbidden(self):
        class FakeResponse:
            status_code = 200
            text = "User-agent: *\nDisallow: /\n"
        class FakeSession:
            def get(self, *args, **kwargs):
                return FakeResponse()
        self.assertFalse(g.can_fetch_html(FakeSession())[0])

    def test_html_image_standard_et_lazy(self):
        html = """<main><article><a href='/jeu-test/'><img data-src='/wp-content/uploads/jeu-test.webp' src='data:image/gif;base64,aA=='></a>
        <h2><a href='/jeu-test/'>Jeu test</a></h2></article></main>"""
        items = g.parse_html_listing(html)
        self.assertEqual(items[0]["image"], "https://www.skidrowreloaded.com/wp-content/uploads/jeu-test.webp")

    def test_html_image_liee_bonne_carte(self):
        html = """<main><article><img src='/pub.jpg'><h2><a href='/test-2/'>Le titre</a></h2>
        <a href='/test-2/'><img src='/bonne-vignette.jpg'></a></article></main>"""
        self.assertEqual(g.parse_html_listing(html)[0]["image"], "https://www.skidrowreloaded.com/bonne-vignette.jpg")

    def test_rss_media_et_image_description(self):
        rss = """<rss xmlns:media='http://search.yahoo.com/mrss/' version='2.0'><channel>
        <item><title>Titre 1</title><link>https://www.skidrowreloaded.com/jeu-a/</link>
        <media:thumbnail url='https://cdn.example.org/jeu-a.jpg'/></item>
        <item><title>Titre 2</title><link>https://www.skidrowreloaded.com/jeu-b/</link>
        <description>&lt;p&gt;&lt;img src='https://cdn.example.org/jeu-b.png'/&gt;&lt;/p&gt;</description></item>
        </channel></rss>"""
        items = g.parse_xml_feed(rss)
        self.assertEqual(items[0]["image"], "https://cdn.example.org/jeu-a.jpg")
        self.assertEqual(items[1]["image"], "https://cdn.example.org/jeu-b.png")

    def test_rss_fichiers_zip_non_images(self):
        rss = """<rss version='2.0'><channel><item><title>Jeu</title>
        <link>https://www.skidrowreloaded.com/jeu-test/</link>
        <enclosure url='https://example.org/game.zip' type='application/zip'/>
        </item></channel></rss>"""
        item = g.parse_xml_feed(rss)[0]
        self.assertEqual(item["image"], "")

    def test_historique_image_conservee(self):
        url = "https://www.skidrowreloaded.com/ancien/"
        old = [{"title": "Ancien", "url": url, "image": "https://cdn.example.org/a.jpg",
                "image_checked_at": "2026-11-15T01:00:00+00:00", "published": "", "first_seen": "date"}]
        fresh = [{"title": "Nouveau", "url": url, "published": "", "image": ""}]
        merged = g.merge_entries(fresh, old, "now")
        self.assertEqual(merged[0]["image"], old[0]["image"])
        self.assertEqual(merged[0]["image_checked_at"], old[0]["image_checked_at"])

    def test_feed_contient_miniature_rss(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(g, "OUT", Path(tmp)):
                image = "https://cdn.example.org/image.webp"
                g.write_feed([{"title": "Jeu", "url": "https://www.skidrowreloaded.com/jeu/",
                               "image": image, "published": ""}],
                             "https://example.github.io/rss/", "2026-11-16T12:00:00+00:00")
                root = ET.parse(Path(tmp) / "feed.xml").getroot()
                node = root.find("channel/item")
                self.assertEqual(node.find("{http://search.yahoo.com/mrss/}thumbnail").get("url"), image)
                self.assertIn(image, node.find("description").text)

    def test_url_image_securisee(self):
        self.assertEqual(g.normalize_image_url("javascript:alert(1)"), "")
        self.assertEqual(g.normalize_image_url("https://a.example/game.zip"), "")
        self.assertEqual(g.normalize_image_url("data:image/png;base64,abcd"), "")
        self.assertEqual(g.normalize_image_url("https://a.example/jeu.jpg"), "https://a.example/jeu.jpg")

    def test_meta_og_image_article(self):
        html = "<html><head><meta property='og:image' content='/wp-content/uploads/jeu.jpg'></head><body></body></html>"
        self.assertEqual(g.image_from_article_html(html, g.SOURCE), "https://www.skidrowreloaded.com/wp-content/uploads/jeu.jpg")

    def test_enrichissement_images_sans_contourner_robots(self):
        class FakeResponse:
            def __init__(self, url, status=200, text="", typ="text/html"):
                self.url, self.status_code, self.text, self.headers = url, status, text, {"Content-Type": typ}
                self.content = text.encode()
            def raise_for_status(self):
                return None
        class FakeSession:
            def __init__(self):
                self.calls = []
            def get(self, url, **kwargs):
                self.calls.append(url)
                if url.endswith("robots.txt"):
                    return FakeResponse(url, text="User-agent: *\nAllow: /\n")
                return FakeResponse(url, text="<html><meta property='og:image' content='/img.jpg'></html>")
        session = FakeSession()
        items = [{"title": "T", "url": "https://www.skidrowreloaded.com/un-jeu/", "image": ""}]
        g.enrich_missing_images(session, items, "2026-11-16T10:00:00+00:00")
        self.assertEqual(items[0]["image"], "https://www.skidrowreloaded.com/img.jpg")
        session.calls.clear()
        g.enrich_missing_images(session, items, "2026-11-16T10:00:00+00:00")
        self.assertEqual(session.calls, [])

    def test_invalid_date_not_faked(self):
        self.assertIsNone(g.as_datetime("dans quelques jours"))


if __name__ == "__main__":
    unittest.main()
