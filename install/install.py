# ======================================
# Auteur : Alexandre Guyot
# Date : 2026-03-25
# Description : Automask - install
# ======================================

import sys
import os
import subprocess
import shutil
import urllib.request
from urllib.parse import urlparse
import zipfile
from pathlib import Path

# -------------------- CONFIG --------------------
ROOT = Path(__file__).parent.parent
VENV_DIR = ROOT / "venv"
LOGS_DIR = ROOT / "logs"
MODELS_DIR = ROOT / "models"
TOOLS_DIR = ROOT / "tools"
MODELS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
VENV_DIR.mkdir(exist_ok=True)

MODEL_URL = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth"

# -------------------- HELPERS --------------------
def has_gpu():
    try:
        result = subprocess.run(["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def ensure_venv(venv_path):
    python_exec = os.path.join(venv_path, "Scripts" if sys.platform.startswith("win") else "bin", "python")
    if os.path.exists(python_exec):
        return python_exec
    print(f"\n\n[INFO] Création du venv : {venv_path}")
    subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
    return python_exec


def ensure_model():
    parsed_url = urlparse(MODEL_URL)
    model_file = os.path.basename(parsed_url.path)
    model_path = os.path.join(MODELS_DIR, model_file)
    print(f"\n\n[INFO] Préparation du modèle {model_file}")
    if os.path.exists(model_path):  # fonction os.path.exists()
        print(f"\tInfo : Modèle '{model_file}' déjà présent")
        return

    print(f"\tInfo : Téléchargement du modèle '{model_file}'")

    with urllib.request.urlopen(MODEL_URL) as response:
        total = response.getheader("Content-Length")
        total = int(total) if total else None

        downloaded = 0
        with open(model_path, "wb") as f:
            while True:
                chunk = response.read(1024*1024)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                if total:
                    percent = downloaded / total * 100
                    sys.stdout.write(f"\r {percent:3.0f}%")
                else:
                    sys.stdout.write(f"\r {downloaded//1024//1024} MB")
                sys.stdout.flush()
    print("\nInfo : Téléchargement du modèle terminé")

# -------------------- MAIN --------------------
def main():
    print(f"===== Installation Automask =====")
    # OS et GPU
    os_type = "win" if sys.platform.startswith("win") else "linux"
    gpu_type = "gpu" if has_gpu() else "cpu"
    req_file = os.path.join(os.path.dirname(__file__), f"requirements.txt")
    print(f"\n[INFO] OS={os_type}, Processing unit={gpu_type}, requirements={req_file}")

    # venv
    python_exec = ensure_venv(VENV_DIR)
    pip_exec = os.path.join(os.path.dirname(python_exec), "pip.exe" if os_type=="win" else "pip")
    env = os.environ.copy()

    # PIP + MAJ Certificate
    print("\n\n[[INFO] Mise à jour de pip et des certificats SSL")
    try:
        subprocess.run([python_exec, "-m", "pip", "install", "--upgrade", "pip"], check=True, env=env)
        subprocess.run([pip_exec, "install", "--upgrade", "certifi"], check=True, env=env)
    except Exception as e:
        print("\n\n[[ERREUR] Erreur lors de la mise à jour de pip ou des certificats SSL")
        print(e)
        sys.exit()


    # Installer dependencies
    print("\n\n[[INFO] Installation des dépendances standard")
    try:
        subprocess.run([pip_exec, "install", "-r", req_file], check=True, env=env)
    except Exception as e:
        print("\n\n[[ERREUR] Erreur lors de l'installation des dépendances")
        print(e)
        sys.exit()

    # Installer dependencies pytorch
    print("\n\n[[INFO] Installation des dépendances pytorch")
    if gpu_type == 'gpu':
        print("[INFO] GPU détecté")
        try:
            subprocess.run(
                [
                    pip_exec,
                    "install",
                    "torch",
                    "torchvision",
                    "--index-url",
                    "https://download.pytorch.org/whl/cu118"
                ],
                check=True,
                env=env
            )
        except Exception as e:
            print("\n\n[[ERREUR] Erreur lors de l'installation des dépendances pytorch")
            print(e)
            sys.exit()
    if gpu_type == 'cpu':
        print("\n\n[[INFO] GPU non détecté / CPU fallback")
        try:
            subprocess.run(
                [
                    pip_exec,
                    "install",
                    "torch",
                    "torchvision",
                    "--index-url",
                    "https://download.pytorch.org/whl/cpu"
                ],
                check=True,
                env=env
            )
        except Exception as e:
            print("\n\n[[ERREUR] Erreur lors de l'installation des dépendances pytorch")
            print(e)
            sys.exit()

    # Installer SAM depuis Git
    print("\n\n[[INFO] Installation de Segment Anything (SAM)...")
    try:
        #subprocess.run([pip_exec, "install", "git+https://github.com/facebookresearch/segment-anything.git"], check=True, env=env)
        subprocess.run([pip_exec, "install", "https://github.com/facebookresearch/segment-anything/archive/refs/heads/main.zip"], check=True, env=env)
    except Exception as e:
        print("\n\n[[ERREUR] Erreur lors de l'installation de Segment Anything (SAM)")
        print(e)
        sys.exit()

    # Téléchargement modèle
    print("\n\n[[INFO] Téléchargement du modèle SAM ...")
    try:
        ensure_model()
    except Exception as e:
        print("\n\n[[ERREUR] Erreur lors du télchargement du modèle")
        print(e)
        sys.exit()

    print("\n\n[[INFO] Vérification des prérequis ...")
    try:
        # chemin vers le script test
        script_path = os.path.join("install", "test_automask.py")
        subprocess.run([python_exec, script_path], check=True)
    except Exception as e:
        print("\n\n[[ERREUR] Erreur lors de la vérification des prérequis")
        print("[ERREUR] Echec de l'installation -> vérifier les message d'erreur et contacter le support")
        print(e)
        sys.exit()

if __name__ == "__main__":
    main()
