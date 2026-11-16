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

    def test_invalid_date_not_faked(self):
        self.assertIsNone(g.as_datetime("dans quelques jours"))


if __name__ == "__main__":
    unittest.main()
