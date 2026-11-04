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
