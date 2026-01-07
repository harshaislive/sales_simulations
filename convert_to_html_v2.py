import os
import markdown
import glob

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Simulation Report</title>
    <style>
        :root {{ --bg-color: #faf9f6; --text-color: #333; --accent-color: #000; --secondary-text: #666; --font-serif: 'Georgia', serif; --font-sans: -apple-system, system-ui, sans-serif; --success-color: #2e7d32; --neutral-color: #1976d2; --moonshot-color: #9c27b0; }}
        body {{ background: var(--bg-color); color: var(--text-color); font-family: var(--font-sans); padding: 4rem 2rem; max-width: 800px; margin: 0 auto; line-height: 1.6; }}
        header {{ border-bottom: 2px solid var(--accent-color); padding-bottom: 2rem; margin-bottom: 4rem; }}
        h1 {{ font-family: var(--font-serif); font-size: 3rem; margin: 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 2rem 0; background: white; }}
        th {{ text-align: left; border-bottom: 2px solid #333; padding: 1rem; background: #eee; }}
        td {{ padding: 1rem; border-bottom: 1px solid #eee; }}
        a {{ color: #666; text-decoration: none; border-bottom: 1px solid #ccc; }}
        strong {{ color: var(--accent-color); }}
        code {{ background: #eee; padding: 0.2rem 0.4rem; border-radius: 4px; }}
    </style>
</head>
<body>
    <a href="../../index.html">&larr; Back to Index</a>
    <div class="content">
        {content}
    </div>
</body>
</html>
"

def convert():
    # Find all MD files recursively
    md_files = glob.glob("simulations/md/**/*.md", recursive=True)
    
    # Structure for Index: { "Global Portfolio": ["path/to/baseline.html", ...], ... }
    index_map = {}
    
    for md_path in md_files:
        # e.g. simulations/md/bhopal_pipeline/baseline.md
        parts = md_path.replace("\", "/").split('/')
        folder_name = parts[-2] # bhopal_pipeline
        file_name = parts[-1]   # baseline.md
        
        # Scope Title (readable)
        scope_title = folder_name.replace("_", " ").title()
        
        if scope_title not in index_map: index_map[scope_title] = []
        
        # Read MD
        with open(md_path, 'r', encoding='utf-8') as f:
            text = f.read()
            html_body = markdown.markdown(text, extensions=['tables'])
            
        # Output HTML path
        # simulations/reports/bhopal_pipeline/baseline.html
        output_dir = f"simulations/reports/{folder_name}"
        os.makedirs(output_dir, exist_ok=True)
        
        html_filename = file_name.replace('.md', '.html')
        output_path = f"{output_dir}/{html_filename}"
        
        final_html = HTML_TEMPLATE.format(content=html_body)
        
        with open(output_path, 'w', encoding='utf-8') as out:
            out.write(final_html)
            
        # Store for Index
        # Relative link from index.html -> reports/bhopal/baseline.html
        rel_link = f"reports/{folder_name}/{html_filename}"
        model_name = html_filename.replace('.html', '').replace('_', ' ').title()
        index_map[scope_title].append((model_name, rel_link))
        
        print(f"Converted: {output_path}")

    # Generate Master Index
    index_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Simulation Library</title>
    <style>
        body{font-family:-apple-system, sans-serif; padding:4rem 2rem; max-width:1000px; margin:0 auto; background:#faf9f6;}
        h1{font-family:'Georgia', serif; font-size:2.5rem; margin-bottom:2rem;}
        .grid{display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:2rem;}
        .card{background:white; padding:2rem; border:1px solid #ddd; border-radius:8px;}
        .card h2{margin-top:0; font-size:1.5rem; border-bottom:2px solid #333; padding-bottom:1rem;}
        ul{list-style:none; padding:0;}
        li{margin:0.5rem 0; border-bottom:1px solid #eee; padding:0.5rem 0;}
        a{text-decoration:none; color:#1976d2; font-weight:500;}
        a:hover{text-decoration:underline;}
    </style>
    </head>
    <body>
    <h1>Advanced Simulation Library</h1>
    <div class="grid">
    "
    
    # Sort scopes to put Global first
    sorted_scopes = sorted(index_map.keys())
    if "Global Portfolio" in sorted_scopes:
        sorted_scopes.remove("Global Portfolio")
        sorted_scopes.insert(0, "Global Portfolio")
        
    for scope in sorted_scopes:
        reports = index_map[scope]
        index_html += f"<div class='card'><h2>{scope}</h2><ul>"
        for name, link in reports:
            index_html += f"<li><a href='{link}'>{name} Forecast</a></li>"
        index_html += "</ul></div>"
        
    index_html += "</div></body></html>"
    
    with open("simulations/index.html", 'w', encoding='utf-8') as f:
        f.write(index_html)
    print("Generated simulations/index.html")

if __name__ == "__main__":
    convert()
