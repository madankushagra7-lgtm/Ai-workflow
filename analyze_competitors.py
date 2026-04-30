"""
Reads business_profile.json + all .tmp/scraped_*.json files, calls Claude API,
and saves structured analysis to .tmp/analysis.json.
Uses prompt caching on the static system prompt (business profile + JSON schema).
"""

import glob
import json
import os
import sys
import time
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096


def load_profile():
    path = os.path.join(ROOT, "business_profile.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_scraped_data():
    pattern = os.path.join(ROOT, ".tmp", "scraped_*.json")
    files = sorted(glob.glob(pattern))
    results = []
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                results.append(data)
            except json.JSONDecodeError:
                print(f"[WARN] Could not parse {fp}, skipping.")
    return results


def build_system_prompt(profile):
    services = ", ".join(profile.get("products_services", [])) or "N/A"
    return f"""You are a senior business strategy analyst specializing in competitive intelligence.

Your task is to analyze competitor data for a business and produce a structured, actionable competitive analysis report.

## The business you are analyzing FOR:
Name: {profile.get('business_name', 'N/A')}
Description: {profile.get('description', 'N/A')}
Industry: {profile.get('industry', 'N/A')}
Target Customers: {profile.get('target_customers', 'N/A')}
Location: {profile.get('location', 'N/A')}
Website: {profile.get('website', 'N/A')}
Products/Services: {services}
Unique Value Proposition: {profile.get('unique_value_proposition', 'N/A')}

## Your output MUST be valid JSON matching this exact schema:
{{
  "executive_summary": "string — 2-3 paragraphs covering market context and key findings",
  "competitors": [
    {{
      "name": "string",
      "url": "string",
      "overview": "string — 1 paragraph description of what they do",
      "target_market": "string",
      "pricing_summary": "string — what is known, or 'Not publicly available'",
      "key_features": ["string"],
      "strengths": ["string"],
      "weaknesses": ["string"],
      "online_presence": "string — social channels, accessibility, SEO signals",
      "data_quality": "full | partial | limited"
    }}
  ],
  "swot_comparison": {{
    "strengths": {{"our_business": ["string"], "competitor_aggregate": ["string"]}},
    "weaknesses": {{"our_business": ["string"], "competitor_aggregate": ["string"]}},
    "opportunities": ["string"],
    "threats": ["string"]
  }},
  "market_gaps": ["string — specific unmet needs or underserved segments you identified"],
  "recommended_actions": [
    {{
      "title": "string",
      "description": "string",
      "priority": "high | medium | low",
      "timeframe": "immediate | 30_days | 90_days | long_term"
    }}
  ],
  "analysis_metadata": {{
    "competitors_analyzed": 0,
    "competitors_with_limited_data": 0,
    "generated_at": "ISO timestamp"
  }}
}}

## Rules:
- Output ONLY the JSON object. No preamble, no markdown code fences, no explanation.
- If a competitor's data has an error field or js_heavy_signal is true, set data_quality to "limited".
- Strengths and weaknesses must be specific and evidence-based from scraped data, not generic.
- Recommended actions must directly reference the competitive landscape.
- SWOT "our_business" fields are inferences based on the business profile provided.
- market_gaps must be actionable insights, not restatements of competitor weaknesses.
- Fill analysis_metadata.generated_at with the current ISO timestamp.
"""


def format_competitor_block(data):
    if data.get("error") and data["error"] != "null":
        return (
            f"URL: {data.get('url', 'unknown')}\n"
            f"Status: SCRAPE FAILED — {data['error']}\n"
            f"Data Quality: limited\n"
        )

    lines = [
        f"URL: {data.get('url', 'N/A')}",
        f"Title: {data.get('title') or 'N/A'}",
        f"Meta Description: {data.get('meta_description') or 'N/A'}",
        f"JS-Heavy Site: {data.get('js_heavy_signal', False)}",
    ]

    headings = data.get("headings", [])
    if headings:
        lines.append(f"Key Headings: {' | '.join(headings[:15])}")

    pricing = data.get("pricing_mentions", [])
    if pricing:
        lines.append(f"Pricing Mentions: {' | '.join(pricing[:5])}")

    features = data.get("feature_keywords", [])
    if features:
        lines.append(f"Feature Keywords Detected: {', '.join(features)}")

    social = data.get("social_links", {})
    if social:
        social_str = ", ".join(f"{k}: {v}" for k, v in social.items())
        lines.append(f"Social Presence: {social_str}")

    contact = data.get("contact_info", {})
    if contact:
        contact_str = ", ".join(f"{k}: {v}" for k, v in contact.items())
        lines.append(f"Contact Info: {contact_str}")

    return "\n".join(lines)


def build_user_message(scraped_data):
    blocks = []
    for i, data in enumerate(scraped_data, 1):
        name = data.get("title") or data.get("url", f"Competitor {i}")
        blocks.append(f"### Competitor {i}: {name}\n{format_competitor_block(data)}")

    body = "\n\n---\n\n".join(blocks)
    return f"## Competitor Data\n\n{body}\n\nProduce the full analysis JSON now."


def parse_json_response(text):
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    return json.loads(text)


def call_claude(system_prompt, user_message, client):
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY is not set in .env. Cannot run analysis.")
        sys.exit(1)

    profile = load_profile()
    scraped_data = load_scraped_data()

    if not scraped_data:
        print("[ERROR] No scraped competitor files found in .tmp/. Run scrape step first.")
        sys.exit(1)

    limited_count = sum(
        1 for d in scraped_data
        if d.get("error") and d["error"] != "null" or d.get("js_heavy_signal")
    )
    print(f"[INFO] Analyzing {len(scraped_data)} competitors ({limited_count} with limited data)...")

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = build_system_prompt(profile)
    user_message = build_user_message(scraped_data)

    import re as _re

    raw_text = None
    for attempt in range(1, 3):
        try:
            print(f"[INFO] Calling Claude API (attempt {attempt})...")
            raw_text = call_claude(system_prompt, user_message, client)
            analysis = parse_json_response(raw_text)
            break
        except json.JSONDecodeError:
            if attempt == 1:
                print("[WARN] Claude returned invalid JSON. Retrying with correction prompt...")
                user_message = user_message + "\n\nYour previous response was not valid JSON. Return ONLY the JSON object with no additional text, no markdown, no code fences."
                time.sleep(3)
            else:
                raw_path = os.path.join(ROOT, ".tmp", "analysis_raw.txt")
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(raw_text or "")
                print(f"[ERROR] Claude returned invalid JSON after 2 attempts. Raw response saved to {raw_path}")
                sys.exit(1)
        except anthropic.APIError as e:
            if attempt == 1:
                print(f"[WARN] API error: {e}. Retrying in 30 seconds...")
                time.sleep(30)
            else:
                print(f"[ERROR] Claude API failed: {e}")
                sys.exit(1)

    tmp_dir = os.path.join(ROOT, ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    out_path = os.path.join(tmp_dir, "analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    n = len(analysis.get("competitors", []))
    print(f"[OK] Analysis complete — {n} competitors, {len(analysis.get('recommended_actions', []))} actions.")
    print(f"[OK] Saved to {out_path}")


if __name__ == "__main__":
    main()
