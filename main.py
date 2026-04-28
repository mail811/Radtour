"""Radtour Assistent — Hauptscript.

Liest eine Komoot-GPX-Datei ein, reichert sie mit Infos an und
generiert eine mobile-freundliche HTML-Seite.

Nutzung:
    python main.py <gpx-datei> [--etappen N] [--output pfad.html]
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from gpx_parser import parse_gpx
from api_enricher import enrich_tour
from html_generator import generate_html
from build_index import build_index


def main():
    parser = argparse.ArgumentParser(description="Radtour Assistent")
    parser.add_argument("gpx_file", help="Pfad zur GPX-Datei (z.B. von Komoot)")
    parser.add_argument("--etappen", type=int, default=None,
                        help="Gewuenschte Anzahl Etappen (Standard: automatisch nach ~100km)")
    parser.add_argument("--max-km", type=float, default=30,
                        help="Maximale Kilometer pro Etappe (Standard: 30)")
    parser.add_argument("--fahrer", default=None,
                        help="Namen der Fahrer, kommagetrennt (z.B. 'Yannic,Phil,Basti')")
    parser.add_argument("--output", "-o", default=None,
                        help="Ausgabepfad fuer die HTML-Datei")

    args = parser.parse_args()

    if not os.path.exists(args.gpx_file):
        print(f"Fehler: Datei '{args.gpx_file}' nicht gefunden.")
        sys.exit(1)

    # 1. GPX parsen
    print(f"Lese GPX-Datei: {args.gpx_file}")
    if args.etappen:
        # Berechne max_km basierend auf gewuenschter Etappenanzahl
        # Erst mal grob parsen um Gesamtdistanz zu kennen
        tour = parse_gpx(args.gpx_file, max_km_per_day=9999)
        max_km = tour.total_distance_km / args.etappen
        tour = parse_gpx(args.gpx_file, max_km_per_day=max_km)
    else:
        tour = parse_gpx(args.gpx_file, max_km_per_day=args.max_km)

    print(f"Tour: {tour.name}")
    print(f"Gesamt: {tour.total_distance_km} km, {tour.total_elevation_gain}m hoch, {tour.total_elevation_loss}m runter")
    print(f"Etappen: {len(tour.stages)}")
    for stage in tour.stages:
        print(f"  Tag {stage.day}: {stage.start_point} -> {stage.end_point} ({stage.distance_km} km)")

    # 2. Mit Claude API anreichern
    print("\nReichere Tour mit Infos an...")
    enrichments = enrich_tour(tour)

    # 3. HTML generieren
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    if args.output:
        output_path = args.output
    else:
        umlauts = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue",
                                  "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})
        safe_name = tour.name.translate(umlauts).replace(" ", "_").replace("/", "-")
        output_path = os.path.join(output_dir, f"{safe_name}.html")

    # Fahrer parsen
    riders = None
    if args.fahrer:
        riders = [name.strip() for name in args.fahrer.split(",")]

    print(f"\nGeneriere HTML: {output_path}")
    html = generate_html(tour, enrichments, riders=riders)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 4. Index aktualisieren
    build_index()

    print(f"\nFertig! Oeffne die Datei im Browser:")
    print(f"  {output_path}")


if __name__ == "__main__":
    main()
