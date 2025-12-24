import os
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

# Load API Key
load_dotenv()
API_KEY = os.getenv("API_Key")

# Initialize the Client
client = genai.Client(api_key=API_KEY)

def generate_car_collage(image_paths, prompt, use_pro=True):
    # --- MODEL SWITCH ---
    # Nano Banana (Standard/Fast)
    model_id = "gemini-3-pro-image-preview" 
    
    # Nano Banana Pro (High Quality/Experimental)
    if use_pro:
        model_id = "nano-banana-pro-preview"

    print(f"Using Model: {model_id}")

    # Load local images into a list for the prompt
    contents = [prompt]
    for path in image_paths:
        try:
            img = Image.open(path)
            contents.append(img)
        except Exception as e:
            print(f"Could not load {path}: {e}")

    # Generate content
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=types.GenerateContentConfig(
                # You can add parameters like temperature here if needed
                candidate_count=1 
            )
        )

        # Process and save the output
        for i, part in enumerate(response.candidates[0].content.parts):
            if part.inline_data:
                # Convert bits to Image object using the SDK's helper
                generated_img = part.as_image()
                output_name = f"result_{i}.png"
                generated_img.save(output_name)
                print(f"Success! Saved to {output_name}")
            elif part.text:
                print(f"AI Feedback: {part.text}")

    except Exception as e:
        print(f"An error occurred during generation: {e}")

# --- CONFIGURATION ---

# Paths to your 3 input images
input_images = [
    r"C:\Users\abhigyansen\Downloads\LEO\BMW-X5\BMW-X5-P1.jpeg",
    r"C:\Users\abhigyansen\Downloads\LEO\BMW-X5\BMW-X5-P2.jpeg",
    r"C:\Users\abhigyansen\Downloads\LEO\BMW-X5\BMW-X5-P3.jpeg"
]

# Your specific prompt
car_prompt = (
    "These are 3 images of the same car, i want 12 images of this car from different perspectives "
    "in 1 single image. Place the car in a car showroom with high ceiling. There should be "
    "no humans or other cars in the surrounding. do not modify the car by adding additional "
    "accessories or changing the rims or colour of the car."
)

# Run the generation (Set use_pro=False for the faster/cheaper Nano Banana)
generate_car_collage(input_images, car_prompt, use_pro=False)