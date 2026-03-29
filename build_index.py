"""Baut eine index.html Startseite, die alle Touren im output/ Ordner auflistet."""

import os
import re


def build_index():
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    html_files = sorted(f for f in os.listdir(output_dir) if f.endswith(".html") and f != "index.html")

    tours_html = ""
    for f in html_files:
        name = f.replace(".html", "").replace("_", " ")
        tours_html += f"""
    <a href="{f}" class="tour-card">
      <span class="tour-name">{name}</span>
      <span class="tour-arrow">→</span>
    </a>"""

    if not tours_html:
        tours_html = '<p style="color:#999;">Noch keine Touren generiert.</p>'

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Radtour Assistent</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #f5f5f5;
    color: #333;
    min-height: 100vh;
  }}
  .hero {{
    background: linear-gradient(135deg, #2c3e50, #3498db);
    color: white;
    padding: 40px 20px;
    text-align: center;
  }}
  .hero h1 {{ font-size: 1.6em; margin-bottom: 8px; }}
  .hero p {{ opacity: 0.8; font-size: 0.95em; }}
  .content {{
    max-width: 600px;
    margin: 0 auto;
    padding: 20px;
  }}
  h2 {{
    margin-bottom: 16px;
    color: #2c3e50;
  }}
  .tour-card {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: white;
    padding: 16px 20px;
    border-radius: 10px;
    margin-bottom: 10px;
    text-decoration: none;
    color: #333;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: box-shadow 0.2s;
  }}
  .tour-card:hover {{
    box-shadow: 0 3px 10px rgba(0,0,0,0.15);
  }}
  .tour-name {{
    font-weight: 600;
    font-size: 1em;
  }}
  .tour-arrow {{
    color: #3498db;
    font-size: 1.3em;
  }}
</style>
</head>
<body>
<div class="hero">
  <h1>Radtour Assistent</h1>
  <p>Mehrtaegige Radtouren planen</p>
</div>
<div class="content">
  <h2>Touren</h2>
  {tours_html}
</div>
</body>
</html>"""

    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Index erstellt: {index_path}")


if __name__ == "__main__":
    build_index()
