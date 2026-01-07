import json

def fix_ghost_deals():
    print("Loading deals.json...")
    try:
        with open('deals.json', 'r', encoding='utf-8') as f:
            deals = json.load(f)
    except FileNotFoundError:
        print("Error: deals.json not found.")
        return

    count = 0
    ghost_value = 0

    print("Scanning for open deals in Ghost Stage (ID 19)...")

    for deal in deals:
        if deal.get('stage_id') == 19 and deal.get('status') == 'open':
            # MODIFY THE DEAL
            deal['status'] = 'lost'
            deal['lost_reason'] = 'Data Cleanup: Ghost Stage 19'
            
            # Track stats
            count += 1
            ghost_value += (deal.get('value') or 0)

    if count > 0:
        print(f"found {count} ghost deals.")
        print(f"Total value removed from pipeline: ₹{ghost_value:,.0f}")
        
        print("Saving updates to deals.json...")
        with open('deals.json', 'w', encoding='utf-8') as f:
            json.dump(deals, f, ensure_ascii=False, indent=4)
        print("Success! Database cleaned.")
    else:
        print("No open ghost deals found. The file might already be clean.")

if __name__ == "__main__":
    fix_ghost_deals()
