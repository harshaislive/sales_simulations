import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
BASE_URL = "https://api.pipedrive.com/v1/pipelines"

def fetch_pipelines():
    if not API_TOKEN:
        print("Error: PIPEDRIVE_API_TOKEN not found.")
        return

    params = {"api_token": API_TOKEN}
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        pipelines = {}
        if 'data' in data:
            for pl in data['data']:
                pipelines[pl['id']] = pl['name']
                print(f"Pipeline {pl['id']}: {pl['name']}")
        
        with open('pipelines.json', 'w', encoding='utf-8') as f:
            json.dump(pipelines, f, indent=4)
        
        return pipelines

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_pipelines()
