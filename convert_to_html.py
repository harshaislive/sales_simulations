import os
import markdown
import glob

# HTML Template with the same style as before
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
        table {{ width: 100%; border-collapse: collapse; margin: 2rem 0; }}
        th {{ text-align: left; border-bottom: 2px solid #333; padding: 1rem; }}
        td {{ padding: 1rem; border-bottom: 1px solid #eee; }}
        a {{ color: #666; text-decoration: none; border-bottom: 1px solid #ccc; }}
        strong {{ color: var(--accent-color); }}
    </style>
</head>
<body>
    <a href="../index.html">&larr; Back to Index</a>
    <div class="content">
        {content}
    </div>
</body>
</html>
"""

def convert():
    # Create index.html content
    index_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Simulation Index</title>
    <style>body{font-family:sans-serif; padding:2rem; max-width:800px; margin:0 auto;} ul{list-style:none; padding:0;} li{margin:1rem 0; padding:1rem; border:1px solid #eee; background:#fff;} a{text-decoration:none; font-weight:bold; font-size:1.2rem; color:#1976d2;} p{margin:0.5rem 0 0; color:#666;}</style>
    </head>
    <body>
    <h1>Advanced Simulation Suite</h1>
    <p>5 Strategic Forecast Models</p>
    <ul>
    """

    md_files = glob.glob("simulations/md/*.md")
    
    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as f:
            text = f.read()
            html_body = markdown.markdown(text, extensions=['tables'])
            
            # Create HTML file
            base_name = os.path.basename(md_file).replace('.md', '.html')
            output_path = f"simulations/reports/{base_name}"
            
            final_html = HTML_TEMPLATE.format(content=html_body)
            
            with open(output_path, 'w', encoding='utf-8') as out:
                out.write(final_html)
            
            print(f"Generated {output_path}")
            
            # Add to Index
            title = base_name.replace('.html', '').replace('_', ' ').title()
            index_content += f"<li><a href='reports/{base_name}'>{title}</a><p>Click to view detailed forecast.</p></li>"

    index_content += "</ul></body></html>"
    
    with open("simulations/index.html", 'w', encoding='utf-8') as f:
        f.write(index_content)
    print("Generated simulations/index.html")

if __name__ == "__main__":
    convert()
