# Mitentwickeln

Danke für deinen Beitrag zu Frame. Die Anwendung verwendet Python 3.11+ und unverändertes HTML/CSS/JavaScript; ein Frontend-Build ist nicht nötig.

1. Repository klonen und eine Python-Umgebung erstellen.
2. `python -m pip install -r requirements.txt` ausführen.
3. Node.js 22+ oder Deno 2.3+ bereitstellen.
4. Mit `python server.py --open` lokal starten.

Vor einem Pull Request:

```sh
python -m unittest discover -s tests -v
node --check web/app.js
python tools/package.py
```

Die Tests erzeugen kurze synthetische Video- und Audiodateien in temporären Ordnern. Sie benötigen keine YouTube-Anmeldung und keine externen Videoabrufe. Bitte echte Medien, Kontodaten und deinen Download-Verlauf nicht in Test-Fixtures übernehmen.

Formatänderungen gehören in `formats.py`; die Oberfläche lädt den Katalog aus der lokalen API. Änderungen an Download-Optionen sollten die passenden Medien-Integrationstests ergänzen. Beschreibe im Pull Request die sichtbare Änderung und die durchgeführten Prüfungen.

Bitte beschränke API-Verbindungen weiter auf Loopback und behalte die Host-, Origin-, Token- und Dateipfadprüfungen bei. Sicherheitsprobleme nach [SECURITY.md](SECURITY.md) melden.
