import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re

class CarDataExtractor:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.setup_folders()
    
    def setup_folders(self):
        """Create template and info folders if they don't exist"""
        os.makedirs('template', exist_ok=True)
        os.makedirs('info', exist_ok=True)
    
    def fetch_webpage(self, url):
        """Fetch webpage content"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"Error fetching webpage: {e}")
            return None
    
    def extract_template(self, url, soup, response):
        """Extract and save website template"""
        template_data = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'html_structure': str(soup.prettify()),
            'css_links': [],
            'js_links': [],
            'inline_styles': [],
            'meta_tags': []
        }
        
        # Extract CSS links
        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href')
            if href:
                full_url = urljoin(url, href)
                template_data['css_links'].append(full_url)
        
        # Extract JS links
        for script in soup.find_all('script'):
            src = script.get('src')
            if src:
                full_url = urljoin(url, src)
                template_data['js_links'].append(full_url)
        
        # Extract inline styles
        for style in soup.find_all('style'):
            if style.string:
                template_data['inline_styles'].append(style.string)
        
        # Extract meta tags
        for meta in soup.find_all('meta'):
            meta_dict = dict(meta.attrs)
            template_data['meta_tags'].append(meta_dict)
        
        return template_data
    
    def save_template(self, template_data, filename):
        """Save template data to file"""
        filepath = os.path.join('template', filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=2, ensure_ascii=False)
        print(f"✓ Template saved to: {filepath}")
    
    def save_info(self, info_data, filename):
        """Save info data to file"""
        filepath = os.path.join('info', filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(info_data, f, indent=2, ensure_ascii=False)
        print(f"✓ Info saved to: {filepath}")
    
    def extract_default_mode(self, url, soup):
        """Extract data in default mode (basic scraping)"""
        info = {
            'url': url,
            'mode': 'default',
            'timestamp': datetime.now().isoformat(),
            'title': soup.title.string if soup.title else 'No title',
            'headings': {},
            'text_content': [],
            'links': [],
            'images': []
        }
        
        # Extract headings
        for i in range(1, 7):
            headings = soup.find_all(f'h{i}')
            if headings:
                info['headings'][f'h{i}'] = [h.get_text(strip=True) for h in headings]
        
        # Extract paragraphs
        paragraphs = soup.find_all('p')
        info['text_content'] = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
        
        # Extract links
        links = soup.find_all('a', href=True)
        info['links'] = [{'text': a.get_text(strip=True), 'href': urljoin(url, a['href'])} for a in links[:50]]
        
        # Extract images
        images = soup.find_all('img')
        info['images'] = [{'alt': img.get('alt', ''), 'src': urljoin(url, img.get('src', ''))} for img in images[:30]]
        
        return info
    
    def extract_car_model(self, url, soup):
        """Extract car model specific data"""
        info = {
            'url': url,
            'mode': 'car_model',
            'timestamp': datetime.now().isoformat(),
            'car_name': '',
            'specifications': {},
            'features': [],
            'price_info': [],
            'images': [],
            'description': ''
        }
        
        # Try to extract car name from title or h1
        if soup.title:
            info['car_name'] = soup.title.string
        h1 = soup.find('h1')
        if h1:
            info['car_name'] = h1.get_text(strip=True)
        
        # Extract all tables (often contain specs)
        tables = soup.find_all('table')
        for idx, table in enumerate(tables):
            table_data = {}
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    table_data[key] = value
            if table_data:
                info['specifications'][f'table_{idx+1}'] = table_data
        
        # Extract features (look for lists)
        lists = soup.find_all(['ul', 'ol'])
        for lst in lists:
            items = lst.find_all('li')
            list_items = [item.get_text(strip=True) for item in items if item.get_text(strip=True)]
            if list_items and len(list_items) <= 30:
                info['features'].extend(list_items)
        
        # Extract price information (look for currency symbols or price keywords)
        price_pattern = re.compile(r'(?:₹|€|\$|£|price|cost|starting)[:\s]*[\d,\.]+', re.IGNORECASE)
        all_text = soup.get_text()
        price_matches = price_pattern.findall(all_text)
        info['price_info'] = list(set(price_matches[:10]))
        
        # Extract images
        images = soup.find_all('img')
        info['images'] = [
            {'alt': img.get('alt', ''), 'src': urljoin(url, img.get('src', ''))} 
            for img in images[:20]
        ]
        
        # Extract description from meta or paragraphs
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            info['description'] = meta_desc.get('content', '')
        else:
            paragraphs = soup.find_all('p')
            if paragraphs:
                info['description'] = ' '.join([p.get_text(strip=True) for p in paragraphs[:3]])
        
        return info
    
    def extract_car_dealer(self, url, soup):
        """Extract car dealer listings"""
        info = {
            'url': url,
            'mode': 'car_dealer',
            'timestamp': datetime.now().isoformat(),
            'dealer_name': '',
            'car_listings': [],
            'total_cars': 0,
            'categories': []
        }
        
        # Extract dealer/site name
        if soup.title:
            info['dealer_name'] = soup.title.string
        
        # Look for car listing patterns
        # Common patterns: divs with class containing 'card', 'listing', 'product', 'vehicle', 'car'
        potential_listings = soup.find_all(['div', 'article', 'li'], 
                                          class_=re.compile(r'(card|listing|product|vehicle|car|item)', re.I))
        
        for listing in potential_listings[:100]:  # Limit to 100 listings
            car_data = {}
            
            # Extract car name/title
            title_elem = listing.find(['h1', 'h2', 'h3', 'h4', 'a'])
            if title_elem:
                car_data['name'] = title_elem.get_text(strip=True)
            
            # Extract price
            price_elem = listing.find(text=re.compile(r'[₹€$£]\s*[\d,\.]+'))
            if price_elem:
                car_data['price'] = price_elem.strip()
            
            # Extract image
            img = listing.find('img')
            if img:
                car_data['image'] = urljoin(url, img.get('src', ''))
            
            # Extract link
            link = listing.find('a', href=True)
            if link:
                car_data['link'] = urljoin(url, link['href'])
            
            # Extract any additional text
            texts = listing.find_all(text=True)
            car_data['details'] = ' '.join([t.strip() for t in texts if t.strip()])[:200]
            
            if car_data.get('name') or car_data.get('price'):
                info['car_listings'].append(car_data)
        
        info['total_cars'] = len(info['car_listings'])
        
        # Extract categories/filters
        nav_items = soup.find_all(['nav', 'div'], class_=re.compile(r'(menu|nav|category|filter)', re.I))
        for nav in nav_items:
            links = nav.find_all('a')
            categories = [link.get_text(strip=True) for link in links if link.get_text(strip=True)]
            info['categories'].extend(categories[:20])
        
        info['categories'] = list(set(info['categories']))
        
        return info
    
    def process_url(self, url, flag=0):
        """Main processing function"""
        print(f"\n{'='*60}")
        print(f"Processing URL: {url}")
        print(f"Mode: {['Default', 'Car Model', 'Car Dealer'][flag]}")
        print(f"{'='*60}\n")
        
        # Fetch webpage
        response = self.fetch_webpage(url)
        if not response:
            print("❌ Failed to fetch webpage")
            return
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Generate filename from URL
        domain = urlparse(url).netloc.replace('www.', '').replace('.', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Extract and save template
        print("Extracting template...")
        template_data = self.extract_template(url, soup, response)
        template_filename = f"{domain}_template_{timestamp}.json"
        self.save_template(template_data, template_filename)
        
        # Extract and save info based on mode
        print("Extracting data...")
        if flag == 0:
            info_data = self.extract_default_mode(url, soup)
        elif flag == 1:
            info_data = self.extract_car_model(url, soup)
        elif flag == 2:
            info_data = self.extract_car_dealer(url, soup)
        else:
            print("❌ Invalid flag value")
            return
        
        info_filename = f"{domain}_info_{timestamp}.json"
        self.save_info(info_data, info_filename)
        
        # Print summary
        print(f"\n{'='*60}")
        print("EXTRACTION SUMMARY")
        print(f"{'='*60}")
        if flag == 1:
            print(f"Car Name: {info_data.get('car_name', 'N/A')}")
            print(f"Specifications Tables: {len(info_data.get('specifications', {}))}")
            print(f"Features Found: {len(info_data.get('features', []))}")
            print(f"Images Found: {len(info_data.get('images', []))}")
        elif flag == 2:
            print(f"Dealer: {info_data.get('dealer_name', 'N/A')}")
            print(f"Total Cars Found: {info_data.get('total_cars', 0)}")
            print(f"Categories Found: {len(info_data.get('categories', []))}")
        else:
            print(f"Title: {info_data.get('title', 'N/A')}")
            print(f"Headings Found: {sum(len(v) for v in info_data.get('headings', {}).values())}")
            print(f"Links Found: {len(info_data.get('links', []))}")
        print(f"{'='*60}\n")

def main():
    print("\n" + "="*60)
    print(" "*15 + "CAR DATA EXTRACTOR")
    print("="*60 + "\n")
    
    extractor = CarDataExtractor()
    
    # Get URL
    url = input("Enter the URL: ").strip()
    if not url:
        print("❌ URL cannot be empty")
        return
    
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Get flag
    flag_input = input("Enter flag (0=Default, 1=Car Model, 2=Car Dealer) [default=0]: ").strip()
    
    if flag_input == '':
        flag = 0
    else:
        try:
            flag = int(flag_input)
            if flag not in [0, 1, 2]:
                print("⚠ Invalid flag. Using default (0)")
                flag = 0
        except ValueError:
            print("⚠ Invalid input. Using default (0)")
            flag = 0
    
    # Process URL
    extractor.process_url(url, flag)
    
    print("\n✅ Extraction complete!\n")

if __name__ == "__main__":
    main()