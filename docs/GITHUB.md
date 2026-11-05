# Frame auf GitHub veröffentlichen

Das Projekt ist zur Weitergabe als lokale Anwendung vorbereitet. Nutzer laden es herunter, starten es auf ihrem Rechner und bedienen es im Browser. Ein zusätzlich gemieteter Server ist dafür nicht nötig.

## Bequemer Weg: GitHub Desktop

1. [GitHub Desktop](https://desktop.github.com/) installieren und mit deinem GitHub-Konto anmelden.
2. **File → Add Local Repository** wählen und den Ordner **Frame** auswählen, in dem `README.md` und `server.py` liegen.
3. Falls noch kein Repository vorhanden ist, über den angebotenen Link ein Repository in diesem Ordner erstellen. Keine vorhandenen Projektdateien überschreiben.
4. Die Dateiliste prüfen. `.runtime`, `downloads` und `frame.local.json` werden automatisch ignoriert. Es sollten nur Quellcode, Dokumentation und `.github`-Dateien erscheinen.
5. Einen ersten Commit erstellen, etwa mit „Frame 2.2: local video and audio downloader“ als Beschreibung.
6. **Publish repository** wählen. Als Namen zum Beispiel `frame-downloader` verwenden. Für eine öffentliche Veröffentlichung „Keep this code private“ abwählen und veröffentlichen.
7. Im neuen GitHub-Repository unter **Actions** die Prüfung „Checks“ ansehen. Das Ergebnis wird nach dem ersten Push angezeigt.

Die öffentliche Veröffentlichung und die Wahl deines Repository-Namens erfolgen durch dich. Dieses vorbereitete Projekt enthält keinen vorkonfigurierten fremden GitHub-Zugang und keine Remote-Adresse.

## Alternative: Terminal

Im Frame-Ordner ausführen. `DEIN-NAME` und `DEIN-REPO` durch deine tatsächlichen GitHub-Angaben ersetzen. Auf GitHub vorher ein **leeres** Repository ohne zusätzliche README oder Lizenz anlegen.

```sh
# Nur wenn der Ordner noch kein Git-Repository ist:
git init -b main

git add .
git status --short
git commit -m "Frame 2.2: local video and audio downloader"
git remote add origin https://github.com/DEIN-NAME/DEIN-REPO.git
git push -u origin main
```

Git muss mit deinem eigenen Namen und deiner bevorzugten Commit-E-Mail eingerichtet sein. Für die Anmeldung den normalen GitHub- oder GitHub-Desktop-Dialog verwenden; Zugangsdaten gehören nicht in die Projektdateien.

## Einen Download unter Releases anbieten

Die Desktop-Downloads enthalten die fertige App. Der Release-Workflow baut macOS Apple Silicon, macOS Intel, Windows x64 und Linux x64 und hängt deren Archive sowie den Quellcode an einen Release-Entwurf an. Details: [DESKTOP-BUILD.md](DESKTOP-BUILD.md).

### Über den vorbereiteten Workflow

Nachdem die Tests erfolgreich sind und die Versionsnummer in `formats.py` stimmt:

```sh
git tag v2.2.0
git push origin v2.2.0
```

Der Workflow **Release** prüft das Projekt, erstellt das ZIP und die SHA-256-Prüfsumme und legt anschließend einen **Release-Entwurf** an. Unter **Releases** den Entwurf ansehen und selbst veröffentlichen. Das Quellcode-ZIP enthält Starter und Quelldateien. Zusätzlich werden vier fertige App-Archive erstellt. Persönliche Medien, Verlauf und lokale Einstellungen sind ausgeschlossen.

Der Workflow verwendet das von GitHub automatisch bereitgestellte Repository-Token. Für normale Repositories ist kein zusätzlich angelegtes Secret erforderlich. Organisationsrichtlinien können Actions oder Schreibrechte einschränken; in diesem Fall die manuelle Variante verwenden.

### Manuell

```sh
python3 tools/package.py
```

Unter **Releases → Draft a new release** den Tag `v2.2.0` auswählen oder anlegen. `dist/Frame-v2.2.0.zip` und `dist/Frame-v2.2.0.zip.sha256` anhängen, Änderungen aus `CHANGELOG.md` übernehmen und veröffentlichen.

## Repository-Seite verständlich machen

Vorschlag für **About / Description**:

> Lokaler YouTube-Downloader für Video und Audio. MP4, MKV, WebM, MP3, M4A, Opus, WAV und FLAC mit einer klaren Dark-Oberfläche.

Passende **Topics**: `youtube-downloader`, `yt-dlp`, `python`, `audio`, `video`, `local-first`.

Die README enthält bereits eine Übersicht, Schnellstart und Formatvergleich. Nutzer sollten im Projektordner selbst starten und brauchen keinen Zugang zu deinem Rechner.

## Was lokal bleibt

- Deine heruntergeladenen Medien und der Verlauf in `downloads/`.
- Die Python-Umgebung unter `.runtime/` oder `.venv/`.
- `frame.local.json`, `.env`-Dateien, Caches und lokale Protokolle.
- Der `.git`-Ordner gehört zum lokalen Repository, wird aber nicht als Projektinhalt hochgeladen.

Die MIT-Lizenz ist als übliche Open-Source-Lizenz vorbereitet. Für den ursprünglichen Frame-Code gilt sie, für separat installierte Werkzeuge deren jeweilige Lizenz. Änderungen an der gewünschten Projektlizenz vor der ersten öffentlichen Veröffentlichung vornehmen.

## Hosting

Die Bedienoberfläche wird vom lokalen Python-Dienst ausgeliefert. GitHub ist hier der Ort für Quellcode und Downloads. **GitHub Pages allein genügt nicht**, da dort yt-dlp und FFmpeg nicht als Serverprozesse laufen. Die Anwendung ist bewusst auf lokale Nutzung begrenzt; sie öffnet keinen öffentlichen Download-Dienst.
