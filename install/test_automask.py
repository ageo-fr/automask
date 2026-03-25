# ======================================
# Auteur : Alexandre Guyot
# Date : 2026-03-25
# Description : Automask - test install
# ======================================

import importlib
import sys
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtCore import QTimer


errors = []


def check_package(import_name, display_name=None, version_attr="__version__"):
    global errors
    display_name = display_name or import_name
    try:
        module = importlib.import_module(import_name)
        version = getattr(module, version_attr, "Version inconnue")
        print(f"[OK] {display_name} : {version}")
        return module
    except Exception as e:
        print(f"[ERREUR] {display_name} : {e}")
        errors.append(display_name)
        return None


print("===== TEST ENVIRONNEMENT AUTOMASK =====")
print(f"Python : {sys.version}")
print("-" * 50)

# Packages principaux
check_package("numpy")
check_package("scipy")
check_package("cv2", "opencv-python-headless")
check_package("PyQt5")
check_package("markdown")

print("-" * 50)

# Torch
torch = check_package("torch")
if torch:
    print(f"CUDA compilé avec : {torch.version.cuda}")
    print(f"CUDA disponible : {torch.cuda.is_available()}")
    print(f"Nombre de GPU : {torch.cuda.device_count()}")
    if torch.cuda.is_available():
        print(f"GPU : {torch.cuda.get_device_name(0)}")

print("-" * 50)

check_package("torchvision")

print("-" * 50)

# SAM
sam = check_package("segment_anything")
if sam:
    try:
        from segment_anything import sam_model_registry
        print("[OK] SAM registry accessible")
    except Exception as e:
        print(f"[ERREUR] SAM registry : {e}")
        errors.append("segment_anything registry")

print("-" * 50)

# -------------------- Qt TEST WINDOW --------------------

app = QApplication(sys.argv)

window = QWidget()
layout = QVBoxLayout()

if errors:
    message = "TEST ERREUR:\n" + "\n".join(errors)
else:
    message = "TEST OK\nFermeture automatique dans 2 secondes"

try :

    label = QLabel(message)
    layout.addWidget(label)
    window.setLayout(layout)
    window.setWindowTitle("Test Environnement Automask")
    window.resize(400, 150)
    window.show()

    # Fermeture automatique après 10 secondes
    QTimer.singleShot(2000, app.quit)

    print(f"[OK] Affichage QT")

except:
    print(f"[ERREUR] Affichage QT")

print("===== FIN DU TEST  =====")

sys.exit(app.exec_())
