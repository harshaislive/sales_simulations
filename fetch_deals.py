import os
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
BASE_URL = "https://api.pipedrive.com/v1/deals"

def fetch_all_deals():
    if not API_TOKEN:
        print("Error: PIPEDRIVE_API_TOKEN not found in .env file.")
        return

    deals = []
    start = 0
    limit = 100  # Pipedrive default limit is usually 100, max 500
    more_items_in_collection = True

    print("Starting to fetch deals...")

    while more_items_in_collection:
        params = {
            "api_token": API_TOKEN,
            "start": start,
            "limit": limit
        }

        try:
            response = requests.get(BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if 'data' in data and data['data']:
                deals.extend(data['data'])
                print(f"Fetched {len(data['data'])} deals (Total: {len(deals)})")
            
            if 'additional_data' in data and 'pagination' in data['additional_data']:
                more_items_in_collection = data['additional_data']['pagination'].get('more_items_in_collection', False)
                start = data['additional_data']['pagination'].get('next_start', start + limit)
            else:
                more_items_in_collection = False
            
            # Be nice to the API
            time.sleep(0.2)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching deals: {e}")
            break
    
    print(f"Finished. Total deals fetched: {len(deals)}")
    
    with open('deals.json', 'w', encoding='utf-8') as f:
        json.dump(deals, f, ensure_ascii=False, indent=4)
    print("Saved to deals.json")

if __name__ == "__main__":
    fetch_all_deals()
