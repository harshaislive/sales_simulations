from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import analysis_core as core
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Production: Use a static key from Env. Dev: Fallback to random.
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

# Load Data Once on Startup (from Supabase now)
DEALS = core.load_data()
PIPELINES = core.load_pipelines()
STAGE_LOOKUP, STAGE_GROUPS = core.build_stage_filters(DEALS, PIPELINES)
PROSPECT_STAGE_IDS = core.identify_prospect_stage_ids(STAGE_LOOKUP, DEALS, default_threshold=0)
OWNERS = core.get_unique_owners(DEALS)

TEAM_PASSWORD = os.environ.get("TEAM_PASSWORD", "admin")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        pwd = request.form.get('password')
        if pwd == TEAM_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid Password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html', pipelines=PIPELINES, owners=OWNERS, stage_groups=STAGE_GROUPS)

@app.route('/prospect-simulation')
def prospect_simulation():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    snapshot = build_prospect_snapshot()
    return render_template('prospect_simulation.html', **snapshot)

@app.route('/velocity-report')
def velocity_report():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        with open('reports/won_deals_velocity_report.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Report not found. Please run the analysis script.", 404

@app.route('/run_sim', methods=['POST'])
def run_sim():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    
    selected_pipeline = data.get('pipeline_id')
    selected_owner = data.get('owner_name')
    model_type = data.get('model_type', 'baseline')
    selected_stage = data.get('stage_id')
    
    stage_filter = None
    if selected_stage and selected_stage != "all":
        stage_filter = STAGE_LOOKUP.get(str(selected_stage))
    
    # --- DATA FILTERING & AUDIT ---
    active_deals = []
    ignored_status = 0
    filtered_out = 0
    
    for d in DEALS:
        # 1. Must be Open
        if d['status'] != 'open': 
            ignored_status += 1
            continue
        
        # 2. Stage Threshold Filter
        if stage_filter:
            if not stage_matches_threshold(d, stage_filter):
                filtered_out += 1
                continue
        
        # 3. User Filters
        match = True
        if selected_pipeline and selected_pipeline != "all":
            if str(d.get('pipeline_id')) != str(selected_pipeline): match = False
            
        if selected_owner and selected_owner != "all":
            if d.get('owner_name') != selected_owner: match = False
            
        if match:
            active_deals.append(d)
        else:
            filtered_out += 1
        
    if not active_deals:
        return jsonify({"error": "No deals match your criteria."})

    # Run Logic
    results = core.run_simulation(active_deals, model_type, DEALS)
    
    # Add Audit Data to Response
    results['audit']['total_db_records'] = len(DEALS)
    results['audit']['ignored_closed'] = ignored_status
    results['audit']['filtered_by_user'] = filtered_out
    
    stage_label = "All Stages"
    if stage_filter:
        stage_name = stage_filter.get('name') or f"Stage {stage_filter.get('id')}"
        if stage_filter.get('order') is not None:
            stage_label = f"{stage_name} +"
        else:
            stage_label = stage_name
    
    return jsonify({
        "success": True,
        "results": results,
        "meta": {
            "pipeline": PIPELINES.get(str(selected_pipeline), "All Pipelines") if selected_pipeline != "all" else "Global Portfolio",
            "owner": selected_owner if selected_owner != "all" else "All Agents",
            "model": model_type.replace("_", " ").title(),
            "stage": stage_label
        }
    })

def stage_matches_threshold(deal, stage_filter):
    selected_pid = stage_filter.get('pipeline_id')
    if selected_pid and str(deal.get('pipeline_id')) != selected_pid:
        return False
    
    deal_stage_id = str(deal.get('stage_id'))
    deal_stage_meta = STAGE_LOOKUP.get(deal_stage_id)
    deal_order = None
    if deal_stage_meta:
        deal_order = deal_stage_meta.get('order')
    if deal_order is None:
        try:
            deal_order = int(deal.get('stage_order_nr')) if deal.get('stage_order_nr') is not None else None
        except:
            deal_order = None
    
    threshold_order = stage_filter.get('order')
    if threshold_order is not None and deal_order is not None:
        return deal_order >= threshold_order
    return deal_stage_id == stage_filter.get('id')

def build_prospect_snapshot():
    stage_ids = PROSPECT_STAGE_IDS or set()
    prospect_deals = []
    stage_totals = {}
    total_value = 0
    
    for d in DEALS:
        if d.get('status') != 'open':
            continue
        if str(d.get('stage_id')) not in stage_ids:
            continue
        prospect_deals.append(d)
        stage_id = str(d.get('stage_id'))
        stage = STAGE_LOOKUP.get(stage_id, {})
        stage_name = stage.get('name') or f"Stage {stage_id}"
        if stage_id not in stage_totals:
            stage_totals[stage_id] = {"name": stage_name, "count": 0, "value": 0}
        stage_totals[stage_id]["count"] += 1
        stage_totals[stage_id]["value"] += (d.get('value') or 0)
        total_value += (d.get('value') or 0)
    
    rates, audit_info = core.calculate_win_rates(DEALS)
    median_cycle = core.estimate_median_cycle(DEALS)
    expected_conversions = 0
    enriched = []
    
    for d in prospect_deals:
        prob = core.get_deal_probability(d, "baseline", rates, median_cycle)
        expected_conversions += prob
        stage_id = str(d.get('stage_id'))
        stage = STAGE_LOOKUP.get(stage_id, {})
        enriched.append({
            "title": d.get('title') or f"Deal {d.get('id')}",
            "owner": d.get('owner_name') or "Unassigned",
            "value": d.get('value') or 0,
            "probability": prob,
            "stage": stage.get('name') or f"Stage {stage_id}"
        })
    
    enriched.sort(key=lambda x: x['probability'], reverse=True)
    top_candidates = enriched[:8]
    
    prospect_count = len(prospect_deals)
    expected_percentage = (expected_conversions / prospect_count * 100) if prospect_count else 0
    
    durations = core.collect_win_durations(DEALS)
    p99_days = percentile(durations, 0.99)
    target_date = None
    if p99_days is not None:
        target_date = (datetime.now() + timedelta(days=p99_days)).strftime("%d %b %Y")
    
    stage_breakdown = sorted(stage_totals.values(), key=lambda x: x['count'], reverse=True)
    
    stage_name_list = []
    for sid in stage_ids:
        meta = STAGE_LOOKUP.get(sid)
        order_hint = meta.get('order') if meta else None
        name = meta.get('name') if meta else f"Stage {sid}"
        stage_name_list.append((order_hint if order_hint is not None else 9999, name))
    sorted_stage_names = [name for _, name in sorted(stage_name_list, key=lambda x: x[0])]
    
    return {
        "prospect_count": prospect_count,
        "prospect_value": total_value,
        "expected_conversions": expected_conversions,
        "expected_percentage": expected_percentage,
        "top_candidates": top_candidates,
        "stage_breakdown": stage_breakdown,
        "p99_days": p99_days,
        "p99_target_date": target_date,
        "prospect_stage_names": sorted_stage_names,
        "audit_info": audit_info
    }

def percentile(values, pct):
    if not values:
        return None
    if pct <= 0:
        return min(values)
    if pct >= 1:
        return max(values)
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1

if __name__ == '__main__':
    print("Starting Secured Intelligence Server...")
    print("Go to http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
