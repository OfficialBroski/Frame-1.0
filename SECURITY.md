# Sicherheit und Datenschutz

Frame ist eine persönliche lokale Anwendung. Der Dienst bindet ausschließlich an `127.0.0.1`. Andere Rechner im Netzwerk erhalten keinen Zugriff. Anfragen, die Downloads verändern, benötigen ein Sitzungstoken und bestehen Host- und Origin-Prüfungen. Dateidownloads sind auf den jeweiligen Auftragsordner begrenzt.

Frame liest keine Browser-Cookies und keine Zugangsdaten. Videoabrufe und Vorschaubilder gehen direkt an YouTube beziehungsweise dessen Medienserver. Frame sendet keine Telemetrie an einen eigenen Dienst.

`downloads/`, `.runtime/`, `frame.local.json` und Umgebungsdateien sind in `.gitignore` aufgeführt und werden vom Paketwerkzeug ausgeschlossen. Bitte diese Dateien nicht manuell zu Git hinzufügen. Der Verlauf kann Videotitel und Links enthalten.

## Problem melden

Falls im GitHub-Repository **Security → Report a vulnerability** aktiviert ist, nutze dort eine private Meldung. Falls die Funktion nicht aktiviert ist, eröffne zunächst ein Issue ohne vertrauliche Details und bitte um einen privaten Meldeweg. Keine Tokens, Browser-Cookies, privaten URLs oder persönlichen Verläufe öffentlich posten.

Unterstützt wird die aktuelle Version 2.x. Python-Abhängigkeiten können mit `python start.py --update` aktualisiert werden.
