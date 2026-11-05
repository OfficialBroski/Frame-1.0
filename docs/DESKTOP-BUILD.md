# Eigenständige Desktop-Releases bauen

Jede Plattform wird nativ gebaut: Ein Windows-Build entsteht auf Windows, ein Mac-Build auf einem Mac und ein Linux-Build auf Linux. Der Workflow `Desktop apps` erledigt das für Windows x64, Linux x64 sowie Apple-Silicon- und Intel-Macs. Die fertigen Archive liegen bei dem Lauf unter **Artifacts**.

## Lokal

Python 3.12 auf der Zielplattform verwenden. Einen sauberen Build-Ordner benutzen:

```sh
python -m venv .buildenv
# macOS / Linux: . .buildenv/bin/activate
# Windows PowerShell: .buildenv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
python tools/build_desktop.py
python tools/smoke_desktop.py
```

Die Archive und SHA-256-Dateien entstehen in `dist/`. Die Prüfung startet einen getrennten lokalen Dienst, richtet die Medienwerkzeuge in einem temporären Ordner ein und prüft echte MP3-/MP4-Downloads aus selbst erzeugten lokalen Testmedien. Persönliche Dateien oder YouTube-Abrufe sind dafür nicht nötig.

## GitHub-Release

1. Die vollständige aktuelle Projektversion einschließlich `.github`, `resources`, `desktop.py` und `runtime_setup.py` übernehmen.
2. Unter **Actions → Desktop apps → Run workflow** bei Bedarf die Builds vorab prüfen.
3. Einen Tag **v2.2.0** auf den geprüften Commit setzen und pushen. Alternativ unter GitHub **Releases → Draft a new release** zunächst einen Tag erstellen; der vorbereitete Tag-Workflow erstellt anschließend den eigentlichen Release-Entwurf mit allen Dateien. Am einfachsten den Tag im Terminal oder mit GitHub Desktop pushen und den fertigen Workflow-Entwurf verwenden.
4. Der Workflow **Release** wartet auf Tests und alle vier nativen Builds. Erst danach erstellt er einen **Entwurf** mit den vier App-Archiven, dem Quellcode und Prüfsummen.
5. Unter **Releases** diesen fertigen Entwurf prüfen und veröffentlichen.

Ein manueller Release-Workflow ohne Versionstag erstellt ein vollständiges Download-Artefakt und veröffentlicht nichts. Der Workflow benötigt kein eigenes Secret; er verwendet das GitHub-Repository-Token mit Schreibrecht nur im abschließenden Entwurfsjob.

## Enthaltene Werkzeuge und Daten

PyInstaller bündelt Python, Frame, yt-dlp und dessen Laufzeitpakete. Node 24.22.2 kommt ausschließlich vom offiziellen Node.js-Downloadserver; Archive werden gegen die eingecheckten SHA-256-Werte geprüft. Die Python- und Node-Lizenztexte sowie Lizenzhinweise der Laufzeitpakete werden beigefügt.

FFmpeg-Binärdateien sind nicht in den Frame-Archiven enthalten. Die App bezieht beim ersten Start genau das für die Plattform festgelegte imageio-ffmpeg-Paket direkt von dessen PyPI-Verteiler. URL, Größe und SHA-256 stehen in `resources/ffmpeg-downloads.json`. Extrahiert wird nur die Werkzeugdatei in ein benutzerspezifisches Verzeichnis außerhalb der App. Erneute Starts verwenden diese Datei. Für künftige Werkzeugaktualisierungen Manifest, Cache-Versionspfad und Tests gemeinsam anpassen; vorhandene laufende Tools nicht überschreiben.

Lokale Downloads, Verlauf, Konfiguration, `.runtime`, Build-Umgebung und Benutzernamen sind keine Release-Eingaben. Der neue App-Starter speichert Medien in `~/Downloads/Frame-Medien`; der Quellcode-Starter behält sein bisheriges `downloads`-Verzeichnis. Die bestehende lokale Dock-App von vor 2.2 hat ihre eigene Einrichtung und wird durch einen Build nicht verändert.

## Öffentliche Signierung

Die Mac-Bundles werden lokal ad hoc signiert, um ihre Integrität prüfen zu können. Für Apple-Notarisierung und eine Herausgebersignatur unter Windows sind eigene Entwicklerzertifikate und ein gesonderter Signierschritt erforderlich. Dieser Workflow behauptet keine Apple- oder Microsoft-Vertrauenssignatur und benötigt keine privaten Zertifikate.
