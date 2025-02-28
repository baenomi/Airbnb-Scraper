'''
Needed:
pip install pandas
pip install requests
pip install selenium
pip install webdriver-manager
pip install beautifulsoup4
pip install colorama
'''

import time
import pandas as pd
import re
import requests
import random
import sys
import os
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timezone
from colorama import Fore, Style, init
from urllib.parse import urlparse

# Data
l = []
previous_data = []

# Data
if getattr(sys, 'frozen', False):
    script_dir = sys._MEIPASS
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))

config_path = os.path.join(script_dir, 'config.json')

init(autoreset=True)

def log_message(message, color):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{color}{timestamp} - {message}{Style.RESET_ALL}")

def Scrap_data(url, site_url):
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = json.load(file)
    except FileNotFoundError:
        log_message(f"Error: config.json not found in {config_path}")
        sys.exit(1)
    
    save_path = config['save_path']

    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless") # delete if u want to see a chrome page
        service = Service(ChromeDriverManager().install())

        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        time.sleep(random.randint(3, 5))
        
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')

        allData = soup.find_all("div", {"itemprop": "itemListElement"})

        current_data = []

        if not allData:
            log_message("No offers found.", Fore.LIGHTRED_EX)
            return current_data

        for i in range(len(allData)):
            o = {}

            # Skip listings in surrounding area - delete section if u dont want to skip it
            if allData[i].find_parent(attrs={"data-testid": "content-scroller"}):
                continue
            
            # Scrap title
            try:
                title = allData[i].find('div', {'data-testid': 'listing-card-title'})
                o["property-title"] = title.text.strip() if title else None
            except AttributeError:
                o["property-title"] = None

            # Scrap rating
            try:
                rating_element = allData[i].find('div', {'class': 't1a9j9y7'})
                if rating_element and rating_element.text.strip():
                    rating_text = rating_element.text.strip()

                    match = re.search(r'(\d+,\d+)(?=\sna\s5)', rating_text)
                    if match:
                        rating = match.group(1)
                        rating = rating.replace(',', '.')
                        
                        if rating.replace('.', '', 1).isdigit():
                            o["rating"] = rating
                        else:
                            o["rating"] = "New offer!"
                    else:
                        o["rating"] = "New offer!"
                else:
                    o["rating"] = "undefined"
            except AttributeError:
                o["rating"] = "undefined"

            # Scrap price per day with all taxes
            try:
                price_element = allData[i].find('div', {'data-testid': 'price-availability-row'})
                if price_element:
                    price_span = price_element.find('span', {'class': '_hb913q'})
                    if price_span and price_span.text.strip():
                        price_text = re.search(r"([^\d]*)([\d\s]+)(\D*)", price_span.text)
                        if price_text:
                            currency_before = price_text.group(1).strip()
                            price_value = price_text.group(2).strip()
                            currency_after = price_text.group(3).strip()
                            currency = currency_before if currency_before else currency_after
                            o["price/day"] = f"{price_value} {currency}"
                        else:
                            o["price/day"] = None
                    else:
                        o["price/day"] = None
                else:
                    o["price/day"] = None
            except AttributeError:
                o["price/day"] = None

            # Scrap the URL of the listing
            try:
                listing_url = allData[i].find('a', href=True)
                if listing_url:
                    o["listing_url"] = site_url + listing_url['href']
                else:
                    o["listing_url"] = None
            except AttributeError:
                o["listing_url"] = None

            # Scrap the image URL
            try:
                img_element = allData[i].find('img', {'data-original-uri': True})
                if img_element and 'data-original-uri' in img_element.attrs:
                    o["image_url"] = img_element['data-original-uri']
                else:
                    o["image_url"] = None
            except AttributeError:
                o["image_url"] = None

            # Add the offer to current_data
            current_data.append(o)

        # Convert to DataFrame and save as CSV if data has changed
        if save_path:
            try:
                if current_data != previous_data:
                    pd.DataFrame(current_data).to_csv(save_path, index=False, encoding='utf-8')
                    log_message(f"Data saved to CSV: {save_path}", Fore.GREEN)
            except Exception as e:
                log_message(f"Error saving data to CSV: {e}", Fore.RED)

        return current_data
    except Exception as e:
        log_message(f"Error occurred in Scrap_data: {str(e)}", Fore.RED)
        return []

def send_webhook(new_data, previous_data, webhook_url, content):

    embeds = []
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    seen_offers = {offer['property-title'] + offer['price/day'] for offer in previous_data}

    for offer in new_data:
        location = offer.get('property-title', 'undefined')
        price_day = offer.get('price/day', 'undefined')

        offer_key = location + price_day

        if offer_key in seen_offers:
            continue

        link = offer.get('listing_url', 'undefined')
        rating = offer.get('rating', 'undefined')
        image_url = offer.get('image_url', 'undefined')

        embed = {
            "title": "New offer found!",
            "url": link,
            "color": 0x1E90FF, #change color if u want
            "thumbnail": {
                "url": image_url,
            },
            "fields": [
                {
                    "name": "Location",
                    "value": location,
                    "inline": True
                },
                {
                    "name": "Price/one day",
                    "value": price_day,
                    "inline": False
                },
                {
                    "name": "Rating",
                    "value": rating,
                    "inline": True
                }
            ],
            "footer": {
                "text": "Airbnb Scraper",
            },
            "timestamp": timestamp
        }

        embeds.append(embed)

    if embeds:
        payload = {
            "content": content, # IN CONFIG, examples: <@your_user_id> for pinging selected user / @everyone
            "embeds": embeds
        }
        try:
            response = requests.post(webhook_url, json=payload)
            if response.status_code in [200, 204]:
                log_message("Webhook sent successfully!", Fore.GREEN)
            else:
                log_message(f"Failed to send webhook. Status code: {response.status_code}", Fore.RED)
        except Exception as e:
            log_message(f"Error sending webhook: {str(e)}", Fore.RED)

def detect_changes(current_data, previous_data):
    new_offers = []
    for offer in current_data:
        if isinstance(offer, dict):
            location = offer.get('property-title', 'undefined')
            price_day = offer.get('price/day', 'undefined')

            if not any(o.get('property-title') == location and o.get('price/day') == price_day for o in previous_data):
                new_offers.append(offer)

    return new_offers

def main():
    url = input("Paste an URL with your filters: ")
    
    if not url:
        print("No URL provided, exiting...")
        return
    
    parsed_url = urlparse(url)
    site_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    previous_data = []
    
    while True:
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = json.load(file)
        except FileNotFoundError:
            log_message(f"Error: config.json not found in {config_path}")
            sys.exit(1)
        
        webhook_url = config['webhook_url']
        content = config['content']

        log_message("Fetching new data...", Fore.LIGHTCYAN_EX)
        current_data = Scrap_data(url, site_url)

        if current_data:
            new_data = detect_changes(current_data, previous_data)
            if new_data:
                if webhook_url:
                    log_message("New offer/s found, sending webhook!", Fore.GREEN)
                    send_webhook(new_data, previous_data, webhook_url, content)
                    previous_data = current_data
                    log_message("Awaiting the next attempt...", Fore.YELLOW)
                else:
                    log_message("New offer/s found, but no webhook provided.", Fore.LIGHTGREEN_EX)
            else:
                log_message("No new data detected, awaiting the next attempt...", Fore.YELLOW)
        else:
            log_message("Failed to fetch data, retrying...", Fore.RED)
        
        # Choose scraping delay (in this example, 3 minutes)
        time.sleep(3*60)

if __name__ == "__main__":
    main()
