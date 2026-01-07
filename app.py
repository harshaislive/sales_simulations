from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import analysis_core as core
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24) # Secure session key

# Load Data Once on Startup (from Supabase now)
DEALS = core.load_data()
PIPELINES = core.load_pipelines()
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
    return render_template('index.html', pipelines=PIPELINES, owners=OWNERS)

@app.route('/run_sim', methods=['POST'])
def run_sim():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    
    selected_pipeline = data.get('pipeline_id')
    selected_owner = data.get('owner_name')
    model_type = data.get('model_type', 'baseline')
    
    # --- DATA FILTERING & AUDIT ---
    active_deals = []
    ignored_status = 0
    filtered_out = 0
    
    for d in DEALS:
        # 1. Must be Open
        if d['status'] != 'open': 
            ignored_status += 1
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
    
    return jsonify({
        "success": True,
        "results": results,
        "meta": {
            "pipeline": PIPELINES.get(str(selected_pipeline), "All Pipelines") if selected_pipeline != "all" else "Global Portfolio",
            "owner": selected_owner if selected_owner != "all" else "All Agents",
            "model": model_type.replace("_", " ").title()
        }
    })

if __name__ == '__main__':
    print("Starting Secured Intelligence Server...")
    print("Go to http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
