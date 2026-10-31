#!/usr/bin/env bash
# Compile un exécutable autonome pour le système courant (Linux ou macOS).
# Windows : utiliser build.bat.
# PyInstaller ne fait pas de compilation croisée : un binaire Windows doit être
# produit sous Windows, un binaire macOS sous macOS (voir .github/workflows/).
set -euo pipefail
cd "$(dirname "$0")"

VENV=".build-venv"
PYTHON="${PYTHON:-python3}"

if [ ! -d "$VENV" ]; then
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
. "$VENV/bin/activate"

python -m pip install --quiet --upgrade pip
python -m pip install --quiet --upgrade pyinstaller psutil

rm -rf build dist

case "$(uname -s)" in
  Darwin)
    ICONE="--icon assets/logo.icns"
    ;;
  *)
    ICONE=""                        # Linux : l'icône vient du .desktop, pas du binaire
    ;;
esac

# Variables volontairement non quotées : elles contiennent des options.
# shellcheck disable=SC2086
python -m PyInstaller --noconfirm --clean --onefile --windowed \
  --name TaxeGigabit $ICONE \
  --add-data assets/logo.png:assets taxe_gigabit.py

case "$(uname -s)" in
  Darwin)
    if [ -d dist/TaxeGigabit.app ]; then
      ditto -c -k --keepParent dist/TaxeGigabit.app \
        "dist/TaxeGigabit-macos-$(uname -m).zip"
    fi
    ;;
  *)
    tar -czf "dist/TaxeGigabit-linux-$(uname -m).tar.gz" -C dist TaxeGigabit
    ;;
esac

echo
echo "Artefacts :"
ls -lh dist
