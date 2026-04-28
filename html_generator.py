"""HTML-Generator: Erzeugt eine mobile-freundliche HTML-Seite für die Radtour."""

import json
from datetime import timedelta
from gpx_parser import TourData, Stage, haversine
from api_enricher import StageEnrichment


def format_duration(td: timedelta | None) -> str:
    if not td:
        return "—"
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}h {minutes:02d}min"


def generate_packing_list() -> str:
    """Standard-Packliste für eine mehrtägige Radtour."""
    categories = {
        "Fahrrad & Technik": [
            "Fahrrad (gecheckt & gewartet)",
            "Fahrradtaschen / Bikepacking-Bags",
            "Ersatzschlauch (2x)",
            "Flickzeug",
            "Mini-Pumpe",
            "Multitool / Inbusschlüssel-Set",
            "Kettenschloss (passend zur Kette)",
            "Kettenöl",
            "Fahrradschloss",
            "Fahrradcomputer / Handy-Halterung",
            "Powerbank + Ladekabel",
            "Stirnlampe / Frontlicht",
            "Rücklicht",
        ],
        "Kleidung": [
            "Radhose (gepolstert)",
            "Radtrikot / Funktions-Shirts (2-3x)",
            "Regenjacke (wasserdicht, atmungsaktiv)",
            "Windjacke",
            "Warme Schicht (Fleece / Merino)",
            "Unterwäsche (Merino, 3x)",
            "Socken (3 Paar, Merino)",
            "Radhandschuhe",
            "Helm",
            "Sonnenbrille",
            "Abend-Kleidung (leichte Hose, T-Shirt)",
            "Badelatschen / leichte Schuhe",
        ],
        "Camping": [
            "Zelt / Biwaksack",
            "Isomatte",
            "Schlafsack",
            "Kocher + Gas",
            "Topf / Becher",
            "Besteck (Spork)",
            "Feuerzeug",
            "Müllbeutel",
        ],
        "Verpflegung": [
            "Trinkflaschen (2x 0,75l)",
            "Energieriegel / Müsliriegel",
            "Nüsse / Trockenfrüchte",
            "Kaffee / Tee",
            "Salz & Pfeffer",
        ],
        "Hygiene & Gesundheit": [
            "Sonnencreme",
            "Zahnbürste + Zahnpasta",
            "Seife / Duschgel (biologisch abbaubar)",
            "Handtuch (Mikrofaser)",
            "Erste-Hilfe-Set",
            "Schmerzmittel (Ibuprofen)",
            "Insektenschutz",
            "Sitzcreme",
        ],
        "Dokumente & Sonstiges": [
            "Personalausweis",
            "Bargeld + EC-Karte",
            "Krankenversicherungskarte",
            "Handy + Ladegerät",
            "Karte / Offline-Navigation",
            "Kabelbinder & Panzertape",
        ],
    }
    return categories


def stage_to_map_data(stage: Stage) -> list[list[float]]:
    """Konvertiert Stage-Punkte zu Koordinaten-Liste für Leaflet."""
    return [[p.lat, p.lon] for p in stage.points]


def generate_html(tour: TourData, enrichments: list[StageEnrichment], riders: list[str] | None = None) -> str:
    """Generiert die komplette HTML-Seite."""

    # Kartendaten vorbereiten
    all_stages_coords = []
    for stage in tour.stages:
        all_stages_coords.append(stage_to_map_data(stage))

    # Enrichments mit Stages zusammenführen
    stage_data = []
    for i, stage in enumerate(tour.stages):
        enrichment = enrichments[i] if i < len(enrichments) else StageEnrichment([], [], [], [], "")
        stage_data.append({
            "stage": stage,
            "enrichment": enrichment,
        })

    packing = generate_packing_list()

    # Höhenprofil-Daten pro Etappe: [[km, ele], ...]
    elevation_profiles = []
    for stage in tour.stages:
        profile = []
        cum_dist = 0.0
        pts = stage.points
        # Ausdünnen auf ~150 Punkte für Performance
        thin = max(1, len(pts) // 150)
        for j in range(0, len(pts), thin):
            if j > 0:
                cum_dist += haversine(pts[j-thin].lat, pts[j-thin].lon, pts[j].lat, pts[j].lon) / 1000
            profile.append([round(cum_dist, 2), round(pts[j].ele, 1)])
        # Letzten Punkt sicherstellen
        if len(pts) > 1 and (len(pts) - 1) % thin != 0:
            cum_dist += haversine(pts[-(thin+1)].lat, pts[-(thin+1)].lon, pts[-1].lat, pts[-1].lon) / 1000
            profile.append([round(cum_dist, 2), round(pts[-1].ele, 1)])
        elevation_profiles.append(profile)
    elevation_json = json.dumps(elevation_profiles)

    # JSON-Daten für JavaScript
    map_data_json = json.dumps(all_stages_coords)

    # Marker-Daten (Sehenswürdigkeiten + Campingplätze)
    markers = []
    for i, sd in enumerate(stage_data):
        e = sd["enrichment"]
        for sight in e.sights:
            markers.append({
                "lat": sight.get("lat", 0),
                "lon": sight.get("lon", 0),
                "name": sight.get("name", ""),
                "desc": sight.get("description", ""),
                "type": "sight",
                "category": sight.get("category", "sonstige"),
                "stage": i + 1,
            })
        for camp in e.campsites:
            markers.append({
                "lat": camp.get("lat", 0),
                "lon": camp.get("lon", 0),
                "name": camp.get("name", ""),
                "desc": camp.get("description", ""),
                "type": "camp",
                "stage": i + 1,
                "website": camp.get("website"),
            })
        for g in e.gastro:
            markers.append({
                "lat": g.get("lat", 0),
                "lon": g.get("lon", 0),
                "name": g.get("name", ""),
                "desc": g.get("opening_hours", ""),
                "type": "gastro",
                "category": g.get("category", "restaurant"),
                "stage": i + 1,
                "website": g.get("website"),
            })
        for em in e.emergency:
            markers.append({
                "lat": em.get("lat", 0),
                "lon": em.get("lon", 0),
                "name": em.get("name", ""),
                "desc": em.get("phone", ""),
                "type": "emergency",
                "category": em.get("category", ""),
                "stage": i + 1,
                "website": em.get("website"),
            })
        for lo in e.lodging:
            markers.append({
                "lat": lo.get("lat", 0),
                "lon": lo.get("lon", 0),
                "name": lo.get("name", ""),
                "desc": lo.get("description", ""),
                "type": "lodging",
                "category": lo.get("category", "hotel"),
                "stage": i + 1,
                "website": lo.get("website"),
            })
    markers_json = json.dumps(markers)

    # Farben für Etappen
    stage_colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
                    "#1abc9c", "#e67e22", "#34495e"]

    # HTML zusammenbauen
    stages_html = ""
    for i, sd in enumerate(stage_data):
        s = sd["stage"]
        e = sd["enrichment"]
        color = stage_colors[i % len(stage_colors)]

        towns_html = ""
        if e.towns:
            towns_html = f'<p class="towns">{" → ".join(e.towns)}</p>'

        terrain_html = ""
        if e.terrain_description:
            terrain_html = f'<p class="terrain">{e.terrain_description}</p>'

        # Oberflächen-Info
        surface_html = ""
        if e.surface and e.surface.get("surfaces"):
            paved = e.surface.get("paved_percent", 0)
            bars = ""
            for sf in e.surface["surfaces"][:6]:
                bars += f'<div class="surface-bar"><span class="surface-label">{sf["label"]}</span><div class="surface-track"><div class="surface-fill" style="width:{sf["percent"]}%"></div></div><span class="surface-pct">{sf["percent"]}%</span></div>'
            surface_html = f'<div class="subsection collapsible"><h4 onclick="toggleSub(this)">Untergrund <span class="sub-badge">{paved}% befestigt</span><span class="sub-chevron">▶</span></h4><div class="sub-body">{bars}</div></div>'

        sights_html = ""
        if e.sights:
            category_order = [
                ("schloss", "Burgen & Schloesser", "🏰"),
                ("museum", "Museen", "🏛"),
                ("kirche", "Kirchen & Kloester", "⛪"),
                ("denkmal", "Denkmaeler & Gedenkstaetten", "🗿"),
                ("ruine", "Ruinen & Ausgrabungen", "🏚"),
                ("aussicht", "Aussichtspunkte", "🔭"),
                ("attraktion", "Attraktionen", "🎯"),
                ("sonstige", "Weitere Sehenswuerdigkeiten", "📍"),
            ]
            categories_found = {}
            for sight in e.sights:
                cat = sight.get("category", "sonstige")
                if cat not in categories_found:
                    categories_found[cat] = []
                categories_found[cat].append(sight)

            inner = ""
            for cat_key, cat_label, cat_icon in category_order:
                if cat_key in categories_found:
                    items = ""
                    for sight in categories_found[cat_key]:
                        items += f'<li><strong>{sight["name"]}</strong></li>'
                    inner += f'<div class="sight-category"><span class="cat-header">{cat_icon} {cat_label}</span><ul>{items}</ul></div>'
            count = len(e.sights)
            sights_html = f'<div class="subsection collapsible" data-stage="{i+1}" data-marker-type="sight"><h4 onclick="toggleSub(this)">Sehenswuerdigkeiten <span class="sub-badge">{count}</span><span class="sub-chevron">▶</span></h4><div class="sub-body">{inner}</div></div>'

        camps_html = ""
        if e.campsites:
            items = ""
            for camp in e.campsites:
                link = ""
                if camp.get("website"):
                    link = f' <a href="{camp["website"]}" target="_blank">Website</a>'
                items += f'<li><strong>{camp["name"]}</strong> — {camp.get("description", "")}{link}</li>'
            count = len(e.campsites)
            camps_html = f'<div class="subsection collapsible" data-stage="{i+1}" data-marker-type="camp"><h4 onclick="toggleSub(this)">Campingplaetze <span class="sub-badge">{count}</span><span class="sub-chevron">▶</span></h4><div class="sub-body"><ul>{items}</ul></div></div>'

        # Hotels/Hostels rund um den Etappenendpunkt
        lodging_html = ""
        if e.lodging:
            lodging_groups = {"hotel": [], "hostel": [], "guest_house": [], "motel": []}
            for lo in e.lodging:
                cat = lo.get("category", "hotel")
                if cat in lodging_groups:
                    lodging_groups[cat].append(lo)

            inner = ""
            for cat, icon, label in [("hotel", "🏨", "Hotels"), ("hostel", "🛏", "Hostels"),
                                      ("guest_house", "🏠", "Pensionen"), ("motel", "🏨", "Motels")]:
                group = lodging_groups.get(cat, [])[:8]
                if group:
                    items = ""
                    for lo in group:
                        parts = [f'<strong>{lo["name"]}</strong>']
                        if lo.get("description") and lo["description"] != label:
                            parts.append(f' — {lo["description"]}')
                        if lo.get("phone"):
                            parts.append(f' <a href="tel:{lo["phone"]}">{lo["phone"]}</a>')
                        if lo.get("website"):
                            parts.append(f' <a href="{lo["website"]}" target="_blank">Website</a>')
                        parts.append(f' <span class="dist">{lo["distance_km"]} km vom Ziel</span>')
                        items += f'<li>{"".join(parts)}</li>'
                    inner += f'<div class="sight-category"><span class="cat-header">{icon} {label}</span><ul>{items}</ul></div>'

            count = len(e.lodging)
            lodging_html = f'<div class="subsection collapsible" data-stage="{i+1}" data-marker-type="lodging"><h4 onclick="toggleSub(this)">Uebernachtung am Ziel <span class="sub-badge">{count}</span><span class="sub-chevron">▶</span></h4><div class="sub-body">{inner}</div></div>'

        # Gastronomie
        gastro_html = ""
        if e.gastro:
            gastro_groups = {"supermarkt": [], "cafe": [], "restaurant": []}
            for g in e.gastro:
                cat = g.get("category", "restaurant")
                if cat in gastro_groups:
                    gastro_groups[cat].append(g)

            inner = ""
            for cat, icon, label in [("supermarkt", "🛒", "Supermaerkte"), ("cafe", "☕", "Cafes"), ("restaurant", "🍽", "Restaurants")]:
                group = gastro_groups.get(cat, [])[:8]
                if group:
                    items = ""
                    for g in group:
                        link = ""
                        if g.get("website"):
                            link = f' <a href="{g["website"]}" target="_blank">Website</a>'
                        hours = ""
                        if g.get("opening_hours"):
                            hours = f' <span class="hours">({g["opening_hours"]})</span>'
                        items += f'<li><strong>{g["name"]}</strong>{hours}{link} <span class="dist">{g["distance_km"]} km</span></li>'
                    inner += f'<div class="sight-category"><span class="cat-header">{icon} {label}</span><ul>{items}</ul></div>'

            count = len(e.gastro)
            gastro_html = f'<div class="subsection collapsible" data-stage="{i+1}" data-marker-type="gastro"><h4 onclick="toggleSub(this)">Verpflegung <span class="sub-badge">{count}</span><span class="sub-chevron">▶</span></h4><div class="sub-body">{inner}</div></div>'

        # Notfall-Infos
        emergency_html = ""
        if e.emergency:
            em_groups = {"fahrrad": [], "krankenhaus": [], "bahnhof": []}
            for em in e.emergency:
                cat = em.get("category", "")
                if cat in em_groups:
                    em_groups[cat].append(em)

            inner = ""
            for cat, icon, label in [("fahrrad", "🔧", "Fahrradwerkstaetten"), ("krankenhaus", "🏥", "Krankenhaeuser"), ("bahnhof", "🚉", "Bahnhoefe")]:
                group = em_groups.get(cat, [])[:6]
                if group:
                    items = ""
                    for em in group:
                        parts = [f'<strong>{em["name"]}</strong>']
                        if em.get("phone"):
                            parts.append(f' <a href="tel:{em["phone"]}">{em["phone"]}</a>')
                        if em.get("website"):
                            parts.append(f' <a href="{em["website"]}" target="_blank">Website</a>')
                        parts.append(f' <span class="dist">{em["distance_km"]} km</span>')
                        items += f'<li>{"".join(parts)}</li>'
                    inner += f'<div class="sight-category"><span class="cat-header">{icon} {label}</span><ul>{items}</ul></div>'

            count = len(e.emergency)
            emergency_html = f'<div class="subsection collapsible" data-stage="{i+1}" data-marker-type="emergency"><h4 onclick="toggleSub(this)">Notfall & Service <span class="sub-badge">{count}</span><span class="sub-chevron">▶</span></h4><div class="sub-body">{inner}</div></div>'

        trivia_html = ""
        if e.trivia:
            items = "".join(f"<li>{t}</li>" for t in e.trivia)
            trivia_html = f'<div class="subsection collapsible"><h4 onclick="toggleSub(this)">Wusstest du? <span class="sub-badge">{len(e.trivia)}</span><span class="sub-chevron">▶</span></h4><div class="sub-body"><ul class="trivia">{items}</ul></div></div>'

        # Wetter: Koordinaten des Etappen-Mittelpunkts für Live-Fetch
        mid_idx = len(s.points) // 2
        mid_lat = round(s.points[mid_idx].lat, 4) if s.points else 0
        mid_lon = round(s.points[mid_idx].lon, 4) if s.points else 0

        stages_html += f"""
    <div class="stage-panel" id="stage-panel-{i+1}" data-stage-idx="{i}">
      <div class="stage-info" style="border-left: 4px solid {color}">
        <h3>{s.name}</h3>
        <div class="stage-stats">
          <span>{s.distance_km} km</span>
          <span>↑ {s.elevation_gain}m</span>
          <span>↓ {s.elevation_loss}m</span>
          <span>{format_duration(s.duration)}</span>
        </div>
      </div>
      <div class="weather-widget" id="weather-{i+1}" data-lat="{mid_lat}" data-lon="{mid_lon}"></div>
      {towns_html}
      {terrain_html}
      {surface_html}
      {gastro_html}
      {sights_html}
      {camps_html}
      {lodging_html}
      {emergency_html}
      {trivia_html}
    </div>"""

    # Packliste als JSON für JavaScript
    packing_json = json.dumps(packing, ensure_ascii=False)
    if not riders:
        riders = ["Fahrer 1", "Fahrer 2"]
    riders_json = json.dumps(riders, ensure_ascii=False)
    packing_html = f"""
    <div class="packing-tabs">
      {"".join(f'<button class="packing-tab{" active" if i == 0 else ""}" onclick="switchRider({i})">{name}</button>' for i, name in enumerate(riders))}
    </div>
    <div id="packing-container"></div>
    """

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>{tour.name}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #f5f5f5;
    color: #333;
    padding-bottom: 70px;
  }}

  .hero {{
    background: linear-gradient(135deg, #2c3e50, #3498db);
    color: white;
    text-align: center;
    position: relative;
  }}
  .hero-overlay {{
    padding: 24px 16px;
  }}
  .back-btn {{
    position: absolute;
    top: 12px;
    left: 12px;
    background: rgba(255,255,255,0.18);
    color: white;
    text-decoration: none;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 0.85em;
    backdrop-filter: blur(4px);
    border: 1px solid rgba(255,255,255,0.25);
    transition: background 0.15s;
  }}
  .back-btn:hover {{
    background: rgba(255,255,255,0.3);
  }}
  .hero h1 {{
    font-size: 1.4em;
    margin-bottom: 8px;
  }}
  .hero-stats {{
    display: flex;
    justify-content: center;
    gap: 16px;
    flex-wrap: wrap;
    font-size: 0.9em;
    opacity: 0.9;
  }}
  .hero-stat {{
    text-align: center;
  }}
  .hero-stat .value {{
    font-size: 1.3em;
    font-weight: bold;
    display: block;
  }}

  #map {{
    width: 100%;
    height: 300px;
    position: sticky;
    top: 0;
    z-index: 100;
    border-bottom: 2px solid #ddd;
  }}

  .tabs {{
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    border-top: 1px solid #ddd;
    z-index: 200;
  }}
  .tab {{
    flex: 1;
    text-align: center;
    padding: 10px 4px;
    font-size: 0.75em;
    cursor: pointer;
    border: none;
    background: none;
    color: #666;
    transition: color 0.2s;
  }}
  .tab.active {{
    color: #3498db;
    font-weight: bold;
  }}
  .tab-icon {{
    font-size: 1.4em;
    display: block;
    margin-bottom: 2px;
  }}

  .content {{
    padding: 12px;
  }}
  .tab-content {{
    display: none;
  }}
  .tab-content.active {{
    display: block;
  }}

  /* Etappen-Reiter */
  .stage-tabs {{
    display: flex;
    gap: 4px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    padding-bottom: 8px;
    scrollbar-width: none;
  }}
  .stage-tabs::-webkit-scrollbar {{
    display: none;
  }}
  .stage-tab {{
    flex: 0 0 auto;
    padding: 8px 12px;
    min-width: 36px;
    border: none;
    background: white;
    border-radius: 8px 8px 0 0;
    font-size: 0.85em;
    font-weight: 600;
    cursor: pointer;
    color: #888;
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
    white-space: nowrap;
  }}
  .stage-tab.active {{
    color: #2c3e50;
    background: white;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }}

  /* Swipe-Container */
  .stage-swipe {{
    position: relative;
    overflow: hidden;
    touch-action: pan-y;
  }}
  .stage-panel {{
    display: none;
    background: white;
    border-radius: 10px;
    padding: 0 16px 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    animation: fadeIn 0.2s ease;
  }}
  .stage-panel.active {{
    display: block;
  }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateX(10px); }}
    to {{ opacity: 1; transform: translateX(0); }}
  }}

  .stage-info {{
    padding: 14px 0;
  }}
  .stage-info h3 {{
    font-size: 1em;
    margin-bottom: 4px;
  }}
  .stage-stats {{
    display: flex;
    gap: 12px;
    font-size: 0.8em;
    color: #666;
  }}

  .towns {{
    color: #666;
    font-size: 0.85em;
    margin-bottom: 10px;
    line-height: 1.5;
  }}
  .terrain {{
    font-style: italic;
    color: #777;
    font-size: 0.85em;
    margin-bottom: 12px;
  }}

  .subsection {{
    margin-bottom: 12px;
  }}
  .subsection h4 {{
    font-size: 0.9em;
    color: #3498db;
    margin-bottom: 6px;
  }}
  .subsection ul {{
    padding-left: 18px;
    font-size: 0.85em;
    line-height: 1.6;
  }}
  .trivia li {{
    list-style: none;
    padding-left: 0;
    position: relative;
  }}
  .trivia li::before {{
    content: "💡";
    margin-right: 6px;
  }}
  .trivia {{
    padding-left: 0 !important;
  }}

  .map-btn {{
    background: #3498db;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 0.85em;
    cursor: pointer;
    margin-top: 8px;
  }}

  .packing-category {{
    background: white;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }}
  .packing-category h4 {{
    margin-bottom: 8px;
    color: #2c3e50;
  }}
  .packing-tabs {{
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
  }}
  .packing-tab {{
    flex: 1;
    padding: 10px;
    border: 2px solid #ddd;
    border-radius: 8px;
    background: white;
    font-size: 0.95em;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    transition: all 0.2s;
  }}
  .packing-tab.active {{
    border-color: #3498db;
    background: #3498db;
    color: white;
  }}
  .packing-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    font-size: 0.9em;
    border-bottom: 1px solid #f0f0f0;
  }}
  .packing-item:last-child {{
    border-bottom: none;
  }}
  .packing-input {{
    flex: 1;
    border: none;
    border-bottom: 1px dashed #ccc;
    padding: 4px 2px;
    font-family: inherit;
    font-size: 0.95em;
    background: transparent;
    outline: none;
  }}
  .packing-input:focus {{
    border-bottom-color: #3498db;
  }}
  .packing-input::placeholder {{
    color: #ccc;
  }}
  .add-item-btn {{
    display: block;
    width: 100%;
    padding: 8px;
    margin-top: 6px;
    border: 2px dashed #ddd;
    border-radius: 6px;
    background: none;
    color: #999;
    cursor: pointer;
    font-size: 0.85em;
  }}
  .add-item-btn:hover {{
    border-color: #3498db;
    color: #3498db;
  }}

  .overview-card {{
    background: white;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }}
  .overview-card h4 {{
    margin-bottom: 8px;
    color: #2c3e50;
  }}
  .overview-table {{
    width: 100%;
    font-size: 0.85em;
    border-collapse: collapse;
  }}
  .overview-table th, .overview-table td {{
    padding: 8px;
    text-align: left;
    border-bottom: 1px solid #f0f0f0;
  }}
  .overview-table th {{
    color: #666;
    font-weight: 600;
  }}

  .sight-category {{
    margin-bottom: 8px;
  }}
  .cat-header {{
    font-weight: 600;
    font-size: 0.85em;
    color: #555;
    display: block;
    margin-bottom: 2px;
  }}
  .sight-category ul {{
    padding-left: 18px;
    font-size: 0.85em;
    line-height: 1.5;
    margin-bottom: 6px;
  }}

  /* Aufklappbare Subsektionen */
  .collapsible > h4 {{
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    user-select: none;
  }}
  .collapsible > h4:hover {{
    opacity: 0.8;
  }}
  .sub-chevron {{
    font-size: 0.7em;
    transition: transform 0.2s;
    margin-left: auto;
    color: #999;
  }}
  .collapsible.open .sub-chevron {{
    transform: rotate(90deg);
  }}
  .sub-body {{
    display: none;
    padding-top: 6px;
  }}
  .collapsible.open .sub-body {{
    display: block;
  }}
  .sub-badge {{
    font-size: 0.7em;
    background: #e8f4f8;
    color: #3498db;
    padding: 1px 7px;
    border-radius: 10px;
    font-weight: 500;
  }}

  /* Oberflächen-Balken */
  .surface-bar {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    font-size: 0.82em;
  }}
  .surface-label {{
    min-width: 100px;
    color: #555;
  }}
  .surface-track {{
    flex: 1;
    height: 8px;
    background: #eee;
    border-radius: 4px;
    overflow: hidden;
  }}
  .surface-fill {{
    height: 100%;
    background: #3498db;
    border-radius: 4px;
  }}
  .surface-pct {{
    min-width: 36px;
    text-align: right;
    color: #888;
    font-size: 0.9em;
  }}

  /* Distanz-Angabe + Öffnungszeiten */
  .dist {{
    color: #999;
    font-size: 0.85em;
  }}
  .hours {{
    color: #888;
    font-size: 0.9em;
  }}

  /* Wetter-Widget */
  .weather-widget {{
    margin-bottom: 12px;
  }}
  .weather-row {{
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 4px;
    -webkit-overflow-scrolling: touch;
  }}
  .weather-day {{
    flex: 0 0 auto;
    min-width: 80px;
    background: linear-gradient(135deg, #e8f4f8, #f0f8ff);
    border-radius: 8px;
    padding: 8px 10px;
    text-align: center;
    font-size: 0.78em;
  }}
  .weather-day .wd-date {{
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 2px;
  }}
  .weather-day .wd-icon {{
    font-size: 1.6em;
    margin: 2px 0;
  }}
  .weather-day .wd-temp {{
    font-weight: 600;
    color: #333;
  }}
  .weather-day .wd-detail {{
    color: #666;
    font-size: 0.92em;
  }}
  .weather-loading {{
    font-size: 0.8em;
    color: #999;
    padding: 6px 0;
  }}

  .gps-btn {{
    position: absolute;
    top: 10px;
    right: 10px;
    z-index: 1000;
    background: white;
    border: 2px solid rgba(0,0,0,0.2);
    border-radius: 6px;
    width: 36px;
    height: 36px;
    font-size: 18px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.2);
  }}
  .gps-btn.active {{
    background: #3498db;
    color: white;
  }}

  @media (min-width: 768px) {{
    body {{ max-width: 768px; margin: 0 auto; }}
    #map {{ height: 400px; border-radius: 0 0 10px 10px; position: relative; }}
  }}
</style>
</head>
<body>

<div class="hero">
  <a href="./" class="back-btn">← Übersicht</a>
  <div class="hero-overlay">
    <h1>{tour.name}</h1>
    <div class="hero-stats">
      <div class="hero-stat"><span class="value">{tour.total_distance_km}</span> km</div>
      <div class="hero-stat"><span class="value">{tour.total_elevation_gain}</span> m hoch</div>
      <div class="hero-stat"><span class="value">{len(tour.stages)}</span> Etappen</div>
      <div class="hero-stat"><span class="value">{tour.min_ele}–{tour.max_ele}</span> m Hoehe</div>
    </div>
  </div>
</div>

<div style="position:relative;">
  <div id="map"></div>
  <button class="gps-btn" id="gps-btn" onclick="toggleGPS()" title="Meinen Standort anzeigen">📍</button>
</div>

<div class="content">
  <div id="tab-etappen" class="tab-content active">
    <div class="stage-tabs">
      {"".join(f'<button class="stage-tab{" active" if i == 0 else ""}" onclick="switchStage({i})" style="border-bottom-color: {stage_colors[i % len(stage_colors)]}">{i+1}</button>' for i in range(len(tour.stages)))}
    </div>
    <div class="stage-swipe" id="stage-swipe">
      {stages_html}
    </div>
  </div>

  <div id="tab-packliste" class="tab-content">
    <h3 style="margin-bottom: 12px;">Packliste</h3>
    <p style="font-size: 0.8em; color: #666; margin-bottom: 12px;">
      Waehle deinen Namen und trag ein, was du mitnimmst. Wird lokal gespeichert.
    </p>
    {packing_html}
  </div>

  <div id="tab-uebersicht" class="tab-content">
    <h3 style="margin-bottom: 12px;">Touruebersicht</h3>
    <div class="overview-card">
      <h4>Etappen</h4>
      <table class="overview-table">
        <tr><th>#</th><th>Strecke</th><th>km</th><th>Hoehe</th></tr>
        {"".join(f'<tr><td>{s.day}</td><td>{s.start_point} → {s.end_point}</td><td>{s.distance_km}</td><td>↑{s.elevation_gain}m</td></tr>' for s in tour.stages)}
      </table>
    </div>
    <div class="overview-card">
      <h4>Hoehenprofile</h4>
      {"".join(f'<div style="margin-bottom:16px;"><p style="font-size:0.85em;font-weight:600;margin-bottom:4px;">Etappe {s.day}: {s.start_point} → {s.end_point}</p><canvas id="profile-{s.day}" width="700" height="150" style="width:100%;height:150px;border-radius:6px;background:#fafafa;"></canvas></div>' for s in tour.stages)}
    </div>
  </div>
</div>

<div class="tabs">
  <button class="tab active" onclick="switchTab('etappen')">
    <span class="tab-icon">🗺</span>Etappen
  </button>
  <button class="tab" onclick="switchTab('packliste')">
    <span class="tab-icon">🎒</span>Packliste
  </button>
  <button class="tab" onclick="switchTab('uebersicht')">
    <span class="tab-icon">📊</span>Uebersicht
  </button>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const stageCoords = {map_data_json};
const markers = {markers_json};
const colors = {json.dumps(stage_colors[:len(tour.stages)])};
const elevationData = {elevation_json};

// Karte initialisieren
const map = L.map('map', {{ zoomControl: true }});
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; OpenStreetMap',
  maxZoom: 18,
}}).addTo(map);

// Alle Routen zeichnen
const polylines = [];
const allBounds = [];
stageCoords.forEach((coords, i) => {{
  const poly = L.polyline(coords, {{
    color: colors[i % colors.length],
    weight: 4,
    opacity: 0.8,
  }}).addTo(map);
  polylines.push(poly);
  allBounds.push(...coords);
}});

// Start- und Endmarker
if (allBounds.length > 0) {{
  const startIcon = L.divIcon({{
    html: '<div style="background:#2ecc71;color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);">S</div>',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    className: '',
  }});
  const endIcon = L.divIcon({{
    html: '<div style="background:#e74c3c;color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);">Z</div>',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    className: '',
  }});
  L.marker(allBounds[0], {{ icon: startIcon }}).addTo(map).bindPopup('Start: Oranienburg');
  L.marker(allBounds[allBounds.length - 1], {{ icon: endIcon }}).addTo(map).bindPopup('Ziel: List auf Sylt');
  map.fitBounds(L.latLngBounds(allBounds), {{ padding: [20, 20] }});
}}

// POI-Marker mit Kategorie-Icons
const catIcons = {{
  'camp': '⛺',
  'schloss': '🏰',
  'museum': '🏛',
  'kirche': '⛪',
  'denkmal': '🗿',
  'ruine': '🏚',
  'aussicht': '🔭',
  'attraktion': '🎯',
  'sonstige': '📍',
  'supermarkt': '🛒',
  'cafe': '☕',
  'restaurant': '🍽',
  'fahrrad': '🔧',
  'krankenhaus': '🏥',
  'bahnhof': '🚉',
  'hotel': '🏨',
  'hostel': '🛏',
  'guest_house': '🏠',
  'motel': '🏨',
}};

// Marker in Layer-Gruppen: markerLayers[stage][type] = L.layerGroup
const markerLayers = {{}};
markers.forEach(m => {{
  if (!m.lat || !m.lon) return;
  const emoji = catIcons[m.type] || catIcons[m.category] || '📍';
  const icon = L.divIcon({{
    html: '<div style="font-size:18px;">' + emoji + '</div>',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    className: '',
  }});
  let popup = '<strong>' + m.name + '</strong><br>' + m.desc;
  if (m.website) popup += '<br><a href="' + m.website + '" target="_blank">Website</a>';
  const marker = L.marker([m.lat, m.lon], {{ icon }}).bindPopup(popup);

  const key = m.stage + '-' + m.type;
  if (!markerLayers[key]) markerLayers[key] = L.layerGroup();
  markerLayers[key].addLayer(marker);
}});

// Navigation
function switchTab(name) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.currentTarget.classList.add('active');
  if (name === 'uebersicht') setTimeout(drawAllProfiles, 50);
}}

// Etappen-Wechsel
let currentStage = 0;
const totalStages = stageCoords.length;

function switchStage(idx) {{
  // Offene Marker der alten Etappe ausblenden
  hideAllMarkers();

  currentStage = idx;

  // Panels
  document.querySelectorAll('.stage-panel').forEach((p, i) => {{
    p.classList.toggle('active', i === idx);
  }});

  // Tabs
  document.querySelectorAll('.stage-tab').forEach((t, i) => {{
    t.classList.toggle('active', i === idx);
  }});

  // Tab in Sicht scrollen
  const activeTab = document.querySelectorAll('.stage-tab')[idx];
  if (activeTab) activeTab.scrollIntoView({{ behavior: 'smooth', block: 'nearest', inline: 'center' }});

  // Karte auf Etappe zoomen + Highlight
  const coords = stageCoords[idx];
  if (coords && coords.length) {{
    map.fitBounds(L.latLngBounds(coords), {{ padding: [30, 30] }});
    polylines.forEach((p, i) => {{
      p.setStyle({{ weight: i === idx ? 6 : 3, opacity: i === idx ? 1 : 0.4 }});
    }});
  }}
}}

function hideAllMarkers() {{
  Object.values(markerLayers).forEach(layer => map.removeLayer(layer));
  // Subsektionen zuklappen
  document.querySelectorAll('.collapsible.open').forEach(el => el.classList.remove('open'));
}}

// Erstes Panel aktivieren
switchStage(0);

// Swipe-Gesten
(function() {{
  const swipe = document.getElementById('stage-swipe');
  if (!swipe) return;
  let startX = 0;
  let startY = 0;
  let tracking = false;

  swipe.addEventListener('touchstart', e => {{
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
    tracking = true;
  }}, {{ passive: true }});

  swipe.addEventListener('touchend', e => {{
    if (!tracking) return;
    tracking = false;
    const dx = e.changedTouches[0].clientX - startX;
    const dy = e.changedTouches[0].clientY - startY;
    // Nur horizontale Swipes (mindestens 50px, mehr horizontal als vertikal)
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {{
      if (dx < 0 && currentStage < totalStages - 1) {{
        switchStage(currentStage + 1);
      }} else if (dx > 0 && currentStage > 0) {{
        switchStage(currentStage - 1);
      }}
    }}
  }}, {{ passive: true }});
}})()

// Packliste — drei Fahrer, editierbare Felder
const packingData = {packing_json};
const riders = {riders_json};
let currentRider = 0;
let riderData = {{}};

function initPacking() {{
  // Gespeicherte Daten laden
  const saved = localStorage.getItem('radtour-packing-v3');
  if (saved) riderData = JSON.parse(saved);

  // Fuer jeden Rider Standarddaten anlegen falls noetig
  riders.forEach(name => {{
    if (!riderData[name]) {{
      riderData[name] = {{}};
      for (const [category, items] of Object.entries(packingData)) {{
        riderData[name][category] = items.map(item => ({{ text: '', placeholder: item }}));
      }}
    }}
  }});

  renderPacking();
}}

function switchRider(idx) {{
  currentRider = idx;
  document.querySelectorAll('.packing-tab').forEach((t, i) => {{
    t.classList.toggle('active', i === idx);
  }});
  renderPacking();
}}

function renderPacking() {{
  const name = riders[currentRider];
  const data = riderData[name];
  const container = document.getElementById('packing-container');
  let html = '';

  for (const [category, items] of Object.entries(data)) {{
    html += '<div class="packing-category"><h4>' + category + '</h4>';
    items.forEach((item, idx) => {{
      html += '<div class="packing-item">';
      html += '<input class="packing-input" type="text" value="' + (item.text || '').replace(/"/g, '&quot;') + '" placeholder="' + (item.placeholder || '').replace(/"/g, '&quot;') + '" data-cat="' + category.replace(/"/g, '&quot;') + '" data-idx="' + idx + '">';
      html += '</div>';
    }});
    html += '<button class="add-item-btn" data-cat="' + category.replace(/"/g, '&quot;') + '">+ Hinzufuegen</button>';
    html += '</div>';
  }}
  container.innerHTML = html;
}}

// Event Delegation fuer Packliste
document.getElementById('packing-container').addEventListener('input', function(e) {{
  if (e.target.classList.contains('packing-input')) {{
    const cat = e.target.dataset.cat;
    const idx = parseInt(e.target.dataset.idx);
    const name = riders[currentRider];
    riderData[name][cat][idx].text = e.target.value;
    savePacking();
  }}
}});
document.getElementById('packing-container').addEventListener('click', function(e) {{
  if (e.target.classList.contains('add-item-btn')) {{
    const cat = e.target.dataset.cat;
    const name = riders[currentRider];
    riderData[name][cat].push({{ text: '', placeholder: '' }});
    renderPacking();
    const inputs = document.querySelectorAll('.packing-input');
    if (inputs.length) inputs[inputs.length - 1].focus();
    savePacking();
  }}
}});

function savePacking() {{
  localStorage.setItem('radtour-packing-v3', JSON.stringify(riderData));
}}

initPacking();

// Hoehenprofile zeichnen
function drawProfile(canvasId, data, color) {{
  const canvas = document.getElementById(canvasId);
  if (!canvas || !data || data.length < 2) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);

  const pad = {{ top: 10, right: 10, bottom: 25, left: 40 }};
  const pw = w - pad.left - pad.right;
  const ph = h - pad.top - pad.bottom;

  const maxKm = data[data.length - 1][0];
  const eles = data.map(d => d[1]);
  const minEle = Math.min(...eles) - 5;
  const maxEle = Math.max(...eles) + 10;
  const eleRange = maxEle - minEle || 1;

  const x = km => pad.left + (km / maxKm) * pw;
  const y = ele => pad.top + ph - ((ele - minEle) / eleRange) * ph;

  // Flaeche
  ctx.beginPath();
  ctx.moveTo(x(data[0][0]), y(data[0][1]));
  data.forEach(d => ctx.lineTo(x(d[0]), y(d[1])));
  ctx.lineTo(x(data[data.length - 1][0]), pad.top + ph);
  ctx.lineTo(x(0), pad.top + ph);
  ctx.closePath();
  ctx.fillStyle = color + '22';
  ctx.fill();

  // Linie
  ctx.beginPath();
  ctx.moveTo(x(data[0][0]), y(data[0][1]));
  data.forEach(d => ctx.lineTo(x(d[0]), y(d[1])));
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.stroke();

  // Achsen
  ctx.fillStyle = '#888';
  ctx.font = '11px sans-serif';
  ctx.textAlign = 'center';
  const kmSteps = Math.ceil(maxKm / 20);
  for (let km = 0; km <= maxKm; km += Math.max(1, Math.round(maxKm / 5))) {{
    ctx.fillText(Math.round(km) + ' km', x(km), h - 4);
  }}
  ctx.textAlign = 'right';
  const eleSteps = Math.max(1, Math.round(eleRange / 4));
  for (let e = Math.ceil(minEle / eleSteps) * eleSteps; e <= maxEle; e += eleSteps) {{
    ctx.fillText(Math.round(e) + 'm', pad.left - 4, y(e) + 4);
    ctx.beginPath();
    ctx.moveTo(pad.left, y(e));
    ctx.lineTo(w - pad.right, y(e));
    ctx.strokeStyle = '#eee';
    ctx.lineWidth = 1;
    ctx.stroke();
  }}
}}

// Alle Profile zeichnen
function drawAllProfiles() {{
  elevationData.forEach((data, i) => {{
    drawProfile('profile-' + (i + 1), data, colors[i % colors.length]);
  }});
}}
drawAllProfiles();
window.addEventListener('resize', drawAllProfiles);

// Aufklappbare Subsektionen mit Marker-Steuerung
function toggleSub(h4) {{
  const section = h4.parentElement;
  const isOpening = !section.classList.contains('open');
  section.classList.toggle('open');

  const stage = section.dataset.stage;
  const mtype = section.dataset.markerType;
  if (!stage || !mtype) return;

  const key = stage + '-' + mtype;
  const layer = markerLayers[key];
  if (!layer) return;

  if (isOpening) {{
    layer.addTo(map);
  }} else {{
    map.removeLayer(layer);
  }}
}}

// Live-Wetter von Open-Meteo
const wmoIcons = {{
  0: '☀️', 1: '🌤', 2: '⛅', 3: '☁️',
  45: '🌫', 48: '🌫',
  51: '🌦', 53: '🌦', 55: '🌧',
  61: '🌧', 63: '🌧', 65: '🌧',
  71: '🌨', 73: '🌨', 75: '❄️',
  80: '🌦', 81: '🌧', 82: '⛈',
  95: '⛈', 96: '⛈', 99: '⛈',
}};
const dayNames = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];

async function loadWeather() {{
  const widgets = document.querySelectorAll('.weather-widget');
  // Sammle einzigartige Koordinaten
  const coords = [];
  widgets.forEach(w => {{
    const lat = w.dataset.lat;
    const lon = w.dataset.lon;
    if (lat && lon && lat !== '0') {{
      coords.push({{ lat, lon, el: w }});
      w.innerHTML = '<div class="weather-loading">Lade Wetter...</div>';
    }}
  }});

  // Pro Widget einzeln laden (Koordinaten können unterschiedlich sein)
  for (const c of coords) {{
    try {{
      const url = `https://api.open-meteo.com/v1/forecast?latitude=${{c.lat}}&longitude=${{c.lon}}&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max,winddirection_10m_dominant&timezone=Europe/Berlin&forecast_days=7`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error('API-Fehler');
      const data = await resp.json();
      const d = data.daily;

      let html = '<div class="weather-row">';
      for (let i = 0; i < Math.min(7, d.time.length); i++) {{
        const date = new Date(d.time[i] + 'T00:00:00');
        const dayName = dayNames[date.getDay()];
        const dateStr = `${{date.getDate()}}.${{date.getMonth() + 1}}.`;
        const icon = wmoIcons[d.weathercode[i]] || '🌡';
        const windDir = ['N','NO','O','SO','S','SW','W','NW'][Math.round(d.winddirection_10m_dominant[i] / 45) % 8];

        html += `<div class="weather-day">
          <div class="wd-date">${{dayName}} ${{dateStr}}</div>
          <div class="wd-icon">${{icon}}</div>
          <div class="wd-temp">${{Math.round(d.temperature_2m_min[i])}}° / ${{Math.round(d.temperature_2m_max[i])}}°</div>
          <div class="wd-detail">💧 ${{d.precipitation_probability_max[i]}}%</div>
          <div class="wd-detail">💨 ${{Math.round(d.windspeed_10m_max[i])}} km/h ${{windDir}}</div>
        </div>`;
      }}
      html += '</div>';
      c.el.innerHTML = html;
    }} catch (e) {{
      c.el.innerHTML = '<div class="weather-loading">Wetter nicht verfuegbar</div>';
    }}
  }}
}}

// Wetter laden wenn Etappen-Tab sichtbar
loadWeather();

// GPS-Standort
let gpsMarker = null;
let gpsCircle = null;
let gpsWatchId = null;

function toggleGPS() {{
  const btn = document.getElementById('gps-btn');
  if (gpsWatchId !== null) {{
    navigator.geolocation.clearWatch(gpsWatchId);
    gpsWatchId = null;
    if (gpsMarker) {{ map.removeLayer(gpsMarker); gpsMarker = null; }}
    if (gpsCircle) {{ map.removeLayer(gpsCircle); gpsCircle = null; }}
    btn.classList.remove('active');
    return;
  }}

  if (!navigator.geolocation) {{
    alert('GPS wird von diesem Browser nicht unterstuetzt.');
    return;
  }}

  btn.classList.add('active');
  gpsWatchId = navigator.geolocation.watchPosition(
    pos => {{
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const acc = pos.coords.accuracy;

      if (gpsMarker) {{
        gpsMarker.setLatLng([lat, lon]);
        gpsCircle.setLatLng([lat, lon]).setRadius(acc);
      }} else {{
        gpsMarker = L.circleMarker([lat, lon], {{
          radius: 8,
          fillColor: '#3498db',
          fillOpacity: 1,
          color: 'white',
          weight: 3,
        }}).addTo(map).bindPopup('Mein Standort');
        gpsCircle = L.circle([lat, lon], {{
          radius: acc,
          color: '#3498db',
          fillColor: '#3498db',
          fillOpacity: 0.1,
          weight: 1,
        }}).addTo(map);
        map.setView([lat, lon], 13);
      }}
    }},
    err => {{
      alert('Standort konnte nicht ermittelt werden: ' + err.message);
      btn.classList.remove('active');
      gpsWatchId = null;
    }},
    {{ enableHighAccuracy: true, maximumAge: 10000 }}
  );
}}
</script>

</body>
</html>"""

    return html
