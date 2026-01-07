import json
import random
import statistics
from collections import defaultdict

def load_data():
    with open('deals.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def build_stage_map(deals):
    """
    Returns nested dict:
    {
        'stages': { stage_id: prob },
        'pipelines': { pipeline_id: prob },
        'global': prob
    }
    """
    stage_stats = defaultdict(lambda: {'won': 0, 'total': 0})
    pipeline_stats = defaultdict(lambda: {'won': 0, 'total': 0})
    global_stats = {'won': 0, 'total': 0}
    
    for deal in deals:
        status = deal.get('status')
        stage_id = deal.get('stage_id')
        pipeline_id = str(deal.get('pipeline_id'))
        
        if status in ['won', 'lost']:
            # Global
            global_stats['total'] += 1
            if status == 'won': global_stats['won'] += 1
            
            # Pipeline
            pipeline_stats[pipeline_id]['total'] += 1
            if status == 'won': pipeline_stats[pipeline_id]['won'] += 1
            
            # Stage (Only the final stage is recorded in 'stage_id' for closed deals usually,
            # but we use this as a proxy for "deals reaching this stage")
            stage_stats[stage_id]['total'] += 1
            if status == 'won': stage_stats[stage_id]['won'] += 1

    probs = {
        'stages': {},
        'pipelines': {},
        'global': 0.0
    }
    
    # 1. Global Rate
    if global_stats['total'] > 0:
        probs['global'] = global_stats['won'] / global_stats['total']
        
    # 2. Pipeline Rates
    for pid, stats in pipeline_stats.items():
        if stats['total'] > 0:
            probs['pipelines'][pid] = stats['won'] / stats['total']
            
    # 3. Stage Rates
    for sid, stats in stage_stats.items():
        if stats['total'] > 0:
            probs['stages'][sid] = stats['won'] / stats['total']
            
    return probs

def run_simulation(open_deals, probability_map, iterations=10000):
    print(f"Simulating {len(open_deals)} open deals over {iterations} iterations...")
    
    simulation_results = []
    
    for i in range(iterations):
        total_revenue = 0
        
        for deal in open_deals:
            stage_id = deal.get('stage_id')
            pipeline_id = str(deal.get('pipeline_id'))
            value = deal.get('value') or 0
            
            # Smart Probability Lookup
            # 1. Try Specific Stage
            win_prob = probability_map['stages'].get(stage_id)
            
            # 2. If no history for stage, use Pipeline Average
            if win_prob is None:
                win_prob = probability_map['pipelines'].get(pipeline_id)
                
            # 3. If no history for pipeline, use Global Average
            if win_prob is None:
                win_prob = probability_map['global']
            
            # Roll the dice
            if random.random() < win_prob:
                total_revenue += value
                
        simulation_results.append(total_revenue)
        
    return simulation_results

def generate_report(results):
    results.sort()
    n = len(results)
    
    # Calculate confidence intervals
    conservative = results[int(n * 0.10)] # 90% chance to beat this (Conservative)
    likely = statistics.median(results)     # 50% chance (Base Case)
    optimistic = results[int(n * 0.90)]   # 10% chance to beat this (Moonshot)
    
    print("\n" + "="*40)
    print("MONTE CARLO REVENUE FORECAST (Next 90 Days)")
    print("="*40)
    print(f"Conservative (90% Confidence): ${conservative:,.0f}")
    print(f"Base Case    (50% Confidence): ${likely:,.0f}")
    print(f"Moonshot     (10% Confidence): ${optimistic:,.0f}")
    print("="*40)
    
    return conservative, likely, optimistic

def load_pipelines():
    try:
        with open('pipelines.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def main():
    deals = load_data()
    pipelines_map = load_pipelines()
    
    # 1. Train the model on historical data
    closed_deals = [d for d in deals if d.get('status') in ['won', 'lost']]
    stage_probs = build_stage_map(closed_deals)
    
    # 2. Identify open deals (Excluding Stage 19)
    # Group by Pipeline
    pipeline_groups = defaultdict(list)
    all_open_deals = []

    for d in deals:
        if d.get('status') == 'open' and d.get('stage_id') != 19:
            pid = str(d.get('pipeline_id')) # JSON keys are strings
            pipeline_groups[pid].append(d)
            all_open_deals.append(d)

    if not all_open_deals:
        print("No open deals found to forecast.")
        return

    # 3. Run Simulation PER PIPELINE
    print(f"\nRunning Simulations across {len(pipeline_groups)} pipelines...\n")
    
    overall_report_data = []

    # First, run for the specific pipelines found
    for pid, p_deals in pipeline_groups.items():
        p_name = pipelines_map.get(pid, f"Pipeline {pid}")
        print(f"--- Simulating: {p_name} ({len(p_deals)} deals) ---")
        
        results = run_simulation(p_deals, stage_probs)
        cons, base, moon = generate_report(results)
        
        overall_report_data.append({
            "name": p_name,
            "count": len(p_deals),
            "conservative": cons,
            "base": base,
            "moonshot": moon
        })

    # 4. Run Aggregate Simulation (Total)
    print(f"--- Simulating: ENTIRE PORTFOLIO ({len(all_open_deals)} deals) ---")
    results = run_simulation(all_open_deals, stage_probs)
    cons, base, moon = generate_report(results)
    
    # Save results to JSON for the HTML report generator to use
    final_output = {
        "pipelines": overall_report_data,
        "total": {
            "name": "Total Portfolio",
            "count": len(all_open_deals),
            "conservative": cons,
            "base": base,
            "moonshot": moon
        }
    }
    
    with open('forecast_results.json', 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=4)
    print("\nResults saved to forecast_results.json")

if __name__ == "__main__":
    main()
