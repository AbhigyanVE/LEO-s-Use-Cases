import os
import csv
import json
from pathlib import Path

import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

CSV_FILE = "data.csv"


# -------------------- CSV INITIALIZATION --------------------
def init_csv():
    if not Path(CSV_FILE).exists():
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "url",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "response_json"
            ])


# -------------------- CACHE LOOKUP (EXACT MATCH) --------------------
def get_cached_result(url):
    if not Path(CSV_FILE).exists():
        return None

    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["url"] == url:  # exact string match
                return json.loads(row["response_json"])

    return None


# -------------------- SAVE RESULT TO CSV --------------------
def save_to_csv(url, usage, response_json):
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            url,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
            json.dumps(response_json, ensure_ascii=False)
        ])


# -------------------- CORE EXTRACTION LOGIC --------------------
def extract_car_data(url):
    try:
        # 1️⃣ Check cache first
        cached = get_cached_result(url)
        if cached:
            print(f"[CACHE HIT] {url}")
            return {
                "success": True,
                "data": cached
            }

        # 2️⃣ Fetch webpage
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # 3️⃣ Clean HTML
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        # 4️⃣ Extract images
        images = [img["src"] for img in soup.find_all("img") if img.get("src")]

        # 5️⃣ Extract text
        content = soup.get_text(separator="\n", strip=True)

        # 6️⃣ OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found")

        client = OpenAI(api_key=api_key)

        prompt = f"""
Extract car information from this webpage content and return ONLY valid JSON.

Content:
{content[:8000]}

Images:
{images}

Return JSON with this structure:
{{
  "model_name": "",
  "variant": "",
  "price": "",
  "specifications": {{}},
  "features": [],
  "images": {{
    "exterior": [],
    "interior": [],
    "other": []
  }},
  "description": ""
}}
"""

        # 7️⃣ LLM call
        completion = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        usage = completion.usage

        # 8️⃣ Print token usage (terminal only)
        print("\n" + "=" * 50)
        print("TOKEN USAGE")
        print(f"Prompt tokens:     {usage.prompt_tokens}")
        print(f"Completion tokens: {usage.completion_tokens}")
        print(f"Total tokens:      {usage.total_tokens}")
        print("=" * 50 + "\n")

        # 9️⃣ Parse response JSON
        llm_json = json.loads(completion.choices[0].message.content)

        # 🔟 Save to CSV
        save_to_csv(url, usage, llm_json)

        return {
            "success": True,
            "data": llm_json
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# -------------------- API ENDPOINTS --------------------
@app.route("/extract", methods=["POST"])
def extract():
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({
            "success": False,
            "error": "Missing 'url' in request body"
        }), 400

    result = extract_car_data(data["url"])

    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


# -------------------- APP START --------------------
if __name__ == "__main__":
    init_csv()

    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not found in environment variables")

    app.run(debug=True, host="0.0.0.0", port=5000)