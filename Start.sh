#!/bin/sh
cd -- "$(dirname -- "$0")" || exit 1
for candidate in ./.runtime/bin/python python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    exec "$candidate" start.py "$@"
  fi
done
printf '%s\n' 'Bitte installiere Python 3.11+ von https://www.python.org/downloads/.'
exit 1
