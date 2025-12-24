import re
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from transformers import pipeline
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

app = Flask(__name__)

# Load NER model once (startup cost only once)
ner = pipeline(
    "ner",
    model="dslim/bert-base-NER",
    aggregation_strategy="simple"
)

# HELPER FUNCTION
def make_json_safe(obj):
    """Convert numpy / HF objects to JSON-safe Python types"""
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(i) for i in obj]
    elif hasattr(obj, "item"):  # numpy types
        return obj.item()
    else:
        return obj

def fetch_html_js(url):
    """Fetch fully rendered HTML using Playwright"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_load_state("networkidle")
        html = page.content()
        browser.close()
        return html

def clean_soup(soup):
    for tag in soup(["script", "style", "nav", "footer", "aside", "noscript"]):
        tag.decompose()
    return soup

def extract_car_data_ner(url):
    try:
        # 1️⃣ Fetch JS-rendered HTML
        html = fetch_html_js(url)

        soup = BeautifulSoup(html, "html.parser")
        soup = clean_soup(soup)

        # 2️⃣ Extract visible text
        text = soup.get_text(separator=" ")
        text = re.sub(r"\s+", " ", text)
        text = text[:3000]  # Keep NER fast

        # 3️⃣ Run NER
        raw_entities = ner(text)
        entities = make_json_safe(raw_entities)

        brands_models = []
        for ent in entities:
            if ent["entity_group"] in ("ORG", "MISC"):
                brands_models.append(ent["word"])

        # 4️⃣ Price extraction (regex still best)
        price_match = re.search(
            r"(₹|\$|€|INR|USD|EUR)\s?[\d,]+(\.\d+)?",
            text
        )
        price = price_match.group(0) if price_match else None

        # 5️⃣ Images
        images = [
            img.get("src")
            for img in soup.find_all("img")
            if img.get("src") and not img.get("src").startswith("data:")
        ]

        return {
            "success": True,
            "data": {
                "possible_model_names": list(set(brands_models))[:10],
                "price": price,
                "entities": entities[:15],
                "images": images[:10]
            }
        }

    except PlaywrightTimeout:
        return {
            "success": False,
            "error": "Page load timed out (JS-heavy site)"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.route("/extract", methods=["POST"])
def extract_ner():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"success": False, "error": "Missing url"}), 400

    return jsonify(extract_car_data_ner(data["url"]))

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5002)