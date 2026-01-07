import json
import csv

def generate_zombie_report():
    print("Loading data...")
    with open('deals.json', 'r', encoding='utf-8') as f:
        deals = json.load(f)

    # Filter for Bala's open deals
    zombies = [
        d for d in deals 
        if d.get('status') == 'open' and d.get('owner_name') == 'Bala'
    ]
    
    # Sort by Value (High to Low), treating None as 0
    zombies.sort(key=lambda x: x.get('value') or 0, reverse=True)
    
    output_file = 'bala_zombie_deals.csv'
    
    print(f"Found {len(zombies)} zombie deals. Writing to {output_file}...")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Deal ID', 'Title', 'Value', 'Currency', 'Org Name', 'Person Name', 'Created Date', 'Stage ID']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for deal in zombies:
            writer.writerow({
                'Deal ID': deal.get('id'),
                'Title': deal.get('title'),
                'Value': deal.get('value'),
                'Currency': deal.get('currency'),
                'Org Name': deal.get('org_name'),
                'Person Name': deal.get('person_name'),
                'Created Date': deal.get('add_time'),
                'Stage ID': deal.get('stage_id')
            })

    print("Done.")

if __name__ == "__main__":
    generate_zombie_report()
