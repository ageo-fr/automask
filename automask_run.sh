#!/usr/bin/env bash
set -e
export LANG=C.UTF-8

echo
echo "========================================"
echo "  AUTOMASK"
echo
echo "  Automask est un outil de segmentation d'images"
echo "  développé par AGEO avec le soutien du SRA Bretagne."
echo "========================================"
echo

# -------------------- Se placer dans le dossier du script --------------------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT_DIR="$SCRIPT_DIR"
cd "$ROOT_DIR"

# -------------------- Chemins --------------------
VENV_DIR="$ROOT_DIR/venv"
PYTHON_EXE="$VENV_DIR/bin/python"

# -------------------- Vérifications --------------------
if [ ! -f "$PYTHON_EXE" ]; then
    echo "Erreur : environnement Python introuvable."
    echo "Chemin attendu : $PYTHON_EXE"
    echo "Veuillez lancer install.py"
    exit 1
fi

# -------------------- Lancer Automask --------------------
echo "Lancement d'AutoMask..."
echo "(veuillez patienter quelques secondes)"
"$PYTHON_EXE" "$ROOT_DIR/code/automask.py"
echo "... Fermeture d'AutoMask."
echo
read -p "Appuyez sur [Entrée] pour fermer..."
