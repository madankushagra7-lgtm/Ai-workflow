"""
Scrapes a single competitor website and saves extracted data to .tmp/scraped_{safe_name}.json
Usage: python tools/scrape_competitor.py <url>
Always writes a JSON file even on failure — pipeline never aborts for one failed scrape.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xhtml;q=0.9,*/*;q=0.8",
}

PRICING_KEYWORDS = re.compile(
    r"\b(price|pricing|plan|plans|per month|per year|/mo|/yr|\$|€|£|free trial|subscribe|subscription)\b",
    re.IGNORECASE,
)

FEATURE_KEYWORDS = re.compile(
    r"\b(feature|integration|dashboard|analytics|report|automat|ai|api|mobile|app|cloud|security|support|sla)\b",
    re.IGNORECASE,
)

SOCIAL_DOMAINS = {
    "linkedin": "linkedin.com",
    "twitter": "twitter.com",
    "x": "x.com",
    "facebook": "facebook.com",
    "instagram": "instagram.com",
    "youtube": "youtube.com",
    "tiktok": "tiktok.com",
}

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def safe_filename(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    domain = re.sub(r"^www\.", "", domain)
    safe = re.sub(r"[^\w]", "_", domain)
    return f"scraped_{safe}"


def extract_text(soup):
    for tag in soup(["script", "style", "noscript", "head"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def detect_js_heavy(soup, full_text):
    script_count = len(soup.find_all("script"))
    return len(full_text) < 600 and script_count > 5


def extract_headings(soup):
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 2:
            headings.append(text)
    return headings[:20]


def extract_pricing_mentions(soup):
    mentions = []
    for element in soup.find_all(string=PRICING_KEYWORDS):
        snippet = element.strip()
        parent = element.parent
        if parent:
            snippet = parent.get_text(separator=" ", strip=True)
        if len(snippet) > 10:
            mentions.append(snippet[:250])
    return list(dict.fromkeys(mentions))[:8]


def extract_feature_keywords(full_text):
    found = set()
    for match in FEATURE_KEYWORDS.finditer(full_text):
        found.add(match.group(0).lower())
    return sorted(found)


def extract_social_links(soup):
    links = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        for platform, domain in SOCIAL_DOMAINS.items():
            if domain in href and platform not in links:
                links[platform] = a["href"]
    return links


def extract_contact_info(soup, full_text):
    contact = {}
    emails = EMAIL_PATTERN.findall(full_text)
    emails = [e for e in emails if not e.endswith((".png", ".jpg", ".gif", ".svg"))]
    if emails:
        contact["email"] = list(dict.fromkeys(emails))[:3]

    phone_hrefs = []
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("tel:"):
            phone_hrefs.append(a["href"].replace("tel:", "").strip())
    if phone_hrefs:
        contact["phone"] = list(dict.fromkeys(phone_hrefs))[:2]

    return contact


def get_meta(soup, name):
    tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": f"og:{name}"})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def scrape(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
    except requests.exceptions.Timeout:
        return {"url": url, "error": "timeout", "scraped_at": datetime.now(timezone.utc).isoformat()}
    except requests.exceptions.ConnectionError as e:
        return {"url": url, "error": f"connection_error: {str(e)[:100]}", "scraped_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        return {"url": url, "error": str(e)[:200], "scraped_at": datetime.now(timezone.utc).isoformat()}

    if resp.status_code != 200:
        return {"url": url, "error": f"http_{resp.status_code}", "scraped_at": datetime.now(timezone.utc).isoformat()}

    soup = BeautifulSoup(resp.text, "lxml")
    full_text = extract_text(BeautifulSoup(resp.text, "lxml"))

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    meta_description = get_meta(soup, "description")

    return {
        "url": url,
        "title": title,
        "meta_description": meta_description,
        "headings": extract_headings(soup),
        "pricing_mentions": extract_pricing_mentions(soup),
        "feature_keywords": extract_feature_keywords(full_text),
        "social_links": extract_social_links(soup),
        "contact_info": extract_contact_info(soup, full_text),
        "js_heavy_signal": detect_js_heavy(soup, full_text),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }


def main():
    if len(sys.argv) < 2:
        print("[ERROR] Usage: python tools/scrape_competitor.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    if not url.startswith("http"):
        url = "https://" + url

    print(f"[INFO] Scraping {url}")
    data = scrape(url)

    if data.get("error"):
        print(f"[WARN] Scrape failed for {url}: {data['error']}")
    else:
        headings_count = len(data.get("headings", []))
        js_flag = data.get("js_heavy_signal", False)
        print(f"[OK] Scraped {url} — {headings_count} headings, JS-heavy: {js_flag}")

    tmp_dir = os.path.join(ROOT, ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    filename = safe_filename(url) + ".json"
    out_path = os.path.join(tmp_dir, filename)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[OK] Saved to {out_path}")


if __name__ == "__main__":
    main()
