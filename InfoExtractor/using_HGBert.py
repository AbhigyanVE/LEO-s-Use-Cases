import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from transformers import pipeline

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


# Load NER model once
ner = pipeline(
    "ner",
    model="dslim/bert-base-NER",
    aggregation_strategy="simple"
)

def clean_soup(soup):
    for tag in soup(["script", "style", "nav", "footer", "aside", "noscript"]):
        tag.decompose()
    return soup

def extract_car_data_ner(url):
    try:
        # response = requests.get(url, headers=HEADERS, timeout=25)
        response = requests.get(url, headers=HEADERS, timeout=25, stream=True)
        
        response.raise_for_status()
        html = response.content
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        soup = clean_soup(soup)

        text = soup.get_text(separator=" ")
        text = text[:3000]  # limit for speed

        entities = ner(text)

        brands_models = []
        for ent in entities:
            if ent["entity_group"] in ["ORG", "MISC"]:
                brands_models.append(ent["word"])

        price_match = re.search(
            r"(₹|\$|€|INR|USD|EUR)\s?[\d,]+(\.\d+)?",
            text
        )
        price = price_match.group(0) if price_match else None

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

    except Exception as e:
        return {"success": False, "error": str(e)}

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
