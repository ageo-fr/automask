# ======================================
# Auteur : Alexandre Guyot
# Date : 2026-03-25
# Description : Automask - test install
# ======================================

import importlib
import sys

errors = []


def check_package(import_name, display_name=None, version_attr="__version__"):
    global errors
    display_name = display_name or import_name
    try:
        module = importlib.import_module(import_name)
        version = getattr(module, version_attr, "Version inconnue")
        print(f"[OK] {display_name} : {version}")
        return None
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
try:
    import torch
    print("[OK] Torch accessible")
    print(f"\tCUDA compilé avec : {torch.version.cuda}")
    print(f"\tCUDA disponible : {torch.cuda.is_available()}")
    print(f"\tNombre de GPU : {torch.cuda.device_count()}")
    if torch.cuda.is_available():
        print(f"\GPU : {torch.cuda.get_device_name(0)}")
except Exception as e:
    print(f"[ERREUR] Torch module : {e}")
    errors.append("torch module")

print("-" * 50)

# Torch vision
try:
    import torchvision
    print("[OK] Torchvision accessible")
except Exception as e:
    print(f"[ERREUR] Torchvision module : {e}")
    errors.append("torchvision module")

print("-" * 50)

# SAM
try:
    from segment_anything import sam_model_registry
    print("[OK] SAM registry accessible")
except Exception as e:
    print(f"[ERREUR] SAM registry : {e}")
    errors.append("segment_anything registry")

print("-" * 50)

# -------------------- Qt TEST WINDOW --------------------
try :
    from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
    from PyQt5.QtCore import QTimer
except Exception as e:
    print(f"[ERREUR] PyQT modules : {e}")
    errors.append("PyQT modules")


try :
    app = QApplication(sys.argv)

    window = QWidget()
    layout = QVBoxLayout()

    label = QLabel(message)
    layout.addWidget(label)
    window.setLayout(layout)
    window.setWindowTitle("Test Environnement Automask")
    window.resize(400, 150)
    window.show()

    # Fermeture automatique après 10 secondes
    QTimer.singleShot(2000, app.quit)
    sys.exit(app.exec_())
    print(f"[OK] Affichage QT")

except:
    print(f"[ERREUR] Affichage QT")

print("===== FIN DU TEST  =====")

sys.exit()
