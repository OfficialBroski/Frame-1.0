# Drittanbieter

Die MIT-Lizenz in diesem Repository gilt für den Frame-Anwendungscode. Externe Werkzeuge behalten ihre jeweiligen Lizenzen.

| Werkzeug | Zweck | Projekt / Lizenzhinweise |
| --- | --- | --- |
| yt-dlp | Videoabruf und Formatauswahl | [Projekt](https://github.com/yt-dlp/yt-dlp) · [Lizenz](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE) |
| yt-dlp-ejs | YouTube-Player-Verarbeitung | [Projekt](https://github.com/yt-dlp/ejs) |
| imageio-ffmpeg | Bereitstellung eines FFmpeg-Programms | [Projekt](https://github.com/imageio/imageio-ffmpeg) · enthält abhängig vom System ein separat lizenziertes FFmpeg-Binary |
| FFmpeg | Zusammenfügen und Audiokonvertierung | [Lizenzinformationen](https://ffmpeg.org/legal.html) |
| Python, Node.js / Deno | Laufzeitumgebungen | Werden vom Nutzer separat installiert. |

Das Release-ZIP enthält den Frame-Quellcode, keine kopierten Laufzeitumgebungen oder FFmpeg-Binaries. Der Starter bezieht Python-Abhängigkeiten beim ersten Start über PyPI. Die dabei installierten weiteren Bibliotheken behalten ebenfalls ihre eigenen Lizenzhinweise.

## Eigenständige Desktop-Ausgaben ab 2.2

- Python 3.12: Python Software Foundation License; Text unter `licenses/Python-LICENSE.txt`.
- PyInstaller-Bootloader: GPL mit Bootloader-Ausnahme zur Verteilung gebündelter Anwendungen; Lizenztext wird beigefügt.
- Node.js 24.22.2: MIT und die im offiziellen Node-Lizenztext aufgeführten Drittanbieter-Lizenzen; `licenses/Node.js-LICENSE.txt`.
- Lizenztexte der gebündelten Python-Laufzeitpakete liegen im App-Verzeichnis unter `licenses`.
- FFmpeg ist nicht Bestandteil des Frame-Release-Archivs. Beim ersten Start bezieht Frame die Plattformdatei aus imageio-ffmpeg 0.8.1 direkt vom PyPI-Verteiler des Projekts. Lizenz und Metadaten werden daneben gespeichert. FFmpeg und seine verwendeten Bibliotheken behalten ihre eigenen LGPL-/GPL-/sonstigen Lizenzbedingungen. Projekt: https://ffmpeg.org/ und https://github.com/imageio/imageio-ffmpeg.
