import os
import re
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from transformers import pipeline
from playwright.sync_api import sync_playwright
from openai import OpenAI
import json

load_dotenv()
app = Flask(__name__)

# ------------------ MODELS ------------------

ner = pipeline(
    "ner",
    model="dslim/bert-base-NER",
    aggregation_strategy="simple"
)

llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ------------------ UTILS ------------------

def fetch_html_js(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_load_state("networkidle")
        html = page.content()
        browser.close()
        return html

def clean_soup(soup):
    for tag in soup(["script", "style", "nav", "footer", "aside", "noscript"]):
        tag.decompose()
    return soup

def make_json_safe(obj):
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    elif hasattr(obj, "item"):
        return obj.item()
    return obj

# ------------------ STEP 2: RULE-BASED ------------------

def rule_based_extract(soup):
    text = soup.get_text(separator=" ")

    price_match = re.search(
        r"(₹|\$|€|INR|USD|EUR)\s?[\d,]+(\.\d+)?",
        text
    )

    specs = {}
    for row in soup.find_all("tr"):
        cols = row.find_all(["th", "td"])
        if len(cols) == 2:
            specs[cols[0].get_text(strip=True)] = cols[1].get_text(strip=True)

    features = [
        li.get_text(strip=True)
        for li in soup.find_all("li")
        if 10 < len(li.get_text(strip=True)) < 120
    ]

    images = [
        img.get("src")
        for img in soup.find_all("img")
        if img.get("src") and not img.get("src").startswith("data:")
    ]

    return {
        "price": price_match.group(0) if price_match else None,
        "specifications": specs,
        "features": list(dict.fromkeys(features))[:20],
        "images": images
    }

# ------------------ STEP 3: HF NER ------------------

def ner_enrichment(text):
    entities = make_json_safe(ner(text[:3000]))

    model_candidates = list({
        e["word"]
        for e in entities
        if e["entity_group"] in ("ORG", "MISC")
    })

    return {
        "model_candidates": model_candidates[:10],
        "entities": entities[:10]
    }

# ------------------ STEP 4: LLM FALLBACK ------------------

def llm_fallback(partial_data, context_text):
    prompt = f"""
You are given partially extracted car data.
Fill ONLY missing or unclear fields.
Do NOT hallucinate.

Partial data:
{partial_data}

Context text:
{context_text[:3000]}

Return JSON:
{{
  "model_name": "",
  "variant": "",
  "description": ""
}}
"""

    response = llm_client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    # return response.choices[0].message.content
    raw = response.choices[0].message.content
    return json.loads(raw)

# ------------------ API ------------------

@app.route("/extract", methods=["POST"])
def extract():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"success": False, "error": "Missing url"}), 400

    url = data["url"]

    # 1️⃣ Fetch HTML
    html = fetch_html_js(url)
    soup = clean_soup(BeautifulSoup(html, "html.parser"))

    # 2️⃣ Rule-based
    rule_data = rule_based_extract(soup)

    # 3️⃣ NER enrichment
    text = soup.get_text(separator=" ")
    ner_data = ner_enrichment(text)

    # Combine
    result = {
        "model_name": None,
        "variant": None,
        "price": rule_data["price"],
        "specifications": rule_data["specifications"],
        "features": rule_data["features"],
        "images": rule_data["images"],
        "description": None,
        "ner": ner_data
    }

    # 4️⃣ LLM fallback only if needed
    missing_fields = [
        k for k in ("model_name", "variant", "description")
        if not result.get(k)
    ]

    llm_used = False
    if missing_fields:
        llm_used = True
        llm_data = llm_fallback(result, text)
        result.update(make_json_safe(llm_data))

    return jsonify({
        "success": True,
        "llm_used": llm_used,
        "data": result
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)