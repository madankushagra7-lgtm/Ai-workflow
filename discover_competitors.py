"""
Discovers competitors for the business defined in business_profile.json.
Tries SerpAPI first, then Tavily, then falls back to known_competitors in the profile.
Writes results to .tmp/competitors.json
"""

import json
import os
import sys
import re
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))


def load_profile():
    path = os.path.join(ROOT, "business_profile.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_query(profile):
    parts = [
        f"top competitors for {profile['business_name']}",
        f"in {profile['industry']}" if profile.get("industry") else "",
        f"serving {profile['target_customers']}" if profile.get("target_customers") else "",
        f"in {profile['location']}" if profile.get("location") else "",
    ]
    return " ".join(p for p in parts if p).strip()


class SerpAPIClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def search(self, query):
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={"q": query, "num": 10, "engine": "google", "api_key": self.api_key},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("organic_results", []):
            results.append({
                "name": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        return results


class TavilyClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def search(self, query):
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"query": query, "max_results": 10, "api_key": self.api_key},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("results", []):
            results.append({
                "name": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            })
        return results


def get_search_client():
    serpapi_key = os.getenv("SERPAPI_API_KEY", "").strip()
    tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
    if serpapi_key:
        print("[INFO] Using SerpAPI for competitor discovery.")
        return SerpAPIClient(serpapi_key)
    if tavily_key:
        print("[INFO] Using Tavily for competitor discovery.")
        return TavilyClient(tavily_key)
    return None


def normalize_competitor(entry):
    if isinstance(entry, str):
        return {"name": entry, "url": "", "snippet": ""}
    return {
        "name": entry.get("name", ""),
        "url": entry.get("url", ""),
        "snippet": entry.get("snippet", ""),
    }


def fallback_from_profile(profile):
    raw = profile.get("known_competitors", [])
    return [normalize_competitor(e) for e in raw if e]


def get_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return re.sub(r"^www\.", "", domain)
    except Exception:
        return url


def deduplicate_by_domain(results):
    seen = set()
    unique = []
    for r in results:
        domain = get_domain(r.get("url", ""))
        if domain and domain not in seen:
            seen.add(domain)
            unique.append(r)
        elif not domain:
            unique.append(r)
    return unique


def main():
    profile = load_profile()

    if not profile.get("business_name"):
        print("[ERROR] business_profile.json is missing 'business_name'. Please fill it in.")
        sys.exit(1)

    client = get_search_client()

    if client:
        query = build_query(profile)
        print(f"[INFO] Searching: {query}")
        try:
            raw_results = client.search(query)
            competitors = deduplicate_by_domain(raw_results)

            own_website = get_domain(profile.get("website", ""))
            if own_website:
                competitors = [c for c in competitors if get_domain(c.get("url", "")) != own_website]

            print(f"[OK] Found {len(competitors)} competitors via search API.")
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                print("[ERROR] Search API rate limit reached. Add more credits or use known_competitors fallback.")
            else:
                print(f"[ERROR] Search API request failed: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Search failed: {e}")
            sys.exit(1)
    else:
        print("[WARN] No search API key found (SERPAPI_API_KEY or TAVILY_API_KEY).")
        print("[WARN] Falling back to known_competitors in business_profile.json.")
        competitors = fallback_from_profile(profile)

        if not competitors:
            print(
                "[ERROR] No competitors found. Either:\n"
                "  1. Add SERPAPI_API_KEY or TAVILY_API_KEY to .env\n"
                "  2. Add entries to known_competitors in business_profile.json"
            )
            sys.exit(1)

        print(f"[OK] Using {len(competitors)} known competitors from profile.")

    tmp_dir = os.path.join(ROOT, ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    out_path = os.path.join(tmp_dir, "competitors.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(competitors, f, indent=2, ensure_ascii=False)

    print(f"[OK] Competitors saved to {out_path}")


if __name__ == "__main__":
    main()
