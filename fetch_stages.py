import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
BASE_URL = "https://api.pipedrive.com/v1/stages"

def fetch_stages():
    if not API_TOKEN:
        print("Error: PIPEDRIVE_API_TOKEN not found.")
        return

    params = {"api_token": API_TOKEN}
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        stages = {}
        if 'data' in data:
            for stage in data['data']:
                stages[stage['id']] = stage['name']
                print(f"Stage {stage['id']}: {stage['name']}")
        
        return stages

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_stages()
