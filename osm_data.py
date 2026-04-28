"""OpenStreetMap Overpass API: Campingplätze, Sehenswürdigkeiten, Gastronomie, Notfall-Infos und Oberflächen entlang der Route."""

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

        # Notabilitaets-Score: Wiki/Heritage zuerst, dann nach Naehe sortieren.
        score = 0
        if tags.get("wikipedia") or tags.get("wikidata"):
            score += 10
        if tags.get("heritage"):
            score += 5
        if tags.get("stars") or tags.get("admission"):
            score += 2

        sights.append({
            "name": name,
            "description": desc,
            "category": category,
            "category_label": category_label,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "distance_km": round(dist, 1),
            "score": score,
        })

    sights.sort(key=lambda s: (-s["score"], s["distance_km"]))
    return sights[:50]


def fetch_gastro(stage: Stage, max_dist_km: float = 5.0) -> list[dict]:
    """Holt Supermärkte, Cafés und Restaurants aus OpenStreetMap."""
    bbox = _bounding_box(stage, padding_km=5.0)
    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

    query = f"""[out:json][timeout:60];
(
  nwr["shop"="supermarket"]({bbox_str});
  nwr["amenity"="cafe"]({bbox_str});
  nwr["amenity"="restaurant"]({bbox_str});
);
out center;"""

    elements = _query_overpass(query)
    results = []

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

        # Kategorie
        if tags.get("shop") == "supermarket":
            category, icon = "supermarkt", "🛒"
        elif tags.get("amenity") == "cafe":
            category, icon = "cafe", "☕"
        else:
            category, icon = "restaurant", "🍽"

        website = tags.get("website", tags.get("contact:website", tags.get("url")))

        opening = tags.get("opening_hours", "")

        results.append({
            "name": name,
            "category": category,
            "icon": icon,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "website": website,
            "opening_hours": opening,
            "distance_km": round(dist, 1),
        })

    results.sort(key=lambda r: r["distance_km"])
    return results


def fetch_emergency(stage: Stage, max_dist_km: float = 15.0) -> list[dict]:
    """Holt Fahrradwerkstätten, Krankenhäuser und Bahnhöfe aus OpenStreetMap."""
    bbox = _bounding_box(stage, padding_km=15.0)
    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

    query = f"""[out:json][timeout:60];
(
  nwr["shop"="bicycle"]({bbox_str});
  nwr["amenity"="hospital"]({bbox_str});
  node["railway"="station"]({bbox_str});
  node["railway"="halt"]({bbox_str});
);
out center;"""

    elements = _query_overpass(query)
    results = []

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

        if tags.get("shop") == "bicycle":
            category, icon = "fahrrad", "🔧"
        elif tags.get("amenity") == "hospital":
            category, icon = "krankenhaus", "🏥"
        else:
            category, icon = "bahnhof", "🚉"

        website = tags.get("website", tags.get("contact:website", tags.get("url")))
        phone = tags.get("phone", tags.get("contact:phone", ""))

        results.append({
            "name": name,
            "category": category,
            "icon": icon,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "website": website,
            "phone": phone,
            "distance_km": round(dist, 1),
        })

    results.sort(key=lambda r: r["distance_km"])
    return results


def fetch_lodging(stage: Stage, radius_km: float = 5.0) -> list[dict]:
    """Holt Hotels, Hostels und Pensionen rund um den Etappenendpunkt."""
    end_lat = stage.points[-1].lat
    end_lon = stage.points[-1].lon
    radius_m = int(radius_km * 1000)

    query = f"""[out:json][timeout:60];
(
  nwr["tourism"="hotel"](around:{radius_m},{end_lat},{end_lon});
  nwr["tourism"="hostel"](around:{radius_m},{end_lat},{end_lon});
  nwr["tourism"="guest_house"](around:{radius_m},{end_lat},{end_lon});
  nwr["tourism"="motel"](around:{radius_m},{end_lat},{end_lon});
);
out center;"""

    elements = _query_overpass(query)
    results = []

    type_labels = {
        "hotel": "Hotel",
        "hostel": "Hostel",
        "guest_house": "Pension",
        "motel": "Motel",
    }
    type_icons = {
        "hotel": "🏨",
        "hostel": "🛏",
        "guest_house": "🏠",
        "motel": "🏨",
    }

    for el in elements:
        name = _get_name(el)
        if not name:
            continue

        lat, lon = _get_coords(el)
        if lat == 0 and lon == 0:
            continue

        dist = haversine(lat, lon, end_lat, end_lon) / 1000
        if dist > radius_km:
            continue

        tags = el.get("tags", {})
        tourism_type = tags.get("tourism", "hotel")
        category_label = type_labels.get(tourism_type, "Unterkunft")
        icon = type_icons.get(tourism_type, "🏨")

        website = tags.get("website", tags.get("contact:website", tags.get("url")))
        phone = tags.get("phone", tags.get("contact:phone", ""))
        stars = tags.get("stars", "")

        desc_parts = [category_label]
        if stars:
            desc_parts.append(f"{stars}★")
        desc = ", ".join(desc_parts)

        results.append({
            "name": name,
            "description": desc,
            "category": tourism_type,
            "category_label": category_label,
            "icon": icon,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "website": website,
            "phone": phone,
            "distance_km": round(dist, 1),
        })

    results.sort(key=lambda r: r["distance_km"])
    return results


def fetch_surface(stage: Stage) -> dict:
    """Ermittelt Straßenoberflächen entlang der Etappe via Overpass."""
    bbox = _bounding_box(stage, padding_km=2.0)
    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

    query = f"""[out:json][timeout:60];
way["highway"]["surface"]({bbox_str});
out tags;"""

    elements = _query_overpass(query)

    surface_counts: dict[str, int] = {}
    for el in elements:
        tags = el.get("tags", {})
        surface = tags.get("surface", "unknown")
        highway = tags.get("highway", "")
        # Nur relevante Straßentypen für Radfahrer
        if highway in ("motorway", "motorway_link", "trunk", "trunk_link"):
            continue
        surface_counts[surface] = surface_counts.get(surface, 0) + 1

    total = sum(surface_counts.values()) or 1

    # Oberflächen-Typen gruppieren
    labels = {
        "asphalt": "Asphalt",
        "paved": "Befestigt",
        "concrete": "Beton",
        "paving_stones": "Pflaster",
        "cobblestone": "Kopfsteinpflaster",
        "sett": "Kopfsteinpflaster",
        "compacted": "Verdichtet",
        "fine_gravel": "Feinkies",
        "gravel": "Schotter",
        "unpaved": "Unbefestigt",
        "ground": "Naturweg",
        "dirt": "Feldweg",
        "grass": "Gras",
        "sand": "Sand",
        "wood": "Holz",
    }

    surfaces = []
    for surface, count in sorted(surface_counts.items(), key=lambda x: -x[1]):
        pct = round(count / total * 100)
        if pct < 2:
            continue
        surfaces.append({
            "type": surface,
            "label": labels.get(surface, surface.replace("_", " ").title()),
            "percent": pct,
        })

    # Bewertung für Radfahrer
    paved_types = {"asphalt", "paved", "concrete", "paving_stones", "sett"}
    paved_pct = sum(c for s, c in surface_counts.items() if s in paved_types)
    paved_pct = round(paved_pct / total * 100)

    return {
        "surfaces": surfaces,
        "paved_percent": paved_pct,
    }


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


def fetch_osm_data(tour: TourData, max_dist_km: float = 10.0) -> list[dict]:
    """Holt alle OSM-Daten für alle Etappen.
    Nutzt Cache für bereits erfolgreich geladene Daten.

    Returns:
        Liste von Dicts mit campsites, sights, gastro, emergency, surface pro Etappe.
    """
    cache = _load_cache(tour.name)
    results = []

    data_types = [
        ("campsites", lambda s: fetch_campsites(s, max_dist_km)),
        ("lodging", lambda s: fetch_lodging(s)),
        ("sights", lambda s: fetch_sights(s, max_dist_km)),
        ("gastro", lambda s: fetch_gastro(s)),
        ("emergency", lambda s: fetch_emergency(s)),
        ("surface", lambda s: fetch_surface(s)),
    ]

    for i, stage in enumerate(tour.stages):
        key = f"etappe_{i+1}"
        cached = cache.get(key, {})

        # Prüfen was fehlt
        to_fetch = []
        for dtype, fetcher in data_types:
            cached_val = cached.get(dtype)
            if not cached_val or (isinstance(cached_val, list) and len(cached_val) == 0):
                to_fetch.append((dtype, fetcher))

        if not to_fetch:
            counts = ", ".join(
                f"{len(cached[dt]) if isinstance(cached[dt], list) else 'ok'} {dt}"
                for dt, _ in data_types
            )
            print(f"  Etappe {i+1}: Cache — {counts}")
            results.append(cached)
            continue

        print(f"  Etappe {i+1}: Lade {', '.join(dt for dt, _ in to_fetch)}...", end=" ", flush=True)

        entry = dict(cached)
        for dtype, fetcher in to_fetch:
            data = fetcher(stage)
            # Nur cachen wenn erfolgreich (Listen: nicht leer, Dicts: hat Inhalt)
            if isinstance(data, list) and len(data) > 0:
                entry[dtype] = data
            elif isinstance(data, dict) and data.get("surfaces"):
                entry[dtype] = data
            else:
                entry[dtype] = cached.get(dtype, data)
            time.sleep(5)

        # Zusammenfassung
        parts = []
        for dtype, _ in data_types:
            val = entry.get(dtype)
            if isinstance(val, list):
                parts.append(f"{len(val)} {dtype}")
            elif isinstance(val, dict):
                parts.append(f"ok {dtype}")
        print(", ".join(parts))

        cache[key] = entry
        results.append(entry)

        if i < len(tour.stages) - 1:
            time.sleep(3)

    _save_cache(tour.name, cache)
    return results
