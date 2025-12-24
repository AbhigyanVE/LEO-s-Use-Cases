import os
import csv
import requests
import re
from bs4 import BeautifulSoup
from pathlib import Path

def parse_assets_notes():
    """Parses the assets/notes.txt file for headings and sections."""
    notes_path = Path("assets/notes.txt")
    if not notes_path.exists():
        return [], []

    content = notes_path.read_text(encoding='utf-8')
    
    # Extract Headings (Heading X: Text)
    headings = re.findall(r"Heading \d+:\s*(.*)", content)
    
    # Extract Sections
    sections = re.split(r"Section \d+", content)
    sections = [s.strip() for s in sections if s.strip() and not s.startswith("Headings")]
    
    return headings, sections

def create_template_app():
    # 1. Setup Folders
    base_dir = Path("downloads")
    template_dir = Path("saved_template")
    assets_dir = Path("assets")
    
    base_dir.mkdir(exist_ok=True)
    template_dir.mkdir(exist_ok=True)
    
    # Find the local image in assets (assumes one image exists)
    local_image = next(assets_dir.glob("*.[jJ][pP][gG]"), None) or \
                  next(assets_dir.glob("*.[pP][nN][gG]"), None) or \
                  next(assets_dir.glob("*.[wW][eE][bB][pP]"), None)

    # 2. Get Input and Sequential Logic
    url = input("Enter the URL to use as a layout: ").strip()
    existing = [d for d in base_dir.iterdir() if d.is_dir() and d.name.isdigit()]
    next_num = max([int(d.name) for d in existing], default=0) + 1
    folder_name = f"{next_num:02d}"
    
    print(f"Fetching layout from {url}...")

    try:
        # 3. Fetch HTML (Fast because we don't download sub-assets)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0.0.0'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 4. Load User Data
        user_headings, user_sections = parse_assets_notes()
        
        # 5. TRANSFORM: Replace Images
        # We point them to the local asset and force them to stretch/squeeze
        if local_image:
            relative_image_path = f"../assets/{local_image.name}"
            for img in soup.find_all('img'):
                img['src'] = relative_image_path
                # Apply CSS to stretch/squeeze as requested
                img['style'] = "object-fit: fill; width: 100%; height: 100%;"
                if img.has_attr('srcset'): del img['srcset']

        # 6. TRANSFORM: Replace Headings (up to 10)
        heading_tags = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5'])
        for i, tag in enumerate(heading_tags[:10]):
            if i < len(user_headings):
                tag.string = user_headings[i]

        # 7. TRANSFORM: Replace Paragraphs with Sections
        p_tags = soup.find_all('p')
        section_count = len(user_sections)
        if section_count > 0:
            for i, p in enumerate(p_tags):
                # Cycle through sections if there are more paragraphs than content
                p.string = user_sections[i % section_count]

        # 8. SAVE TEMPLATE
        with open(template_dir / "index.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())

        # 9. LOG TO CSV
        csv_path = base_dir / "notes.csv"
        file_exists = csv_path.exists()
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["folder_name", "input_url"])
            writer.writerow([folder_name, url])
            
        # Create the numbered folder just to maintain the directory structure
        (base_dir / folder_name).mkdir(exist_ok=True)

        print(f"\nDone!")
        print(f"Template saved in: {template_dir}/index.html")
        print(f"Log updated in: {csv_path}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_template_app()