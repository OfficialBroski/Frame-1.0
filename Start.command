#!/bin/zsh
cd -- "${0:A:h}" || exit 1
for candidate in "./.runtime/bin/python" /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
    "$candidate" start.py "$@"
    result=$?
    if [ "$result" -ne 0 ]; then read '?Drücke Enter zum Schließen …'; fi
    exit "$result"
  fi
done
echo 'Frame kann noch nicht starten: Python 3.11 oder neuer fehlt.'
echo 'Installiere Python von https://www.python.org/downloads/macos/ und öffne danach Start.command erneut.'
read '?Drücke Enter zum Schließen …'
