"""OpenStreetMap Overpass API: Echte Campingplätze und Sehenswürdigkeiten entlang der Route."""

import json
import time
import urllib.request
import urllib.error
import urllib.parse
from gpx_parser import Stage, TourData, haversine

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _bounding_box(stage: Stage, padding_km: float = 10.0) -> tuple[float, float, float, float]:
    """Berechnet eine Bounding Box um die Etappe mit Padding."""
    padding_deg = padding_km / 111  # grobe Umrechnung km -> Grad
    lats = [p.lat for p in stage.points]
    lons = [p.lon for p in stage.points]
    return (
        min(lats) - padding_deg,
        min(lons) - padding_deg,
        max(lats) + padding_deg,
        max(lons) + padding_deg,
    )


def _query_overpass(query: str, retries: int = 3) -> list[dict]:
    """Führt eine Overpass-Abfrage aus mit Retries bei Rate-Limiting."""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")

    for attempt in range(retries):
        req = urllib.request.Request(OVERPASS_URL, data=data)
        req.add_header("User-Agent", "RadtourAssistent/1.0")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("elements", [])
        except urllib.error.HTTPError as e:
            if e.code in (429, 504) and attempt < retries - 1:
                wait = (attempt + 1) * 10
                print(f"(Warte {wait}s)...", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"  Overpass-Fehler: {e}")
                return []
        except Exception as e:
            print(f"  Overpass-Fehler: {e}")
            return []
    return []


def _min_distance_to_route(lat: float, lon: float, stage: Stage) -> float:
    """Minimale Distanz (km) eines Punktes zur Route."""
    min_dist = float("inf")
    # Nur jeden 5. Punkt prüfen für Performance
    step = max(1, len(stage.points) // 200)
    for i in range(0, len(stage.points), step):
        p = stage.points[i]
        d = haversine(lat, lon, p.lat, p.lon)
        if d < min_dist:
            min_dist = d
    return min_dist / 1000


def _get_name(element: dict) -> str:
    """Extrahiert den Namen aus einem OSM-Element."""
    tags = element.get("tags", {})
    return tags.get("name", tags.get("name:de", ""))


def _get_coords(element: dict) -> tuple[float, float]:
    """Extrahiert Koordinaten — für Nodes direkt, für Ways/Relations den Center."""
    if "lat" in element and "lon" in element:
        return element["lat"], element["lon"]
    center = element.get("center", {})
    return center.get("lat", 0), center.get("lon", 0)


def fetch_campsites(stage: Stage, max_dist_km: float = 10.0) -> list[dict]:
    """Holt echte Campingplätze aus OpenStreetMap."""
    bbox = _bounding_box(stage)
    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

    query = f"""[out:json][timeout:60];
(
  nwr["tourism"="camp_site"]({bbox_str});
  nwr["tourism"="caravan_site"]({bbox_str});
);
out center;"""

    elements = _query_overpass(query)
    campsites = []

    for el in elements:
        name = _get_name(el)
        if not name:
            continue

        lat, lon = _get_coords(el)
        if lat == 0 and lon == 0:
            continue

        dist = _min_distance_to_route(lat, lon, stage)
        if dist > max_dist_km:
            continue

        tags = el.get("tags", {})
        website = tags.get("website", tags.get("contact:website", tags.get("url")))

        desc_parts = []
        if tags.get("stars"):
            desc_parts.append(f"{tags['stars']} Sterne")
        if tags.get("phone") or tags.get("contact:phone"):
            desc_parts.append(f"Tel: {tags.get('phone', tags.get('contact:phone'))}")
        if tags.get("capacity"):
            desc_parts.append(f"{tags['capacity']} Stellplätze")
        desc = ", ".join(desc_parts) if desc_parts else "Campingplatz"

        campsites.append({
            "name": name,
            "description": desc,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "website": website,
            "distance_km": round(dist, 1),
        })

    # Nach Entfernung zur Route sortieren
    campsites.sort(key=lambda c: c["distance_km"])
    return campsites


def fetch_sights(stage: Stage, max_dist_km: float = 10.0) -> list[dict]:
    """Holt echte Sehenswürdigkeiten aus OpenStreetMap."""
    bbox = _bounding_box(stage)
    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

    query = f"""[out:json][timeout:60];
(
  nwr["tourism"="attraction"]({bbox_str});
  nwr["historic"~"castle|monument|memorial|ruins|archaeological_site"]({bbox_str});
  nwr["tourism"="museum"]({bbox_str});
  node["tourism"="viewpoint"]({bbox_str});
  nwr["amenity"="place_of_worship"]["heritage"]({bbox_str});
);
out center;"""

    elements = _query_overpass(query)
    sights = []

    for el in elements:
        name = _get_name(el)
        if not name:
            continue

        lat, lon = _get_coords(el)
        if lat == 0 and lon == 0:
            continue

        dist = _min_distance_to_route(lat, lon, stage)
        if dist > max_dist_km:
            continue

        tags = el.get("tags", {})

        # Kategorie bestimmen
        category = "sonstige"
        category_label = "Sehenswürdigkeit"
        if tags.get("historic") in ("castle",):
            category, category_label = "schloss", "Burg/Schloss"
        elif tags.get("historic") in ("monument", "memorial"):
            category, category_label = "denkmal", "Denkmal/Gedenkstätte"
        elif tags.get("historic") in ("ruins", "archaeological_site"):
            category, category_label = "ruine", "Ruine/Ausgrabung"
        elif tags.get("tourism") == "museum":
            category, category_label = "museum", "Museum"
        elif tags.get("tourism") == "viewpoint":
            category, category_label = "aussicht", "Aussichtspunkt"
        elif tags.get("amenity") == "place_of_worship":
            category, category_label = "kirche", "Kirche/Kloster"
        elif tags.get("tourism") == "attraction":
            category, category_label = "attraktion", "Attraktion"

        desc_parts = [category_label]
        if tags.get("description"):
            desc_parts.append(tags["description"][:100])
        desc = ", ".join(desc_parts)

        sights.append({
            "name": name,
            "description": desc,
            "category": category,
            "category_label": category_label,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "distance_km": round(dist, 1),
        })

    sights.sort(key=lambda s: s["distance_km"])
    return sights


def _cache_path(tour_name: str) -> str:
    """Pfad zur Cache-Datei."""
    import os
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
    os.makedirs(cache_dir, exist_ok=True)
    safe = tour_name.replace(" ", "_").replace("/", "-")
    return os.path.join(cache_dir, f"{safe}_osm.json")


def _load_cache(tour_name: str) -> dict:
    """Lädt gecachte OSM-Daten."""
    path = _cache_path(tour_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(tour_name: str, data: dict):
    """Speichert OSM-Daten im Cache."""
    path = _cache_path(tour_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_osm_data(tour: TourData, max_dist_km: float = 10.0) -> list[tuple[list[dict], list[dict]]]:
    """Holt Campingplätze und Sehenswürdigkeiten für alle Etappen.
    Nutzt Cache für bereits erfolgreich geladene Daten.

    Returns:
        Liste von (campsites, sights) Tupeln, eins pro Etappe.
    """
    cache = _load_cache(tour.name)
    results = []

    for i, stage in enumerate(tour.stages):
        key = f"etappe_{i+1}"
        cached = cache.get(key, {})
        cached_camps = cached.get("campsites", [])
        cached_sights = cached.get("sights", [])

        need_camps = len(cached_camps) == 0
        need_sights = len(cached_sights) == 0

        if not need_camps and not need_sights:
            print(f"  Etappe {i+1}: Cache — {len(cached_camps)} Campingplätze, {len(cached_sights)} Sehenswürdigkeiten")
            results.append((cached_camps, cached_sights))
            continue

        print(f"  Etappe {i+1}: Lade OSM-Daten...", end=" ", flush=True)

        if need_camps:
            campsites = fetch_campsites(stage, max_dist_km)
            time.sleep(5)
        else:
            campsites = cached_camps

        if need_sights:
            sights = fetch_sights(stage, max_dist_km)
        else:
            sights = cached_sights

        print(f"{len(campsites)} Campingplätze, {len(sights)} Sehenswürdigkeiten")

        # Nur cachen wenn erfolgreich
        cache_entry = {}
        cache_entry["campsites"] = campsites if len(campsites) > 0 else cached_camps
        cache_entry["sights"] = sights if len(sights) > 0 else cached_sights
        cache[key] = cache_entry

        results.append((campsites if len(campsites) > 0 else cached_camps,
                        sights if len(sights) > 0 else cached_sights))

        if i < len(tour.stages) - 1:
            time.sleep(8)

    _save_cache(tour.name, cache)
    return results
