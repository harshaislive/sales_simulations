import json
import random
import statistics
import os
from datetime import datetime, timedelta
from collections import defaultdict

# --- CONFIGURATION ---
ITERATIONS = 5000
TODAY = datetime.now()

# --- HELPER FUNCTIONS ---

def parse_date(date_str):
    if not date_str: return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except:
        return None

def load_data():
    with open('deals.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_pipelines():
    try:
        with open('pipelines.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def get_metadata(deals):
    """Extracts key stats for the report header"""
    if not deals:
        return {"count": 0, "value": 0, "start": "N/A", "end": "N/A"}
    
    count = len(deals)
    value = sum(d.get('value') or 0 for d in deals)
    
    # Date Range (based on creation date for open deals)
    dates = [parse_date(d.get('add_time')) for d in deals if d.get('add_time')]
    dates = [d for d in dates if d]
    
    if dates:
        start = min(dates).strftime("%b %Y")
        end = max(dates).strftime("%b %Y")
    else:
        start, end = "N/A", "N/A"
        
    return {"count": count, "value": value, "start": start, "end": end}

def get_stage_duration_stats(all_deals):
    """Global median days to win (for Time Decay model)"""
    won_durations = []
    for d in all_deals:
        if d['status'] == 'won' and d.get('add_time') and d.get('won_time'):
            start = parse_date(d['add_time'])
            end = parse_date(d['won_time'])
            if start and end:
                won_durations.append((end - start).days)
    return statistics.median(won_durations) if won_durations else 90

def calculate_rates(all_deals, recent_only=False):
    """Builds hierarchical win rates (Stage -> Pipeline -> Global)"""
    cutoff = TODAY - timedelta(days=180) if recent_only else datetime.min
    
    stage_stats = defaultdict(lambda: {'won': 0, 'total': 0})
    pipe_stats = defaultdict(lambda: {'won': 0, 'total': 0})
    owner_stats = defaultdict(lambda: {'won': 0, 'total': 0})
    global_stats = {'won': 0, 'total': 0}

    for d in all_deals:
        if d['status'] not in ['won', 'lost']: continue
        
        # Check date filter
        close_time = parse_date(d.get('close_time')) or parse_date(d.get('update_time'))
        if not close_time or close_time < cutoff: continue

        sid = d.get('stage_id')
        pid = str(d.get('pipeline_id'))
        owner = d.get('owner_name')
        
        # Aggregate
        for container, key in [
            (stage_stats, sid), 
            (pipe_stats, pid), 
            (owner_stats, owner)
        ]:
            container[key]['total'] += 1
            if d['status'] == 'won': container[key]['won'] += 1
            
        global_stats['total'] += 1
        if d['status'] == 'won': global_stats['won'] += 1

    # Convert to probabilities
    rates = {'stages': {}, 'pipelines': {}, 'owners': {}, 'global': 0.0}
    
    if global_stats['total'] > 0:
        rates['global'] = global_stats['won'] / global_stats['total']
        
    for k, v in stage_stats.items():
        if v['total'] > 0: rates['stages'][k] = v['won'] / v['total']
        
    for k, v in pipe_stats.items():
        if v['total'] > 0: rates['pipelines'][k] = v['won'] / v['total']

    for k, v in owner_stats.items():
        if v['total'] > 0: rates['owners'][k] = v['won'] / v['total']
        
    return rates

def get_prob(deal, model_type, rates, median_cycle):
    """Calculates specific deal probability based on the model"""
    sid = deal.get('stage_id')
    pid = str(deal.get('pipeline_id'))
    owner = deal.get('owner_name')
    
    # 1. Base Probability (Hierarchy: Stage -> Pipeline -> Global)
    base = rates['stages'].get(sid)
    if base is None: base = rates['pipelines'].get(pid)
    if base is None: base = rates['global']
    
    # 2. Apply Model Modifiers
    if model_type == "Baseline":
        return base
        
    elif model_type == "Owner Performance":
        # Use owner specific rate if available, else average
        return rates['owners'].get(owner, base)
        
    elif model_type == "Time Decay":
        created = parse_date(deal.get('add_time'))
        if created:
            age = (TODAY - created).days
            if age > (median_cycle * 2): return base * 0.2
            if age > median_cycle: return base * 0.5
        return base
        
    elif model_type == "Engagement Weighted":
        # Simple proxy for engagement
        acts = (deal.get('activities_count') or 0) + (deal.get('notes_count') or 0)
        if acts > 5: return min(base * 1.5, 0.95)
        if acts == 0: return base * 0.5
        return base
        
    elif model_type == "Recent Momentum":
        # Rates passed in are already time-filtered
        return base
        
    return base

def run_sim(open_deals, model_name, rates, median_cycle):
    if not open_deals: return 0, 0, 0
    
    results = []
    for _ in range(ITERATIONS):
        rev = 0
        for d in open_deals:
            prob = get_prob(d, model_name, rates, median_cycle)
            if random.random() < prob:
                rev += (d.get('value') or 0)
        results.append(rev)
        
    results.sort()
    return (
        results[int(ITERATIONS*0.1)], 
        results[int(ITERATIONS*0.5)], 
        results[int(ITERATIONS*0.9)]
    )

def save_report(scope_name, model_name, desc, results, meta):
    # Ensure directory exists
    safe_scope = scope_name.lower().replace(" ", "_")
    folder = f"simulations/md/{safe_scope}"
    os.makedirs(folder, exist_ok=True)
    
    filename = f"{folder}/{model_name.lower().replace(' ', '_')}.md"
    
    content = f"""# {scope_name}: {model_name} Forecast

## Executive Summary
**Base Case Projection:** ₹{results[1]:,.0f}

This report models your revenue using the **{model_name}** algorithm. 
It analyzes **{meta['count']} active deals** created between **{meta['start']}** and **{meta['end']}**.

## Forecast Scenarios
| Scenario | Probability | Revenue Projection | What it means |
| :--- | :--- | :--- | :--- |
| **Conservative** | 90% Confidence | **₹{results[0]:,.0f}** | The "Safe Bet". You rarely perform worse than this. |
| **Base Case** | 50% Confidence | **₹{results[1]:,.0f}** | The most likely statistical outcome. |
| **Moonshot** | 10% Confidence | **₹{results[2]:,.0f}** | Requires exceptional execution and luck. |

## Methodology Explained
**How this specific model works:**
{desc}

## Data Profile
- **Scope:** {scope_name}
- **Active Deals:** {meta['count']}
- **Total Pipeline Value:** ₹{meta['value']:,.0f}
- **Date Range:** {meta['start']} - {meta['end']}
- **Excluded:** "Ghost Deals" (Stage 19) and Lost deals.

---
*Generated by Gemini Monte Carlo Engine (v2.0) • {ITERATIONS} Iterations*
"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Generated: {filename}")

def main():
    # 1. Load Everything
    all_deals = load_data()
    pipeline_names = load_pipelines()
    
    # 2. Prepare Global Stats
    median_cycle = get_stage_duration_stats(all_deals)
    rates_all_time = calculate_rates(all_deals, recent_only=False)
    rates_recent = calculate_rates(all_deals, recent_only=True)
    
    # 3. Define Scopes (Global + Each Pipeline)
    # Filter out Stage 19 (Ghost) from EVERYTHING
    valid_deals = [d for d in all_deals if d.get('stage_id') != 19]
    
    scopes = {'Global Portfolio': [d for d in valid_deals if d['status'] == 'open']}
    
    # Group by Pipeline
    for d in valid_deals:
        if d['status'] == 'open':
            pid = d.get('pipeline_id')
            p_name = pipeline_names.get(str(pid), f"Pipeline {pid}")
            if p_name not in scopes: scopes[p_name] = []
            scopes[p_name].append(d)
            
    # 4. Run Simulations for Each Scope
    models = [
        ("Baseline", "Uses standard historical win rates for each stage. This is your 'Control' group."),
        ("Time Decay", f"Penalizes stagnation. Deals older than {median_cycle} days lose 50% probability. Older than {median_cycle*2} days lose 80%."),
        ("Engagement Weighted", "Rewards high activity. Deals with >5 touchpoints get a 1.5x probability boost. Silent deals get a 50% penalty."),
        ("Owner Performance", "Personalized forecasting. Uses the specific win rate of the deal owner (e.g., Rakesh vs Vivekanand) instead of company averages."),
        ("Recent Momentum", "Trend-based. Only uses data from the last 6 months. Ignores older history to capture current market reality.")
    ]
    
    print(f"Starting analysis for {len(scopes)} scopes...")
    
    for scope_name, deals in scopes.items():
        if not deals: continue
        print(f"--- Analyzing {scope_name} ({len(deals)} deals) ---")
        
        meta = get_metadata(deals)
        
        for model_name, desc in models:
            # Select correct rates
            rates = rates_recent if model_name == "Recent Momentum" else rates_all_time
            
            # Run Sim
            results = run_sim(deals, model_name, rates, median_cycle)
            
            # Save Report
            save_report(scope_name, model_name, desc, results, meta)

if __name__ == "__main__":
    main()
