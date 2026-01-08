import os
import json
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
BASE_URL = "https://api.pipedrive.com/v1"

def get_deal_flow(deal_id):
    url = f"{BASE_URL}/deals/{deal_id}/flow"
    params = {"api_token": API_TOKEN}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get('data', [])
    except Exception as e:
        print(f"Error fetching flow for deal {deal_id}: {e}")
        return []

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
             return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        except:
             return None

def generate_html_report(results, stages_metadata):
    """Generates a clean HTML report for won deal velocity."""
    now_str = datetime.now().strftime("%d %b %Y")
    
    valid_durations = [r['days_prospect_to_win'] for r in results if r['days_prospect_to_win'] is not None]
    avg_days = sum(valid_durations) / len(valid_durations) if valid_durations else 0
    
    # Calculate Velocity Cohorts (Exclusive Buckets)
    bucket_0_3m = sum(1 for d in valid_durations if d <= 90)
    bucket_3_6m = sum(1 for d in valid_durations if 90 < d <= 180)
    bucket_6_9m = sum(1 for d in valid_durations if 180 < d <= 270)
    bucket_9_12m = sum(1 for d in valid_durations if 270 < d <= 365)
    bucket_over_12m = sum(1 for d in valid_durations if d > 365)
    
    total_valid = len(valid_durations)
    total_deals = len(results)
    total_skipped = total_deals - total_valid
    
    rows_html = ""
    for r in results:
        p_date = r['prospect_entry_time'].strftime('%Y-%m-%d') if r['prospect_entry_time'] else "<span style='color:#999'>Direct Entry</span>"
        w_date = r['won_time'].strftime('%Y-%m-%d') if r['won_time'] else "N/A"
        days = f"{r['days_prospect_to_win']:.1f}" if r['days_prospect_to_win'] is not None else "<span style='color:#ccc'>-</span>"
        
        history_html = ""
        for sd in r['stage_durations']:
            dur = f"{sd['duration_days']:.1f}d" if sd['duration_days'] is not None else "Final"
            history_html += f"<li><span class='stage-date'>{sd['start_time'].strftime('%b %d, %Y')}</span>: {sd['stage_name']} <span class='stage-dur'>({dur})</span></li>"

        rows_html += f"""
        <tr>
            <td><strong>{r['title']}</strong><br><small>{r['owner']}</small></td>
            <td>{p_date}</td>
            <td>{w_date}</td>
            <td class="days-val">{days}</td>
            <td>
                <ul class="stage-list">
                    {history_html}
                </ul>
            </td>
        </tr>
        """

    # Calculate Won Date Range
    won_dates = [r['won_time'] for r in results if r['won_time']]
    if won_dates:
        min_date = min(won_dates).strftime("%d %b %Y")
        max_date = max(won_dates).strftime("%d %b %Y")
        date_range_str = f"{min_date} - {max_date}"
    else:
        date_range_str = "N/A"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Won Deal Velocity Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.5; color: #333; max-width: 1200px; margin: 40px auto; padding: 0 20px; background: #f9f9f9; }}
        h1 {{ border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 5px; }}
        .header-meta {{ color: #666; font-size: 0.95rem; margin-bottom: 40px; }}
        h2 {{ margin-top: 40px; border-bottom: 1px solid #ccc; padding-bottom: 5px; font-size: 1.5rem; }}
        
        .summary-cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 30px 0; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; border-top: 4px solid #000; }}
        .card .val {{ font-size: 2.5rem; font-weight: bold; display: block; }}
        .card .label {{ text-transform: uppercase; font-size: 0.8rem; color: #666; letter-spacing: 1px; }}
        
        .cohort-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 15px; margin-bottom: 40px; }}
        .cohort-box {{ background: #fff; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #ddd; }}
        .cohort-box .count {{ font-size: 2rem; font-weight: bold; color: #000; display: block; }}
        .cohort-box .title {{ font-size: 0.9rem; font-weight: 600; margin-bottom: 5px; display: block; }}
        .cohort-box .pct {{ font-size: 0.8rem; color: #666; }}
        .cohort-box.skipped {{ background: #fff0f0; border-color: #ffd0d0; }}

        .table-container {{ overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        table {{ width: 100%; border-collapse: collapse; background: white; min-width: 800px; }}
        th {{ background: #f4f4f4; text-align: left; padding: 12px; font-size: 0.85rem; text-transform: uppercase; color: #666; white-space: nowrap; }}
        td {{ padding: 12px; border-bottom: 1px solid #eee; vertical-align: top; }}
        .days-val {{ font-weight: bold; font-size: 1.1rem; }}
        .stage-list {{ margin: 0; padding: 0; list-style: none; font-size: 0.85rem; color: #555; }}
        .stage-date {{ color: #999; width: 85px; display: inline-block; }}
        .stage-dur {{ font-weight: 600; color: #333; }}
        small {{ color: #888; }}

        /* Mobile Responsiveness */
        @media (max-width: 768px) {{
            body {{ padding: 0 15px; margin: 20px auto; }}
            h1 {{ font-size: 1.8rem; }}
            .header-meta {{ font-size: 0.85rem; }}
            
            .summary-cards {{ grid-template-columns: 1fr; gap: 15px; }}
            .card .val {{ font-size: 2rem; }}
            
            .cohort-grid {{ grid-template-columns: repeat(2, 1fr); gap: 10px; }}
            .cohort-box {{ padding: 10px; }}
            .cohort-box .count {{ font-size: 1.5rem; }}
            
            th, td {{ padding: 10px; font-size: 0.9rem; }}
            .days-val {{ font-size: 1rem; }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>Won Deal Velocity: Prospect to Win</h1>
        <div class="header-meta">
            <strong>Data Range:</strong> {date_range_str} &bull; 
            <strong>Analysis Date:</strong> {now_str}
        </div>
    </header>

    <div class="summary-cards">
        <div class="card">
            <span class="val">{total_deals}</span>
            <span class="label">Total Won Deals</span>
        </div>
        <div class="card">
            <span class="val">{avg_days:.1f}</span>
            <span class="label">Avg Days (Prospect to Win)</span>
        </div>
        <div class="card">
            <span class="val">{total_valid}</span>
            <span class="label">Analyzed Velocity</span>
        </div>
    </div>

    <h2>Velocity Breakdown</h2>
    <p style="color: #666; margin-bottom: 20px;">Count of deals won within specific time ranges from becoming a prospect. (Total: {total_deals})</p>
    <div class="cohort-grid">
        <div class="cohort-box">
            <span class="title">0 - 3 Months</span>
            <span class="count">{bucket_0_3m}</span>
            <span class="pct">{bucket_0_3m/total_deals*100:.1f}%</span>
        </div>
        <div class="cohort-box">
            <span class="title">3 - 6 Months</span>
            <span class="count">{bucket_3_6m}</span>
            <span class="pct">{bucket_3_6m/total_deals*100:.1f}%</span>
        </div>
        <div class="cohort-box">
            <span class="title">6 - 9 Months</span>
            <span class="count">{bucket_6_9m}</span>
            <span class="pct">{bucket_6_9m/total_deals*100:.1f}%</span>
        </div>
        <div class="cohort-box">
            <span class="title">9 - 12 Months</span>
            <span class="count">{bucket_9_12m}</span>
            <span class="pct">{bucket_9_12m/total_deals*100:.1f}%</span>
        </div>
         <div class="cohort-box" style="background: #fafafa;">
            <span class="title">Over 12 Months</span>
            <span class="count">{bucket_over_12m}</span>
            <span class="pct">{bucket_over_12m/total_deals*100:.1f}%</span>
        </div>
        <div class="cohort-box skipped">
            <span class="title">No Prospect Phase</span>
            <span class="count">{total_skipped}</span>
            <span class="pct">{total_skipped/total_deals*100:.1f}%</span>
        </div>
    </div>
    <p style="font-size: 0.95rem; color: #555; background: #fff0f0; padding: 15px; border-left: 4px solid #ffd0d0; border-radius: 4px;">
        <strong>Note:</strong> Deals in the "No Prospect Phase" category skipped the standard prospecting stages (likely created directly in late stages like MOU or Closed). 
        These are identified as <strong>"Direct Entry"</strong> in the table below, as they technically had a 0-day prospecting cycle.
    </p>

    <h2>Detailed Deal History</h2>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Deal & Owner</th>
                    <th>Prospect Entry</th>
                    <th>Won Date</th>
                    <th>Days (P&rarr;W)</th>
                    <th>Full Stage Journey</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
</body>
</html>"""
    
    os.makedirs('reports', exist_ok=True)
    html_path = 'reports/won_deals_velocity_report.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML Report generated: {html_path}")

def main():
    if not API_TOKEN:
        print("Error: PIPEDRIVE_API_TOKEN not found.")
        return

    try:
        with open('deals.json', 'r', encoding='utf-8') as f:
            deals = json.load(f)
    except FileNotFoundError:
        print("deals.json not found.")
        return

    # Load stages and build maps
    pipeline_prospect_map = {} # pid -> {id, order}
    stage_orders = {} # id -> order
    stages = {} # id -> name
    
    try:
        with open('stages.json', 'r', encoding='utf-8') as f:
            stages_data = json.load(f)
            stage_list = stages_data['data'] if isinstance(stages_data, dict) else stages_data
            
            stages = {s['id']: s['name'] for s in stage_list}
            stage_orders = {s['id']: s.get('order_nr', 0) for s in stage_list}
            
            # Group by pipeline
            p_stages = {}
            for s in stage_list:
                pid = s.get('pipeline_id')
                if pid not in p_stages: p_stages[pid] = []
                p_stages[pid].append(s)
            
            # Find prospect stage for each pipeline
            for pid, s_list in p_stages.items():
                # Look for "Prospect"
                prospect = next((s for s in s_list if "Prospect" in s['name']), None)
                if prospect:
                    pipeline_prospect_map[pid] = {'id': prospect['id'], 'order': prospect.get('order_nr', 0)}
                else:
                    # Fallback: pick the middle stage? or 3rd?
                    pass
            
            # Manual Patch for Missing Legacy Stages
            # Stage 19 in Pipeline 3 appears in history but not in current stages.
            # It acts as an early stage (likely Lead In).
            if 3 in pipeline_prospect_map:
                stages[19] = "Legacy Lead In"
                stage_orders[19] = 0 # Force it to be early
                
    except Exception as e:
        print(f"Error loading stages: {e}")

    won_deals = [d for d in deals if d.get('status') == 'won']
    print(f"Found {len(won_deals)} won deals. Fetching history...")

    results = []
    for i, deal in enumerate(won_deals):
        deal_id = deal.get('id')
        title = deal.get('title')
        pipeline_id = deal.get('pipeline_id')
        print(f"[{i+1}/{len(won_deals)}] Processing '{title}'...")
        
        target_info = pipeline_prospect_map.get(pipeline_id)
        target_order = target_info['order'] if target_info else 999
        
        flow = get_deal_flow(deal_id)
        add_time = parse_date(deal.get('add_time'))
        
        stage_changes = []
        for item in flow:
            if item.get('object') == 'dealChange' and item.get('data', {}).get('field_key') == 'stage_id':
                data = item.get('data', {})
                new_sid = data.get('new_value')
                old_sid = data.get('old_value')
                ts = data.get('log_time') or item.get('timestamp')
                dt = parse_date(ts)
                if new_sid and dt:
                    stage_changes.append({'time': dt, 'new': int(new_sid), 'old': int(old_sid) if old_sid else None})
        
        stage_changes.sort(key=lambda x: x['time'])
        initial_sid = stage_changes[0]['old'] if stage_changes else deal.get('stage_id')
        
        timeline = []
        if add_time:
            timeline.append((add_time, int(initial_sid) if initial_sid else 0))
        for c in stage_changes:
            timeline.append((c['time'], c['new']))
            
        # Find entry to "Prospecting Phase"
        # Defined as: The first time it enters any stage with order <= Prospect Stage Order
        # This handles:
        # 1. Normal flow: Lead -> Prospect (Start here) -> Won
        # 2. Skipped Prospect: Lead (Start here) -> Negotiation -> Won
        # 3. Late Start: Negotiation (Start here) -> Won [Short cycle]
        
        prospect_entry_time = None
        
        if target_info:
            # 1. Exact match first
            for t, sid in timeline:
                if sid == target_info['id']:
                    prospect_entry_time = t
                    break
            
            # 2. If not found, look for earlier stages (Lead In etc)
            if not prospect_entry_time:
                for t, sid in timeline:
                    s_order = stage_orders.get(sid, 999)
                    # If we find a stage that is PRE-Prospect (or equal order but diff ID), assume cycle started here
                    if s_order <= target_order:
                        prospect_entry_time = t
                        break
        
        won_time = parse_date(deal.get('won_time'))
        days_pw = (won_time - prospect_entry_time).total_seconds() / 86400 if prospect_entry_time and won_time else None
        
        # Path and Durations
        path_stages = []
        last_s = None
        stage_durations = []
        for idx in range(len(timeline)):
            start_t, sid = timeline[idx]
            if sid != last_s:
                path_stages.append(str(sid))
                last_s = sid
            
            end_t = timeline[idx+1][0] if idx < len(timeline)-1 else won_time
            dur = (end_t - start_t).total_seconds() / 86400 if end_t and end_t > start_t else None
            stage_durations.append({"stage_id": sid, "stage_name": stages.get(sid, str(sid)), "start_time": start_t, "duration_days": dur})

        results.append({
            "id": deal_id, "title": title, "owner": deal.get('owner_name'),
            "prospect_entry_time": prospect_entry_time, "won_time": won_time,
            "days_prospect_to_win": days_pw, "path": "->".join(path_stages),
            "stage_durations": stage_durations
        })
        time.sleep(0.1)

    generate_html_report(results, stages)
    
    # Save JSON
    with open('won_deals_stage_analysis.json', 'w', encoding='utf-8') as f:
        json_out = []
        for r in results:
            rc = r.copy()
            rc['prospect_entry_time'] = rc['prospect_entry_time'].isoformat() if rc['prospect_entry_time'] else None
            rc['won_time'] = rc['won_time'].isoformat() if rc['won_time'] else None
            new_sd = []
            for sd in rc['stage_durations']:
                sdc = sd.copy()
                sdc['start_time'] = sdc['start_time'].isoformat()
                new_sd.append(sdc)
            rc['stage_durations'] = new_sd
            json_out.append(rc)
        json.dump(json_out, f, indent=4)

if __name__ == "__main__":
    main()