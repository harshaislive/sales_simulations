import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    exit(1)

supabase: Client = create_client(url, key)

def parse_date(date_str):
    if not date_str: return None
    try:
        # Pipedrive format: "2023-11-04 04:03:42"
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return dt.isoformat()
    except:
        return None

def migrate():
    print("Loading local data...")
    with open('deals.json', 'r', encoding='utf-8') as f:
        deals = json.load(f)

    print(f"Preparing {len(deals)} deals for migration...")
    
    batch = []
    batch_size = 100
    total_uploaded = 0

    for deal in deals:
        # Map Pipedrive JSON to Supabase Table Schema
        record = {
            "id": deal.get('id'),
            "title": deal.get('title'),
            "value": deal.get('value'),
            "currency": deal.get('currency'),
            "status": deal.get('status'),
            "stage_id": deal.get('stage_id'),
            "pipeline_id": deal.get('pipeline_id'),
            "owner_name": deal.get('owner_name'),
            "add_time": parse_date(deal.get('add_time')),
            "won_time": parse_date(deal.get('won_time')),
            "close_time": parse_date(deal.get('close_time')),
            "activities_count": deal.get('activities_count'),
            "notes_count": deal.get('notes_count'),
            "email_messages_count": deal.get('email_messages_count'),
            "org_name": deal.get('org_name'),
            "person_name": deal.get('person_name')
        }
        batch.append(record)

        if len(batch) >= batch_size:
            try:
                supabase.table("deals").upsert(batch).execute()
                total_uploaded += len(batch)
                print(f"Uploaded {total_uploaded}/{len(deals)} deals...")
                batch = []
            except Exception as e:
                print(f"Error uploading batch: {e}")
                # Optional: break or continue?
                
    # Upload remaining
    if batch:
        supabase.table("deals").upsert(batch).execute()
        total_uploaded += len(batch)
        print(f"Uploaded {total_uploaded}/{len(deals)} deals.")

    print("Migration Complete.")

if __name__ == "__main__":
    migrate()
