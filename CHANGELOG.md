# Änderungen

## 2.2.0 – 2026-11-05

- Eigenständige Desktop-Ausgaben für macOS Apple Silicon/Intel, Windows x64 und Linux x64 mit Python, Node und ursprünglichem Frame-Icon.
- Automatischer Serverstart im Hintergrund, Browseröffnung und Wiederverwendung eines laufenden Frame-Dienstes.
- Einmalige automatische Einrichtung der Medienwerkzeuge aus einem per SHA-256 fixierten Upstream-Paket.
- Korrekte eigene Worker-Prozesse auch in eingefrorenen App-Ausgaben; Windows-Standardstreams werden für die Download-Kommunikation eingerichtet.
- Vier native GitHub-Builds mit vollständigem App-Start und echten MP3-/MP4-Worker-Tests vor dem Release-Entwurf.
- Medien der Desktop-Ausgabe außerhalb der App unter `Downloads/Frame-Medien`.

## 2.1.0 – 2026-11-05

- Paketdownload mit bis zu 100 YouTube-Links und einer gemeinsamen Qualitäts- und Formatauswahl, einschließlich Audio.
- Einzeldateien oder ZIP64-Paket mit eindeutigen Dateinamen und Ergebnisübersicht. Große ZIPs werden auf der Festplatte vorbereitet.
- Paketfortschritt, Abbruch, gezielter Neuversuch fehlender Videos und gespeicherter Paketverlauf.
- Doppelte Links werden übersprungen; alle Links werden vor dem Anlegen des Pakets geprüft.
- Warteschlange für bis zu 200 Aufträge bei zwei gleichzeitigen Downloads.
- macOS-Starter finden Python und JavaScript-Laufzeiten auch an üblichen Installationsorten außerhalb des Terminal-PATH.
- Schutz vor doppelten Downloads bei schnellem Abbrechen und erneutem Starten eines Pakets.

## 2.0.0 – 2026-11-04

- Neues, reduziertes Dark-Design mit einer gemeinsamen Oberfläche für Video und Audio.
- MP3 mit 96, 128, 192, 256 oder 320 kbit/s.
- M4A, Opus, WAV und FLAC als weitere Audioausgaben.
- WebM zusätzlich zu MP4 und MKV; nur aus passenden WebM-Quellspuren.
- Qualitätsauswahl und Dateiinformationen passen sich dem Download-Typ an.
- Portable Starter für macOS, Windows und Linux, Diagnose und Werkzeug-Updates.
- Dokumentation, MIT-Lizenz, lokale Tests, GitHub-Prüfungen und Release-Paketierung.
- Persönliche Dateien und lokale Konfiguration sind von Git und Release-ZIPs ausgeschlossen.

## 1.0.0 – 2026-11-04

- Lokale YouTube-Video-Downloads als MP4 oder MKV.
- Auflösungsauswahl, Warteschlange, Fortschritt, Abbrechen und Verlauf.
