"""GPX-Parser: Liest Komoot-GPX ein und berechnet Etappen, Distanz, Höhenmeter."""

import gpxpy
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class Trackpoint:
    lat: float
    lon: float
    ele: float
    time: datetime | None


@dataclass
class Stage:
    """Eine Tagesetappe."""
    name: str
    day: int
    start_point: str
    end_point: str
    distance_km: float
    elevation_gain: float
    elevation_loss: float
    duration: timedelta | None
    points: list[Trackpoint] = field(default_factory=list)
    waypoints: list[dict] = field(default_factory=list)

    @property
    def start_lat(self) -> float:
        return self.points[0].lat if self.points else 0

    @property
    def start_lon(self) -> float:
        return self.points[0].lon if self.points else 0

    @property
    def end_lat(self) -> float:
        return self.points[-1].lat if self.points else 0

    @property
    def end_lon(self) -> float:
        return self.points[-1].lon if self.points else 0


@dataclass
class TourData:
    """Gesamte Tour-Daten."""
    name: str
    total_distance_km: float
    total_elevation_gain: float
    total_elevation_loss: float
    total_duration: timedelta | None
    stages: list[Stage]
    min_ele: float
    max_ele: float


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanz zwischen zwei Koordinaten in Metern (Haversine-Formel)."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


_geocode_cache: dict[str, str] = {}


def reverse_geocode_simple(lat: float, lon: float) -> str:
    """Ortsbestimmung via Nominatim Reverse Geocoding mit Cache und Retries."""
    import urllib.request
    import urllib.error
    import json
    import time

    # Cache-Key auf 2 Dezimalstellen (gleicher Ort bei ~1km Abweichung)
    cache_key = f"{round(lat, 2)},{round(lon, 2)}"
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    url = (
        f"https://nominatim.openstreetmap.org/reverse?"
        f"lat={lat}&lon={lon}&format=json&zoom=10&addressdetails=1"
    )

    for attempt in range(3):
        time.sleep(1.5)  # Nominatim Rate-Limit: max 1 req/s
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "RadtourAssistent/1.0")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            addr = data.get("address", {})
            name = (
                addr.get("city")
                or addr.get("town")
                or addr.get("village")
                or addr.get("municipality")
                or addr.get("county", "Unbekannt")
            )
            _geocode_cache[cache_key] = name
            return name
        except Exception:
            if attempt < 2:
                time.sleep(3)
    return "Unbekannt"


def parse_gpx(filepath: str, max_km_per_day: float = 30) -> TourData:
    """Parst eine GPX-Datei und teilt die Tour in Tagesetappen auf.

    Args:
        filepath: Pfad zur GPX-Datei
        max_km_per_day: Maximale Kilometer pro Tagesetappe für die automatische Aufteilung
    """
    with open(filepath, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    tour_name = gpx.tracks[0].name if gpx.tracks else "Radtour"

    # Alle Trackpoints sammeln
    all_points: list[Trackpoint] = []
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                all_points.append(Trackpoint(
                    lat=pt.latitude,
                    lon=pt.longitude,
                    ele=pt.elevation or 0,
                    time=pt.time,
                ))

    if not all_points:
        raise ValueError("Keine Trackpoints in der GPX-Datei gefunden.")

    # Gesamtstatistiken berechnen
    total_dist = 0.0
    total_gain = 0.0
    total_loss = 0.0
    min_ele = float("inf")
    max_ele = float("-inf")

    # Kumulative Distanzen berechnen für Etappenaufteilung
    cumulative_distances = [0.0]
    for i in range(1, len(all_points)):
        p1, p2 = all_points[i - 1], all_points[i]
        d = haversine(p1.lat, p1.lon, p2.lat, p2.lon)
        total_dist += d
        cumulative_distances.append(total_dist)

        ele_diff = p2.ele - p1.ele
        if ele_diff > 0:
            total_gain += ele_diff
        else:
            total_loss += abs(ele_diff)

        min_ele = min(min_ele, p1.ele, p2.ele)
        max_ele = max(max_ele, p1.ele, p2.ele)

    total_dist_km = total_dist / 1000

    # Etappen aufteilen basierend auf max_km_per_day
    stages: list[Stage] = []
    stage_start_idx = 0
    day = 1

    for i in range(1, len(all_points)):
        stage_dist = (cumulative_distances[i] - cumulative_distances[stage_start_idx]) / 1000

        is_last_point = i == len(all_points) - 1
        should_split = stage_dist >= max_km_per_day and not is_last_point

        if should_split or is_last_point:
            end_idx = i if is_last_point else i
            stage_points = all_points[stage_start_idx:end_idx + 1]

            # Etappen-Statistiken
            s_gain = 0.0
            s_loss = 0.0
            s_dist = 0.0
            for j in range(1, len(stage_points)):
                p1, p2 = stage_points[j - 1], stage_points[j]
                s_dist += haversine(p1.lat, p1.lon, p2.lat, p2.lon)
                ele_diff = p2.ele - p1.ele
                if ele_diff > 0:
                    s_gain += ele_diff
                else:
                    s_loss += abs(ele_diff)

            start_name = reverse_geocode_simple(stage_points[0].lat, stage_points[0].lon)
            end_name = reverse_geocode_simple(stage_points[-1].lat, stage_points[-1].lon)

            duration = None
            if stage_points[0].time and stage_points[-1].time:
                duration = stage_points[-1].time - stage_points[0].time

            # Punkte ausdünnen für die HTML-Karte (jeden N-ten Punkt behalten)
            thin_factor = max(1, len(stage_points) // 500)
            thinned = stage_points[::thin_factor]
            if stage_points[-1] not in thinned:
                thinned.append(stage_points[-1])

            stages.append(Stage(
                name=f"{start_name} → {end_name}",
                day=day,
                start_point=start_name,
                end_point=end_name,
                distance_km=round(s_dist / 1000, 1),
                elevation_gain=round(s_gain),
                elevation_loss=round(s_loss),
                duration=duration,
                points=thinned,
            ))

            if not is_last_point:
                stage_start_idx = i
                day += 1

    total_duration = None
    if all_points[0].time and all_points[-1].time:
        total_duration = all_points[-1].time - all_points[0].time

    return TourData(
        name=tour_name,
        total_distance_km=round(total_dist_km, 1),
        total_elevation_gain=round(total_gain),
        total_elevation_loss=round(total_loss),
        total_duration=total_duration,
        stages=stages,
        min_ele=round(min_ele),
        max_ele=round(max_ele),
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python gpx_parser.py <gpx-file>")
        sys.exit(1)

    tour = parse_gpx(sys.argv[1])
    print(f"Tour: {tour.name}")
    print(f"Gesamt: {tour.total_distance_km} km, ↑{tour.total_elevation_gain}m ↓{tour.total_elevation_loss}m")
    print(f"Höhe: {tour.min_ele}m – {tour.max_ele}m")
    print(f"Etappen: {len(tour.stages)}")
    for stage in tour.stages:
        print(f"  {stage.name}: {stage.distance_km} km, ↑{stage.elevation_gain}m ↓{stage.elevation_loss}m")
