#!/usr/bin/env python3
"""Agrège uniquement les métadonnées publiques d'articles en RSS et en JSON.

Le programme ne télécharge aucun jeu, fichier joint, image ni contenu intégral.
Il respecte robots.txt pour l'extraction HTML et n'essaie pas de contourner un 403.
"""
from __future__ import annotations

import argparse
import html as html_module
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime, parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlparse, urlunparse, unquote
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs"
SOURCE = "https://www.skidrowreloaded.com/"
SOURCES_RSS = (
    "https://feeds.feedburner.com/SkidrowReloadedGames",
    "https://www.skidrowreloaded.com/feed/",
    "https://www.skidrowreloaded.com/?feed=rss2",
)
USER_AGENT = "MonRSSPublications/1.1 (agrégateur de titres et liens des miniatures)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/html;q=0.8"}
TIMEOUT = 16
MAX_ARTICLES = 180
IMAGE_LOOKUPS_PER_RUN = 4  # Respecter le serveur source : max. quatre pages d'articles par passage.
IMAGE_RETRY_HOURS = 24  # Ne pas re-tester les images manquantes toutes les cinq minutes.
IMAGE_EXTENSIONS = re.compile(r"\.(?:jpe?g|png|webp|gif|avif)$", re.I)
MEDIA_NS = "http://search.yahoo.com/mrss/"
ET.register_namespace("media", MEDIA_NS)
ALLOWED_DOMAINS = {"skidrowreloaded.com", "www.skidrowreloaded.com"}
ATOM_NS = "http://www.w3.org/2005/Atom"
ET.register_namespace("atom", ATOM_NS)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def as_datetime(value):
    if not value:
        return None
    txt = str(value).strip()
    try:
        dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(txt)
        except (ValueError, TypeError, IndexError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_article_url(raw, base=SOURCE):
    if not raw:
        return None
    url = urljoin(base, raw.strip())
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or parsed.hostname not in ALLOWED_DOMAINS:
        return None
    path = unquote(parsed.path)
    if not path.startswith("/") or not path.strip("/"):
        return None
    # Un article est à la racine avec son slug WordPress, pas dans /page/ ou /category/.
    slugs = [p for p in path.split("/") if p]
    if len(slugs) != 1 or slugs[0].lower() in {
        "feed", "contact", "category", "tag", "archives", "about", "requests", "dmca",
        "privacy-policy", "sitemap.xml", "index.php", "wp-admin", "wp-login.php",
    }:
        return None
    return urlunparse(("https", "www.skidrowreloaded.com", "/" + slugs[0] + "/", "", "", ""))


def normalize_image_url(raw, base=SOURCE):
    """Valide une URL de miniature ; aucune image n'est téléchargée ni recopiée."""
    if not raw or not isinstance(raw, str):
        return ""
    raw = html_module.unescape(raw.strip()).strip("\"'")
    if not raw or len(raw) > 2048:
        return ""
    url = urljoin(base, raw)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return ""
    # On ne publie que des liens HTTPS vers de vrais formats d'image.
    if not IMAGE_EXTENSIONS.search(unquote(parsed.path)):
        return ""
    name = unquote(parsed.path).rsplit("/", 1)[-1].lower()
    if any(s in name for s in ("favicon", "site-logo", "gravatar", "avatar", "pixel-1x1", "spacer.gif")):
        return ""
    return urlunparse(("https", parsed.netloc, parsed.path, parsed.params, parsed.query, ""))


def parse_srcset(raw, base):
    choices = []
    for candidate in (raw or "").split(","):
        parts = candidate.strip().split()
        if not parts:
            continue
        url = normalize_image_url(parts[0], base)
        if url:
            size = 600
            if len(parts) > 1 and parts[1].endswith("w"):
                try:
                    size = int(parts[1][:-1])
                except ValueError:
                    pass
            choices.append((size, url))
    if not choices:
        return ""
    return min(choices, key=lambda v: (v[0] < 340, abs(v[0] - 680)))[1]


def image_from_tag(tag, base):
    if tag is None:
        return ""
    for attr in ("data-src", "data-lazy-src", "data-original", "data-echo", "data-fallback-src"):
        url = normalize_image_url(tag.get(attr), base)
        if url:
            return url
    for attr in ("data-srcset", "srcset"):
        url = parse_srcset(tag.get(attr), base)
        if url:
            return url
    return normalize_image_url(tag.get("src"), base)


def image_from_markup(soup, base, article_url=""):
    """Privilégie les miniatures liées à cet article dans une carte HTML."""
    images = soup.select("img")
    for img in images:
        anchor = img.find_parent("a", href=True)
        if anchor and normalize_article_url(anchor.get("href"), base) == article_url:
            url = image_from_tag(img, base)
            if url:
                return url
    for selector in (
        ".post-thumbnail img", ".entry-thumb img", ".thumbnail img",
        ".thumb img", ".featured-image img", "img.wp-post-image",
        "img.attachment-post-thumbnail", "img",
    ):
        for img in soup.select(selector):
            url = image_from_tag(img, base)
            if url:
                return url
    return ""


def image_from_article_html(raw_html, base):
    soup = BeautifulSoup(raw_html, "html.parser")
    for selector, attr in (
        ('meta[property="og:image:secure_url"]', "content"),
        ('meta[property="og:image"]', "content"),
        ('meta[name="twitter:image"]', "content"),
    ):
        tag = soup.select_one(selector)
        url = normalize_image_url(tag.get(attr), base) if tag else ""
        if url:
            return url
    content = soup.select_one("article, .entry-content, .post-content, main, #content") or soup
    return image_from_markup(content, base)


def clean_title(value):
    return re.sub(r"\s+", " ", (value or "")).strip()[:240]


def parse_xml_feed(raw_xml):
    """Lit RSS/Atom, y compris les miniatures (pas les archives ni les téléchargements)."""
    try:
        tree = ET.fromstring(raw_xml)
    except ET.ParseError:
        return []
    tag = tree.tag.rsplit("}", 1)[-1].lower()
    if tag not in ("rss", "feed", "rdf"):
        return []
    items = []
    entries = [n for n in tree.iter() if n.tag.rsplit("}", 1)[-1].lower() in ("item", "entry")]
    for entry in entries:
        fields = {}
        links = []
        image = ""
        html_fragments = []
        for node in entry:
            name = node.tag.rsplit("}", 1)[-1].lower()
            if name in ("title", "pubdate", "published", "updated", "date", "guid", "id"):
                if name not in fields and node.text:
                    fields[name] = node.text.strip()
            if name == "link":
                link = (node.attrib.get("href") or node.text or "").strip()
                rel = node.attrib.get("rel", "alternate")
                if rel == "alternate":
                    links.append(link)
            if name in ("description", "encoded", "summary", "content") and node.text:
                html_fragments.append(node.text)
            # Media RSS : <media:thumbnail> et <media:content medium="image">.
            if node.tag.startswith("{" + MEDIA_NS + "}") and name in ("thumbnail", "content"):
                if name == "thumbnail" or node.get("medium") == "image" or (node.get("type") or "").startswith("image/"):
                    image = image or normalize_image_url(node.get("url"))
            # Les enclosures non-image (ZIP, EXE, torrents...) sont ignorées.
            if name == "enclosure" and (node.get("type") or "").startswith("image/"):
                image = image or normalize_image_url(node.get("url"))
            if name == "image" and node.get("href"):
                image = image or normalize_image_url(node.get("href"))
        candidate = next((valid for u in links if (valid := normalize_article_url(u))), None)
        if not candidate:
            candidate = normalize_article_url(fields.get("guid") or fields.get("id"))
        title = clean_title(fields.get("title"))
        if candidate and title:
            if not image:
                for fragment in html_fragments:
                    image = image_from_markup(BeautifulSoup(fragment, "html.parser"), SOURCE, candidate)
                    if image:
                        break
            dt = as_datetime(fields.get("pubdate") or fields.get("published") or fields.get("date") or fields.get("updated"))
            items.append({"title": title, "url": candidate,
                          "published": dt.isoformat(timespec="seconds") if dt else "",
                          "image": image})
    return dedupe(items)


def parse_html_listing(html, base=SOURCE):
    """Lit seulement les liens des titres h2/h3 situés dans les cartes d'articles."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main, #content, .content, .posts, #main") or soup
    blocks = main.select("article, .post, .type-post, .post-item, .entry")
    # Certains thèmes WordPress proposent seulement une grille h2.
    candidates = blocks if blocks else main.select("h2, h3")
    items = []
    for block in candidates:
        heading = block.select_one("h2 a[href], h3 a[href], .entry-title a[href], .post-title a[href]")
        if heading is None and block.name in ("h2", "h3"):
            heading = block.select_one("a[href]")
        if not heading:
            continue
        title = clean_title(heading.get_text(" ", strip=True))
        link = normalize_article_url(heading.get("href"), base)
        if not title or not link:
            continue
        date_node = block.select_one("time[datetime], .entry-date, .post-date, .date, time")
        date_str = ""
        if date_node:
            date_str = date_node.get("datetime") or date_node.get("content") or date_node.get_text(" ", strip=True)
        date = as_datetime(date_str)
        image = image_from_markup(block, base, link)
        items.append({"title": title, "url": link,
                      "published": date.isoformat(timespec="seconds") if date else "",
                      "image": image})
    return dedupe(items)


def dedupe(items):
    result = []
    seen = set()
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            result.append(item)
    return result


def read_robots(session):
    """Renvoie (règles, autorisation racine, raison), sans ignorer les refus."""
    robots = urljoin(SOURCE, "/robots.txt")
    try:
        response = session.get(robots, timeout=TIMEOUT)
        if response.status_code in (404, 410):
            return None, True, "robots.txt absent"
        if response.status_code != 200:
            return None, False, f"robots.txt : HTTP {response.status_code}"
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser, parser.can_fetch("MonRSSPublications", SOURCE), "Consignes robots.txt"
    except requests.RequestException as err:
        return None, False, f"robots.txt inaccessible : {err.__class__.__name__}"


def can_fetch_html(session):
    _, allowed, why = read_robots(session)
    return allowed, why


def enrich_missing_images(session, items, checked):
    """Complète jusqu'à 4 miniatures manquantes ; une nouvelle tentative après 24 h."""
    eligible = []
    deadline = datetime.now(timezone.utc) - timedelta(hours=IMAGE_RETRY_HOURS)
    for item in items:
        if item.get("image"):
            continue
        previous = as_datetime(item.get("image_checked_at"))
        if previous and previous > deadline:
            continue
        eligible.append(item)
        if len(eligible) >= IMAGE_LOOKUPS_PER_RUN:
            break
    if not eligible:
        return
    parser, allowed, why = read_robots(session)
    if not allowed:
        print("INFO : miniatures non interrogées (" + why + ")")
        return
    for item in eligible:
        item["image_checked_at"] = checked
        if parser and not parser.can_fetch("MonRSSPublications", item["url"]):
            print("INFO : page article interdite par robots.txt")
            continue
        try:
            response = safe_get(session, item["url"])
            if "html" not in response.headers.get("Content-Type", "text/html").lower():
                continue
            image = image_from_article_html(response.text, response.url)
            if image:
                item["image"] = image
        except (requests.RequestException, ValueError) as err:
            print(f"INFO : image non disponible pour {item['url']} ({err.__class__.__name__})")



def safe_get(session, url):
    response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    if len(response.content) > 6_000_000:
        raise ValueError("Réponse supérieure à 6 Mo")
    host = urlparse(response.url).hostname
    expected = ALLOWED_DOMAINS | {"feeds.feedburner.com"}
    if host not in expected:
        raise ValueError(f"Redirection inattendue vers {host}")
    return response


def fetch_entries(session):
    errors = []
    for url in SOURCES_RSS:
        try:
            response = safe_get(session, url)
            entries = parse_xml_feed(response.content)
            if entries:
                dates = [dt for item in entries if (dt := as_datetime(item.get("published")))]
                if dates and max(dates) < datetime.now(timezone.utc) - timedelta(days=14):
                    errors.append(f"RSS {url}: dernières dates de publication trop anciennes, autre méthode tentée")
                    continue
                return entries, "RSS : " + url, errors
            errors.append(f"RSS {url}: flux vide ou format non reconnu")
        except (requests.RequestException, ValueError) as err:
            errors.append(f"RSS {url}: {err}")
    allowed, why = can_fetch_html(session)
    if not allowed:
        errors.append("HTML non interrogé (" + why + ")")
        return [], "", errors
    try:
        response = safe_get(session, SOURCE)
        entries = parse_html_listing(response.text, response.url)
        if entries:
            return entries, "Page d'accueil HTML", errors
        errors.append("HTML : aucun titre d'article reconnu ; la structure du site a peut-être changé")
    except (requests.RequestException, ValueError) as err:
        errors.append(f"HTML : {err}")
    return [], "", errors


def default_site_url():
    override = os.getenv("SITE_URL", "").strip()
    if override:
        if not override.startswith("https://"):
            raise ValueError("SITE_URL doit commencer par https://")
        return override.rstrip("/") + "/"
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if "/" in repo:
        owner, name = repo.split("/", 1)
        # Les dépôts utilisateur spéciaux <user>.github.io sont publiés à la racine.
        return f"https://{owner.lower()}.github.io/" + ("" if name.lower() == owner.lower() + ".github.io" else f"{name}/")
    return "https://EXEMPLE.github.io/mon-rss-skidrow/"


def load_previous():
    path = OUT / "items.json"
    if path.exists():
        try:
            val = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(val, dict) and isinstance(val.get("items"), list):
                return val
        except (OSError, ValueError):
            pass
    return {"items": [], "last_success_at": ""}


def merge_entries(fresh, old, checked):
    known = {v.get("url"): v for v in old if isinstance(v, dict) and v.get("url")}
    merged = []
    for item in fresh:
        previous = known.get(item["url"], {})
        merged.append({"title": item["title"], "url": item["url"],
                       "published": item.get("published") or previous.get("published", ""),
                       "image": item.get("image") or previous.get("image", ""),
                       "image_checked_at": previous.get("image_checked_at", ""),
                       "first_seen": previous.get("first_seen", checked)})
    seen = {v["url"] for v in merged}
    for item in old:
        if isinstance(item, dict) and item.get("url") and item["url"] not in seen:
            merged.append(item)
            seen.add(item["url"])
    return merged[:MAX_ARTICLES]


def write_feed(items, site_url, checked):
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    for key, val in (
        ("title", "Publications de SkidrowReloaded — flux indépendant"),
        ("link", site_url),
        ("description", "Titres des publications publiques (agrégateur non officiel ; aucun fichier hébergé)."),
        ("language", "fr"),
        ("lastBuildDate", format_datetime(as_datetime(checked))),
        ("generator", "Mon RSS Publications 1.1"),
    ):
        ET.SubElement(channel, key).text = val
    ET.SubElement(channel, f"{{{ATOM_NS}}}link", {
        "href": site_url + "feed.xml", "rel": "self", "type": "application/rss+xml"
    })
    for item in items:
        node = ET.SubElement(channel, "item")
        ET.SubElement(node, "title").text = item["title"]
        ET.SubElement(node, "link").text = item["url"]
        ET.SubElement(node, "guid", isPermaLink="true").text = item["url"]
        image = normalize_image_url(item.get("image"))
        if image:
            ET.SubElement(node, f"{{{MEDIA_NS}}}thumbnail", {"url": image})
            # La description HTML est utilisée par les lecteurs RSS qui ignorent Media RSS.
            description = '<p><img src="' + html_module.escape(image, quote=True) + '" alt="Miniature de la publication" /></p><p>Nouvelle publication sur le site source.</p>'
        else:
            description = "Nouvelle publication sur le site source."
        ET.SubElement(node, "description").text = description
        published = as_datetime(item.get("published"))
        if published:
            ET.SubElement(node, "pubDate").text = format_datetime(published)
    ET.indent(root, space="  ")
    (OUT / "feed.xml").write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))


def write_data(data):
    (OUT / "items.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(demo=False):
    OUT.mkdir(exist_ok=True)
    site_url = default_site_url()
    old = load_previous()
    checked = now_iso()
    if demo:
        fixture = (ROOT / "examples" / "liste-exemple.html").read_text(encoding="utf-8")
        new_items = parse_html_listing(fixture)
        source, errors = "Démonstration locale", []
        print("Mode DEMO : aucun accès réseau.")
    else:
        session = requests.Session()
        session.headers.update(HEADERS)
        new_items, source, errors = fetch_entries(session)
    if new_items:
        items = merge_entries(new_items, old.get("items", []), checked)
        if not demo:
            enrich_missing_images(session, items, checked)
        state = "demo" if demo else "ok"
        last_success = "" if demo else checked
    else:
        items = old.get("items", [])[:MAX_ARTICLES]
        state = "erreur"
        last_success = old.get("last_success_at", "")
    payload = {
        "title": "Mon fil de publications", "source_url": SOURCE,
        "checked_at": checked, "last_success_at": last_success,
        "status": state, "source_type": source,
        "message": "Mode démonstration (données fictives)." if demo else (
            f"{len(new_items)} articles trouvés ; {len(items)} conservés." if new_items else
            "La source n'a pas pu être lue ; les publications précédentes sont conservées."
        ),
        "errors": errors[-5:], "items": items,
    }
    write_data(payload)
    write_feed(items, site_url, checked)
    print(f"État : {state} | {len(items)} articles | adresse RSS : {site_url}feed.xml")
    for err in errors:
        print("INFO :", err)
    # Déploiement utile même en cas d'échec réseau (site et diagnostic toujours visibles).
    return 0


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--demo", action="store_true", help="Teste avec les titres fictifs sans connexion internet")
    args = cli.parse_args()
    sys.exit(run(demo=args.demo))
