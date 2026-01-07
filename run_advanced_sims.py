import json
import random
import statistics
from datetime import datetime, timedelta
from collections import defaultdict

# --- CONFIGURATION ---
ITERATIONS = 5000  # 5k per simulation for speed/accuracy balance
TODAY = datetime.now()

def parse_date(date_str):
    if not date_str: return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except:
        return None

def load_data():
    with open('deals.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_stage_duration_stats(deals):
    """Calculates median days spent in each stage for WON deals"""
    # Simplified: We'll just look at age of open deals vs age of won deals
    won_durations = []
    for d in deals:
        if d['status'] == 'won' and d.get('add_time') and d.get('won_time'):
            start = parse_date(d['add_time'])
            end = parse_date(d['won_time'])
            if start and end:
                won_durations.append((end - start).days)
    
    if not won_durations: return 100
    return statistics.median(won_durations)

def calculate_base_rates(deals, recent_only=False):
    """
    Builds a map of Win Rates.
    If recent_only=True, only considers deals closed in last 180 days.
    """
    stats = defaultdict(lambda: {'won': 0, 'total': 0})
    
    cutoff = TODAY - timedelta(days=180) if recent_only else datetime.min

    for d in deals:
        if d['status'] not in ['won', 'lost']: continue
        
        close_time = parse_date(d.get('close_time')) or parse_date(d.get('update_time'))
        if not close_time or close_time < cutoff: continue

        stage_id = d.get('stage_id')
        owner = d.get('owner_name')
        
        # Track by Stage
        stats[f"stage_{stage_id}"]['total'] += 1
        if d['status'] == 'won': stats[f"stage_{stage_id}"]['won'] += 1
        
        # Track by Owner
        stats[f"owner_{owner}"]['total'] += 1
        if d['status'] == 'won': stats[f"owner_{owner}"]['won'] += 1
        
        # Global
        stats['global']['total'] += 1
        if d['status'] == 'won': stats['global']['won'] += 1

    rates = {}
    for key, val in stats.items():
        if val['total'] > 0:
            rates[key] = val['won'] / val['total']
        else:
            rates[key] = 0.0
            
    return rates

def get_probability(deal, scenario, rates, median_cycle):
    """
    Determines win probability for a single deal based on the scenario.
    """
    stage_id = deal.get('stage_id')
    owner = deal.get('owner_name')
    
    # 1. BASE RATE (Stage-based)
    base_prob = rates.get(f"stage_{stage_id}", rates.get('global', 0.01))
    
    if scenario == "Baseline":
        return base_prob

    elif scenario == "Owner_Performance":
        # Use owner specific rate, fallback to base
        return rates.get(f"owner_{owner}", base_prob)

    elif scenario == "Time_Decay":
        # If deal is older than 2x median cycle, prob drops by 80%
        created = parse_date(deal.get('add_time'))
        if created:
            age_days = (TODAY - created).days
            if age_days > (median_cycle * 2):
                return base_prob * 0.2
            elif age_days > median_cycle:
                return base_prob * 0.5
        return base_prob

    elif scenario == "Engagement_Weighted":
        # Boost if activity > 0
        activities = (deal.get('activities_count') or 0) + \
                     (deal.get('email_messages_count') or 0) + \
                     (deal.get('notes_count') or 0)
        
        if activities > 5: return min(base_prob * 1.5, 0.95) # Boost
        if activities == 0: return base_prob * 0.5 # Penalty
        return base_prob

    elif scenario == "Recent_Momentum":
        # Rates passed in should already be 'recent'
        return base_prob
        
    return base_prob

def run_simulation(scenario_name, open_deals, rates, median_cycle=None):
    results = []
    print(f"Running {scenario_name}...")
    
    for _ in range(ITERATIONS):
        revenue = 0
        for deal in open_deals:
            prob = get_probability(deal, scenario_name, rates, median_cycle)
            if random.random() < prob:
                revenue += (deal.get('value') or 0)
        results.append(revenue)
        
    results.sort()
    p10 = results[int(ITERATIONS * 0.1)] # Conservative (90% confident)
    p50 = results[int(ITERATIONS * 0.5)] # Median
    p90 = results[int(ITERATIONS * 0.9)] # Moonshot
    
    return p10, p50, p90

def generate_md_report(scenario, description, p10, p50, p90):
    content = f"""# Simulation Report: {scenario}

## Scenario Description
{description}

## Forecast Results
| Metric | Revenue Projection | Confidence |
| :--- | :--- | :--- |
| **Conservative** | **₹{p10:,.0f}** | 90% (Safe Floor) |
| **Base Case** | **₹{p50:,.0f}** | 50% (Most Likely) |
| **Moonshot** | **₹{p90:,.0f}** | 10% (Best Case) |

## Key Logic
- **Simulation Count:** {ITERATIONS} iterations
- **Data Source:** Active Pipeline (Stage 19 Excluded)
"""
    filename = f"simulations/md/{scenario.lower()}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved {filename}")

def main():
    deals = load_data()
    
    # Filter Active Deals (Exclude Stage 19 Ghost Deals)
    open_deals = [d for d in deals if d['status'] == 'open' and d.get('stage_id') != 19]
    
    # 1. Baseline Data
    all_time_rates = calculate_base_rates(deals, recent_only=False)
    recent_rates = calculate_base_rates(deals, recent_only=True)
    median_cycle = get_stage_duration_stats(deals)
    
    # --- SIMULATION 1: Baseline ---
    p10, p50, p90 = run_simulation("Baseline", open_deals, all_time_rates)
    generate_md_report("Baseline_Model", 
        "Uses historical conversion rates for each stage to predict future outcomes. The standard, steady-state view.", p10, p50, p90)

    # --- SIMULATION 2: Time Decay ---
    p10, p50, p90 = run_simulation("Time_Decay", open_deals, all_time_rates, median_cycle)
    generate_md_report("Time_Decay_Model", 
        f"Penalizes deals that are stagnant. Deals older than {median_cycle:.0f} days (median cycle) get a 50% probability cut. Deals older than 2x median get an 80% cut.", p10, p50, p90)

    # --- SIMULATION 3: Engagement Weighted ---
    p10, p50, p90 = run_simulation("Engagement_Weighted", open_deals, all_time_rates)
    generate_md_report("Engagement_Model", 
        "Adjusts win probability based on activity. Deals with >5 emails/calls/notes get a 1.5x boost. Silent deals (0 activity) get a 50% penalty.", p10, p50, p90)

    # --- SIMULATION 4: Owner Performance ---
    p10, p50, p90 = run_simulation("Owner_Performance", open_deals, all_time_rates)
    generate_md_report("Owner_Performance_Model", 
        "Uses the specific win rate of the Deal Owner (e.g., Rakesh's deals use Rakesh's 1.0% rate, not the global avg). Highly personalized.", p10, p50, p90)

    # --- SIMULATION 5: Recent Momentum ---
    p10, p50, p90 = run_simulation("Recent_Momentum", open_deals, recent_rates)
    generate_md_report("Recent_Momentum_Model", 
        "Uses only data from the last 180 days. Captures current market conditions and team performance trends, ignoring old history.", p10, p50, p90)

if __name__ == "__main__":
    main()
