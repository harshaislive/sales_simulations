import json
import random
import statistics
import os
from datetime import datetime, timedelta
from collections import defaultdict
from supabase import create_client
from dotenv import load_dotenv
import requests

load_dotenv()

# --- SUPABASE CONNECTION ---
def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key: return None
    return create_client(url, key)

# --- DATA LOADING ---
def load_data():
    """
    Fetches all deals from Supabase. 
    In a production app with millions of rows, you'd paginate or filter.
    For 7,000 rows, fetching all is fine for analysis context.
    """
    supabase = get_supabase()
    if not supabase:
        print("Supabase not configured. Falling back to local.")
        try:
            with open('deals.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    
    print("Fetching live data from Supabase...")
    try:
        # Fetch in chunks if Supabase limits to 1000
        all_rows = []
        offset = 0
        limit = 1000
        while True:
            response = supabase.table("deals").select("*").range(offset, offset + limit - 1).execute()
            rows = response.data
            if not rows: break
            all_rows.extend(rows)
            offset += limit
            print(f"Loaded {len(all_rows)} rows...")
            
        print(f"Total loaded: {len(all_rows)}")
        return all_rows
    except Exception as e:
        print(f"Error fetching from Supabase: {e}")
        return []

def load_pipelines():
    try:
        with open('pipelines.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def _coerce_int(value):
    try:
        if value is None: return None
        return int(value)
    except:
        return None

def load_stage_metadata(deals):
    """
    Returns a dict of stage_id -> metadata with name, pipeline_id, and order_nr.
    Prefers Supabase->stages, then stages.json, fellbacks to observed deals.
    """
    stage_rows = []
    supabase = get_supabase()
    if supabase:
        try:
            resp = supabase.table("stages").select("*").execute()
            stage_rows = resp.data or []
        except Exception as e:
            print(f"Error fetching stages from Supabase: {e}")
    
    if not stage_rows:
        try:
            with open('stages.json', 'r', encoding='utf-8') as f:
                stage_rows = json.load(f)
        except FileNotFoundError:
            stage_rows = []
        except Exception as e:
            print(f"Error reading stages.json: {e}")
            stage_rows = []
    
    if not stage_rows:
        stage_rows = fetch_stages_from_pipedrive()
        if stage_rows:
            cache_stage_rows(stage_rows)

    if isinstance(stage_rows, dict):
        if 'data' in stage_rows and isinstance(stage_rows['data'], list):
            stage_rows = stage_rows['data']
        else:
            stage_rows = [{"id": k, "name": v} for k, v in stage_rows.items()]
    
    metadata = {}
    for row in stage_rows:
        sid = row.get('id') or row.get('stage_id')
        if sid is None: continue
        sid_str = str(sid)
        pid = row.get('pipeline_id')
        pid_str = str(pid) if pid is not None else None
        order_val = None
        for key in ('order_nr', 'order', 'order_no', 'index', 'sequence'):
            val = _coerce_int(row.get(key))
            if val is not None:
                order_val = val
                break
        name = row.get('name') or row.get('label') or row.get('display_name') or f"Stage {sid}"
        metadata[sid_str] = {
            "id": sid_str,
            "name": name,
            "pipeline_id": pid_str,
            "order": order_val
        }
    
    if not metadata:
        # Fall back to inferring from deals
        for d in deals:
            sid = d.get('stage_id')
            if sid is None: continue
            sid_str = str(sid)
            if sid_str in metadata: continue
            pid = d.get('pipeline_id')
            metadata[sid_str] = {
                "id": sid_str,
                "name": f"Stage {sid}",
                "pipeline_id": str(pid) if pid is not None else None,
                "order": _coerce_int(d.get('stage_order_nr'))
            }
    # Ensure every entry has a display label
    for sid, data in metadata.items():
        order_val = data.get('order')
        label = data.get('name') or f"Stage {sid}"
        if order_val is not None:
            label = f"{order_val}. {label}"
        data['label'] = label
    return metadata

def fetch_stages_from_pipedrive():
    token = os.environ.get("PIPEDRIVE_API_TOKEN")
    if not token:
        return []
    base_url = os.environ.get("PIPEDRIVE_STAGE_URL", "https://api.pipedrive.com/v1/stages")
    params = {"api_token": token}
    try:
        resp = requests.get(base_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get('data') or []
    except Exception as e:
        print(f"Error fetching stages from Pipedrive: {e}")
        return []

def cache_stage_rows(rows):
    try:
        with open('stages.json', 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error caching stages.json: {e}")

def build_stage_filters(deals, pipelines):
    """
    Returns (stage_lookup, stage_groups_for_ui)
    """
    stage_lookup = load_stage_metadata(deals)
    pipeline_names = {str(k): v for k, v in pipelines.items()}
    grouped = defaultdict(list)
    
    for sid, data in stage_lookup.items():
        pid = data.get('pipeline_id') or "unmapped"
        display_name = data.get('name') or f"Stage {sid}"
        order_val = data.get('order')
        grouped[pid].append({
            "id": sid,
            "name": display_name,
            "label": data.get('label') or display_name,
            "order": order_val
        })
    
    stage_groups = []
    for pid, items in grouped.items():
        items.sort(key=lambda x: (x['order'] is None, x['order'] if x['order'] is not None else 0, x['name']))
        pipeline_label = pipeline_names.get(str(pid))
        if not pipeline_label:
            if pid == "unmapped":
                pipeline_label = "Unmapped Pipeline"
            else:
                pipeline_label = f"Pipeline {pid}"
        stage_groups.append({
            "pipeline_id": str(pid),
            "pipeline_name": pipeline_label,
            "stages": items
        })
    
    stage_groups.sort(key=lambda g: g['pipeline_name'])
    return stage_lookup, stage_groups

def identify_prospect_stage_ids(stage_lookup, deals=None, default_threshold=1):
    """
    Returns set of stage_ids (as strings) that should be treated as Prospect stages.
    Uses order <= threshold when available.
    """
    prospect_ids = set()
    for sid, data in stage_lookup.items():
        order_val = data.get('order')
        if order_val is not None and order_val <= default_threshold:
            prospect_ids.add(sid)
    # Fallback: if no order-based matches, take the three lowest-order stages.
    if not prospect_ids and stage_lookup:
        sorted_stages = sorted(
            stage_lookup.items(),
            key=lambda item: (
                item[1].get('order') is None,
                item[1].get('order') if item[1].get('order') is not None else 0
            )
        )
        for sid, _ in sorted_stages[:3]:
            prospect_ids.add(sid)
    if deals:
        for d in deals:
            order = d.get('stage_order_nr')
            if order is not None and order <= default_threshold:
                sid = d.get('stage_id')
                if sid is not None:
                    prospect_ids.add(str(sid))
    return prospect_ids

def collect_win_durations(all_deals):
    durations = []
    for d in all_deals:
        if d.get('status') == 'won' and d.get('add_time') and d.get('won_time'):
            start = parse_date(d.get('add_time'))
            end = parse_date(d.get('won_time'))
            if start and end:
                durations.append((end - start).days)
    return durations

def estimate_median_cycle(all_deals, default=90):
    durations = collect_win_durations(all_deals)
    if durations:
        return statistics.median(durations)
    return default

# --- HELPER UTILS ---
def parse_date(date_str):
    if not date_str: return None
    try: 
        # Handle ISO format from Supabase (often includes T and Z)
        # e.g. 2023-11-04T04:03:42+00:00
        date_str = date_str.replace('T', ' ').replace('Z', '')
        # Remove timezone offset if present for simple calculation
        if '+' in date_str: date_str = date_str.split('+')[0]
        if '.' in date_str: date_str = date_str.split('.')[0]
        
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except: 
        return None

def get_unique_owners(deals):
    owners = set()
    for d in deals:
        if d.get('owner_name'): owners.add(d.get('owner_name'))
    return sorted(list(owners))

# --- CORE SIMULATION LOGIC ---
def calculate_win_rates(all_deals, filter_recent=False):
    """Calculates Stage, Pipeline, and Global win rates."""
    cutoff = datetime.now() - timedelta(days=180) if filter_recent else datetime.min
    
    stage_stats = defaultdict(lambda: {'won': 0, 'total': 0})
    pipe_stats = defaultdict(lambda: {'won': 0, 'total': 0})
    owner_stats = defaultdict(lambda: {'won': 0, 'total': 0})
    global_stats = {'won': 0, 'total': 0}
    
    training_count = 0
    min_date = None
    max_date = None
    
    for d in all_deals:
        if d['status'] not in ['won', 'lost']: continue
        
        close_date = parse_date(d.get('close_time') or d.get('update_time'))
        if not close_date or close_date < cutoff: continue
        
        # Track Date Range
        if min_date is None or close_date < min_date: min_date = close_date
        if max_date is None or close_date > max_date: max_date = close_date
        training_count += 1
        
        sid = d.get('stage_id')
        pid = str(d.get('pipeline_id'))
        owner = d.get('owner_name')
        
        # Aggregate
        global_stats['total'] += 1
        if d['status'] == 'won': global_stats['won'] += 1
        
        stage_stats[sid]['total'] += 1
        if d['status'] == 'won': stage_stats[sid]['won'] += 1
        
        pipe_stats[pid]['total'] += 1
        if d['status'] == 'won': pipe_stats[pid]['won'] += 1
        
        owner_stats[owner]['total'] += 1
        if d['status'] == 'won': owner_stats[owner]['won'] += 1

    # Normalize to probabilities
    rates = {'stages': {}, 'pipelines': {}, 'owners': {}, 'global': 0.0}
    
    if global_stats['total'] > 0:
        rates['global'] = global_stats['won'] / global_stats['total']
        
    for k, v in stage_stats.items():
        if v['total'] > 0: rates['stages'][k] = v['won'] / v['total']
        
    for k, v in pipe_stats.items():
        if v['total'] > 0: rates['pipelines'][k] = v['won'] / v['total']
        
    for k, v in owner_stats.items():
        if v['total'] > 0: rates['owners'][k] = v['won'] / v['total']
        
    audit_info = {
        "training_count": training_count,
        "date_range": f"{min_date.strftime('%b %Y')} - {max_date.strftime('%b %Y')}" if min_date else "N/A",
        "global_win_rate": rates['global']
    }
        
    return rates, audit_info

def get_deal_probability(deal, model_type, rates, median_cycle):
    sid = deal.get('stage_id')
    pid = str(deal.get('pipeline_id'))
    owner = deal.get('owner_name')
    
    # Base Probability Hierarchy
    base = rates['stages'].get(sid)
    if base is None: base = rates['pipelines'].get(pid)
    if base is None: base = rates['global']
    
    # Model Modifiers
    if model_type == "baseline":
        return base
    
    elif model_type == "owner_performance":
        return rates['owners'].get(owner, base)
    
    elif model_type == "time_decay":
        created = parse_date(deal.get('add_time'))
        if created:
            age = (datetime.now() - created).days
            if age > (median_cycle * 2): return base * 0.2
            if age > median_cycle: return base * 0.5
        return base
    
    elif model_type == "engagement":
        acts = (deal.get('activities_count') or 0) + (deal.get('notes_count') or 0)
        if acts > 5: return min(base * 1.5, 0.95)
        if acts == 0: return base * 0.5
        return base
    
    elif model_type == "momentum":
        return base # Rates are already filtered for momentum in the main runner
        
    return base

def run_simulation(active_deals, model_type, all_history_deals):
    iterations = 10000
    
    # Prepare Data
    median_cycle = estimate_median_cycle(all_history_deals)
    
    # Calculate Rates
    is_momentum = (model_type == "momentum")
    rates, audit_info = calculate_win_rates(all_history_deals, filter_recent=is_momentum)
    
    # Run Monte Carlo
    results = []
    for _ in range(iterations):
        revenue = 0
        for deal in active_deals:
            prob = get_deal_probability(deal, model_type, rates, median_cycle)
            if random.random() < prob:
                revenue += (deal.get('value') or 0)
        results.append(revenue)
        
    results.sort()
    
    return {
        "conservative": results[int(iterations * 0.1)],
        "base": results[int(iterations * 0.5)],
        "moonshot": results[int(iterations * 0.9)],
        "count": len(active_deals),
        "total_value": sum(d.get('value') or 0 for d in active_deals),
        "audit": audit_info
    }
