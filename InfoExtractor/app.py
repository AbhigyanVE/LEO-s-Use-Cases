import os
import re
import json
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from transformers import pipeline
from playwright.sync_api import sync_playwright
from openai import OpenAI

# ------------------ SETUP ------------------

load_dotenv()
app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
llm_client = OpenAI(api_key=OPENAI_API_KEY)

ner = pipeline(
    "ner",
    model="dslim/bert-base-NER",
    aggregation_strategy="simple"
)

# ------------------ UTILS ------------------

def make_json_safe(obj):
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    if hasattr(obj, "item"):
        return obj.item()
    return obj

def fetch_html_js(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page.goto(url, timeout=30000)
        page.wait_for_load_state("networkidle")
        html = page.content()
        browser.close()
        return html

def clean_soup(soup):
    for tag in soup(["script", "style", "nav", "footer", "aside", "noscript", "header"]):
        tag.decompose()
    return soup

# ------------------ RULE-BASED EXTRACTION ------------------

def extract_price(text):
    match = re.search(
        r"(₹|\$|€|INR|USD|EUR)\s?[\d,]+(\.\d+)?",
        text
    )
    return match.group(0) if match else None

def extract_images(soup):
    return [
        img.get("src")
        for img in soup.find_all("img")
        if img.get("src") and not img.get("src").startswith("data:")
    ]

def extract_features(soup):
    features = []
    for section in soup.find_all(["section", "div"]):
        text = section.get_text(" ", strip=True)
        if (
            80 < len(text) < 600 and
            any(word in text.lower() for word in [
                "feature", "equipped", "interior", "technology",
                "design", "assistant", "display"
            ])
        ):
            features.append(text)
    return features[:5]

def extract_spec_blocks(soup):
    specs = {}
    for block in soup.find_all("div"):
        text = block.get_text(" ", strip=True)
        if (
            any(k in text.lower() for k in [
                "km/h", "hp", "kw", "engine",
                "fuel", "acceleration", "consumption"
            ]) and
            len(text) < 500
        ):
            specs[f"block_{len(specs)+1}"] = text
    return specs

def rule_based_extract(soup):
    text = soup.get_text(" ", strip=True)
    return {
        "price": extract_price(text),
        "features": extract_features(soup),
        "specifications": extract_spec_blocks(soup),
        "images": extract_images(soup)
    }

# ------------------ HF NER ------------------

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

# ------------------ LLM FALLBACK ------------------

def llm_fallback(partial_data, context_text):
    prompt = f"""
You are extracting structured car information.

Rules:
- Use ONLY the provided text
- Do NOT invent data
- Structure variants and specifications if present
- Leave fields empty if not found

Return JSON ONLY:

{{
  "model_name": "",
  "variant": "",
  "specifications": {{}},
  "features": [],
  "description": ""
}}

Existing extracted data:
{json.dumps(partial_data, indent=2)}

Relevant content:
{context_text[:2500]}
"""

    response = llm_client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)

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

    # 2️⃣ Rule-based extraction
    rule_data = rule_based_extract(soup)

    # 3️⃣ NER enrichment
    text = soup.get_text(" ", strip=True)
    ner_data = ner_enrichment(text)

    # 4️⃣ Combine base result
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

    # 5️⃣ LLM fallback only if needed
    llm_used = False
    missing = any(
        not result.get(k)
        for k in ("model_name", "variant", "description")
    )

    if missing:
        llm_used = True
        context = "\n".join(
            result["features"] +
            list(result["specifications"].values())
        )
        llm_data = llm_fallback(result, context)
        result.update(make_json_safe(llm_data))

    return jsonify({
        "success": True,
        "llm_used": llm_used,
        "data": result
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# ------------------ MAIN ------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
