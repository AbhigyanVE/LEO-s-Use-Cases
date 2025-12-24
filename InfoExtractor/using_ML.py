import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def clean_soup(soup):
    for tag in soup(["script", "style", "nav", "footer", "aside", "noscript"]):
        tag.decompose()
    return soup

def extract_car_data_rule_based(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        soup = clean_soup(soup)

        # -------- TITLE / MODEL --------
        title = soup.title.string.strip() if soup.title else None
        h1 = soup.find("h1")
        model_name = h1.get_text(strip=True) if h1 else title

        # -------- PRICE --------
        text = soup.get_text(separator=" ")
        price_match = re.search(
            r"(₹|\$|€|INR|USD|EUR)\s?[\d,]+(\.\d+)?",
            text
        )
        price = price_match.group(0) if price_match else None

        # -------- SPECIFICATIONS --------
        specifications = {}
        for row in soup.find_all("tr"):
            cols = row.find_all(["th", "td"])
            if len(cols) == 2:
                key = cols[0].get_text(strip=True)
                val = cols[1].get_text(strip=True)
                if key and val:
                    specifications[key] = val

        # -------- FEATURES --------
        features = []
        for li in soup.find_all("li"):
            txt = li.get_text(strip=True)
            if 5 < len(txt) < 80:
                features.append(txt)

        features = list(dict.fromkeys(features))[:20]

        # -------- IMAGES --------
        images = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and not src.startswith("data:"):
                images.append(src)

        return {
            "success": True,
            "data": {
                "model_name": model_name,
                "price": price,
                "specifications": specifications,
                "features": features,
                "images": images[:10]
            }
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route("/extract", methods=["POST"])
def extract_rule():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"success": False, "error": "Missing url"}), 400

    return jsonify(extract_car_data_rule_based(data["url"]))

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5001)
