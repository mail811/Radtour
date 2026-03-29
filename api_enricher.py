"""Anreicherung: OSM-Daten für Orte + Claude API für Trivia und Beschreibungen."""

import json
import os
from dataclasses import dataclass

import anthropic

from gpx_parser import Stage, TourData
from osm_data import fetch_osm_data


@dataclass
class StageEnrichment:
    """Angereicherte Daten für eine Etappe."""
    sights: list[dict]
    campsites: list[dict]
    trivia: list[str]
    towns: list[str]
    terrain_description: str


def _sample_waypoints(stage: Stage, n: int = 10) -> list[tuple[float, float]]:
    """Nimmt N gleichmäßig verteilte Wegpunkte aus einer Etappe."""
    points = stage.points
    if len(points) <= n:
        return [(p.lat, p.lon) for p in points]
    step = max(1, len(points) // n)
    sampled = [(points[i].lat, points[i].lon) for i in range(0, len(points), step)]
    if (points[-1].lat, points[-1].lon) not in sampled:
        sampled.append((points[-1].lat, points[-1].lon))
    return sampled[:n + 1]


def _build_trivia_prompt(tour: TourData) -> str:
    """Baut den Prompt für Trivia und Ortsbeschreibungen."""
    stages_info = []
    for stage in tour.stages:
        stages_info.append(
            f"- {stage.name}: {stage.distance_km} km, "
            f"von {stage.start_point} nach {stage.end_point}"
        )

    return f"""Du bist ein Experte für Radtouren und Regionalgeschichte in Deutschland.
Ich plane folgende Radtour:

**{tour.name}**
Gesamtstrecke: {tour.total_distance_km} km

Etappen:
{chr(10).join(stages_info)}

Bitte gib mir für JEDE Etappe als JSON-Array:
- "stage_day": Etappen-Nummer (int)
- "towns": Liste der wichtigsten Orte auf der Strecke (Strings)
- "terrain_description": Beschreibung der Landschaft und des Geländes (2-3 Sätze, hilfreich für Radfahrer)
- "trivia": Array von 4-6 interessante, überraschende oder unterhaltsame Fakten über die Gegend (Strings). Denk an Geschichte, Natur, lokale Besonderheiten, berühmte Personen, kulinarische Spezialitäten.

Antworte NUR mit validem JSON. Keine Erklärungen davor oder danach."""


def enrich_tour(tour: TourData, max_dist_km: float = 10.0) -> list[StageEnrichment]:
    """Reichert die Tour an: OSM für Orte, Claude API für Trivia."""

    # 1. Echte Daten aus OpenStreetMap
    print("Lade echte Daten aus OpenStreetMap...")
    osm_results = fetch_osm_data(tour, max_dist_km=max_dist_km)

    # 2. Trivia von Claude API
    trivia_data = _fetch_trivia(tour)

    # 3. Zusammenführen
    enrichments = []
    for i, stage in enumerate(tour.stages):
        campsites, sights = osm_results[i] if i < len(osm_results) else ([], [])
        trivia_item = trivia_data[i] if i < len(trivia_data) else {}

        enrichments.append(StageEnrichment(
            sights=sights,
            campsites=campsites,
            trivia=trivia_item.get("trivia", []),
            towns=trivia_item.get("towns", [stage.start_point, stage.end_point]),
            terrain_description=trivia_item.get("terrain_description", ""),
        ))

    return enrichments


def _fetch_trivia(tour: TourData) -> list[dict]:
    """Holt Trivia und Beschreibungen von der Claude API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Kein ANTHROPIC_API_KEY gesetzt. Überspringe Trivia.")
        return [{} for _ in tour.stages]

    print("Lade Trivia von Claude API...")
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_trivia_prompt(tour)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  API-Fehler: {e}")
        return [{} for _ in tour.stages]

    response_text = message.content[0].text.strip()

    # JSON extrahieren
    import re
    if "```" in response_text:
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response_text, re.DOTALL)
        if match:
            response_text = match.group(1).strip()

    if not response_text.startswith("["):
        start = response_text.find("[")
        end = response_text.rfind("]")
        if start != -1 and end != -1:
            response_text = response_text[start:end + 1]

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as exc:
        print(f"  JSON-Fehler: {exc}")
        return [{} for _ in tour.stages]
