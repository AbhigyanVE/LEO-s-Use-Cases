import os
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

def extract_car_data(url):
    try:
        # 1. Fetch webpage
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 2. Clean HTML - remove scripts, styles, nav, footer
        for tag in soup(['script', 'style', 'nav', 'footer']):
            tag.decompose()
        
        # 3. Extract all images
        images = [img['src'] for img in soup.find_all('img') if img.get('src')]
        
        # 4. Get main content
        content = soup.get_text(separator='\n', strip=True)
        
        # 5. Use GPT-4 to extract structured data
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
        Extract car information from this webpage content and return as JSON:
        
        Content: {content[:8000]}
        Images: {images}
        
        Return JSON with:
        {{
          "model_name": "",
          "variant": "",
          "price": "",
          "specifications": {{}},
          "features": [],
          "images": {{"exterior": [], "interior": [], "other": []}},
          "description": ""
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        # Extract token usage
        usage = response.usage
        token_info = {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens
        }
        
        # Print token usage to terminal
        print(f"\n{'='*50}")
        print(f"TOKEN USAGE:")
        print(f"  Prompt tokens: {usage.prompt_tokens}")
        print(f"  Completion tokens: {usage.completion_tokens}")
        print(f"  Total tokens: {usage.total_tokens}")
        print(f"{'='*50}\n")
        
        return {
            "success": True,
            "data": response.choices[0].message.content,
            "token_usage": token_info
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.route('/extract', methods=['POST'])
def extract():
    """
    API endpoint to extract car data from a URL
    
    Request JSON:
    {
        "url": "https://example.com/car-listing"
    }
    
    Response JSON:
    {
        "success": true,
        "data": {...},
        "token_usage": {...}
    }
    """
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({
            "success": False,
            "error": "Missing 'url' in request body"
        }), 400
    
    url = data['url']
    result = extract_car_data(url)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    # Check if API key is loaded
    if not os.getenv('OPENAI_API_KEY'):
        print("WARNING: OPENAI_API_KEY not found in environment variables!")
        print("Please create a .env file with: OPENAI_API_KEY=your_api_key_here")
    
    app.run(debug=True, host='0.0.0.0', port=5000)