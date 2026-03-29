# Radtour Assistent

Mehrtägige Radtouren planen: GPX einlesen, Etappen berechnen, echte Campingplätze und Sehenswürdigkeiten aus OpenStreetMap laden, Trivia per Claude API generieren, alles als mobile-friendly HTML ausgeben.

## Struktur
- `main.py` — Hauptscript, orchestriert alles
- `gpx_parser.py` — GPX einlesen, Distanz/Höhenmeter/Etappen berechnen
- `osm_data.py` — OpenStreetMap Overpass API für Campingplätze und Sehenswürdigkeiten
- `api_enricher.py` — Claude API für Trivia + OSM-Daten zusammenführen
- `html_generator.py` — HTML-Ausgabe generieren
- `output/` — Generierte HTML-Dateien
- `cache/` — Gecachte OSM-Daten (werden wiederverwendet)

## Nutzung
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
python main.py pfad/zur/tour.gpx --etappen 6 --fahrer "Yannic,Phil,Basti"
```

### Parameter
- `--etappen N` — Gewünschte Anzahl Etappen
- `--max-km N` — Maximale km pro Etappe (Alternative zu --etappen)
- `--fahrer "Name1,Name2,Name3"` — Namen für die Packliste
- `--output pfad.html` — Ausgabepfad
