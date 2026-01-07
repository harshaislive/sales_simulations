import json
import collections

def load_data():
    with open('deals.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_win_dna(deals):
    print("Analyzing Win DNA...")
    
    # Containers for analysis
    won_deals = [d for d in deals if d.get('status') == 'won']
    lost_deals = [d for d in deals if d.get('status') == 'lost']
    all_closed = won_deals + lost_deals
    
    total_won = len(won_deals)
    total_closed = len(all_closed)
    
    if total_closed == 0:
        print("No closed deals to analyze.")
        return

    global_win_rate = total_won / total_closed

    # --- 1. DEAL VALUE ANALYSIS ---
    # Bucketize values: <10k, 10k-50k, 50k-100k, 100k-500k, 500k+
    value_buckets = collections.defaultdict(lambda: {'won': 0, 'total': 0})
    
    for deal in all_closed:
        val = deal.get('value') or 0
        if val < 10000: bucket = "Under ₹10k"
        elif val < 50000: bucket = "₹10k - ₹50k"
        elif val < 100000: bucket = "₹50k - ₹100k"
        elif val < 500000: bucket = "₹100k - ₹500k"
        elif val < 1000000: bucket = "₹500k - ₹1M"
        else: bucket = "Over ₹1M"
        
        value_buckets[bucket]['total'] += 1
        if deal.get('status') == 'won':
            value_buckets[bucket]['won'] += 1

    # --- 2. OWNER ANALYSIS ---
    owner_stats = collections.defaultdict(lambda: {'won': 0, 'total': 0, 'value': 0})
    
    for deal in all_closed:
        owner = deal.get('owner_name') or "Unknown"
        owner_stats[owner]['total'] += 1
        if deal.get('status') == 'won':
            owner_stats[owner]['won'] += 1
            owner_stats[owner]['value'] += (deal.get('value') or 0)

    # --- OUTPUT REPORT ---
    print("\n" + "="*50)
    print(f"WIN DNA REPORT (Based on {total_closed} closed deals)")
    print(f"Global Win Rate: {global_win_rate:.2%}")
    print("="*50)

    print("\n--- WIN RATE BY DEAL SIZE ---")
    # Sort buckets by logical order is hard with strings, so I'll just print them in definition order if possible or list them explicitly
    ordered_buckets = ["Under ₹10k", "₹10k - ₹50k", "₹50k - ₹100k", "₹100k - ₹500k", "₹500k - ₹1M", "Over ₹1M"]
    
    for bucket in ordered_buckets:
        data = value_buckets[bucket]
        if data['total'] > 0:
            rate = data['won'] / data['total']
            print(f"{bucket:<15} | Win Rate: {rate:>6.1%} | Deals: {data['total']}")
        else:
             print(f"{bucket:<15} | Win Rate:    N/A | Deals: 0")

    print("\n--- PERFORMANCE BY OWNER ---")
    # Sort by Win Rate (descending)
    sorted_owners = sorted(owner_stats.items(), key=lambda x: (x[1]['won']/x[1]['total'] if x[1]['total'] > 0 else 0), reverse=True)
    
    for owner, data in sorted_owners:
        if data['total'] > 5: # Only show owners with significant activity
            rate = data['won'] / data['total']
            print(f"{owner:<20} | Win Rate: {rate:>6.1%} | Closed: {data['total']} | Won Rev: ₹{data['value']:,.0f}")

if __name__ == "__main__":
    deals = load_data()
    analyze_win_dna(deals)
