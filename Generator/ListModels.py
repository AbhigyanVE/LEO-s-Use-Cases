import os
from google import genai
from dotenv import load_dotenv

# Load API key
load_dotenv()
API_KEY = os.getenv("API_Key")

# Initialize client
client = genai.Client(api_key=API_KEY)

def list_models():
    print("Available models:\n")

    for model in client.models.list():
        print(f"Model ID: {model.name}")

        # Supported methods (important!)
        if hasattr(model, "supported_generation_methods"):
            print("  Supported methods:")
            for method in model.supported_generation_methods:
                print(f"   - {method}")

        print("-" * 60)

if __name__ == "__main__":
    list_models()
