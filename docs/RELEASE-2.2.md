# Frame 2.2

Fertige Downloads für macOS, Windows und Linux – mit Browseroberfläche, automatischem Serverstart und Paketdownload.

## Welcher Download ist richtig?

| Dein Rechner | Datei |
| --- | --- |
| Mac mit M1, M2, M3, M4 oder neuer | `Frame-v2.2.0-macOS-AppleSilicon.zip` |
| Mac mit Intel-Prozessor | `Frame-v2.2.0-macOS-Intel.zip` |
| Windows 10/11, 64 Bit | `Frame-v2.2.0-Windows-x64.zip` |
| Linux, 64 Bit, z. B. Ubuntu 22.04+ | `Frame-v2.2.0-Linux-x64.tar.gz` |
| Quellcode zum Entwickeln | `Frame-v2.2.0.zip` |

Archiv vollständig entpacken. Auf dem Mac `Frame.app` nach Programme ziehen und öffnen; unter Windows `Frame.exe` im entpackten Ordner öffnen; unter Linux die Datei `Frame` starten. Unter Windows und Linux den gesamten entpackten Ordner zusammenlassen. Python und Node.js müssen nicht installiert werden.

Beim ersten Start werden die Medienwerkzeuge einmalig automatisch über den offiziellen PyPI-Verteiler von imageio-ffmpeg geladen und per SHA-256 geprüft. Dafür ist eine Internetverbindung nötig. Danach öffnet sich Frame im Standardbrowser. Neue Downloads landen unter `Downloads/Frame-Medien`. Der Server läuft im Hintergrund bis zum Beenden oder Neustart des Rechners.

## Neu

- Bis zu 100 YouTube-Links pro Paket, ein Format und eine Qualität für alle.
- MP4, MKV, WebM sowie MP3, M4A, Opus, WAV und FLAC.
- Einzeldateien oder ZIP mit Übersicht der erfolgreichen und fehlgeschlagenen Videos.
- Abbrechen, gezielt erneut versuchen und gespeicherter Verlauf.
- Eigenständige App-Starter, ohne Terminal oder manuelle Python-Einrichtung.
- Prüfsummen neben jedem Download.

Die Mac-Version ist für macOS 14+ vorgesehen. Windows- und Mac-Apps sind noch nicht mit einem öffentlichen Herausgeberzertifikat signiert beziehungsweise bei Apple notarisiert; das Betriebssystem kann beim ersten Öffnen eine Freigabe verlangen. Auf Linux wird glibc 2.35+ benötigt; Alpine/musl und ARM-Linux sind nicht Bestandteil dieses Releases.

Die Quellcode-Starter bleiben als Alternative erhalten. Bestehende Downloads werden nicht gelöscht. Für eigene oder zum Download freigegebene Inhalte verwenden. YouTube kann einzelne Videos weiterhin durch Anmeldepflicht oder Abrufbeschränkungen blockieren.
