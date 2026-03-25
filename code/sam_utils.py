# ======================================
# Auteur : Alexandre Guyot
# Date : 2026-03-25
# Description : Automask - sam
# ======================================

import os
import numpy as np
import cv2
import time
import logging

# Récupère le logger
logger = logging.getLogger("Automask")

# Tentative import SAM
try:
    import torch
    from segment_anything import sam_model_registry, SamPredictor
    SAM_AVAILABLE = True
except Exception as e:
    logger.error(f"SAM non disponible (impossible de charger les librairies torch ou segment_anything): ", e)
    SAM_AVAILABLE = False

SAM_PREDICTOR = None
SAM_DEVICE = None

def init_sam(model_type, checkpoint):
    """
    Initialise le modèle SAM de manière isolée.
    Charge le checkpoint si trouvé.
    """
    global SAM_PREDICTOR, SAM_DEVICE

    if not SAM_AVAILABLE:
        logger.error(f"SAM non disponible (impossible de charger les librairies torch ou segment_anything): ", e)
        return False

    # Choix device
    SAM_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    if not os.path.isfile(checkpoint):
        logger.error(f"Le fichier Checkpoint '{checkpoint}' n'a pas été trouvé")
        return False

    try:
        logger.info(f"Chargement du modèle SAM {model_type} sur {SAM_DEVICE}...")
        model = sam_model_registry[model_type](checkpoint=checkpoint)
        model.to(device=SAM_DEVICE)
        SAM_PREDICTOR = SamPredictor(model)
        logger.info("Modèle SAM chargé avec succès")
        return True
    except Exception as e:
        logger.error(f"Impossible de charger le modèle SAM: ", e)
        return False


def run_sam(image_path, csv_path):
    """
    Exécute prédiction SAM.
    Retourne un mask (H,W) booléen ou None en cas d'échec.
    """
    global SAM_PREDICTOR

    if SAM_PREDICTOR is None:
        logger.error("SAM indisponible.")
        return None

    # load image
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        logger.warning(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t impossible de charger le fichier image ({image_path})")
        return None

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # load points
    if not os.path.exists(csv_path):
        logger.warning(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t impossible de charger le fichier annotation ({csv_path})")
        return None

    points = np.genfromtxt(
        csv_path,
        delimiter=',',
        dtype=int,
        encoding='utf-8'
    )

    if points.size == 0:
        logger.warning(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t aucun point dans le fichier annotation")
        logger.warning(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t aucun masque calculé")
        return None

    if points.ndim == 1:
        points = points[np.newaxis, :]

    try:
        logger.info(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t calcul du masque en cours ...")
        start_time = time.time()
        SAM_PREDICTOR.set_image(img_rgb)

        masks, scores, _ = SAM_PREDICTOR.predict(
            point_coords=points.astype(float),
            point_labels=np.ones(len(points), dtype=int),
            multimask_output=False
        )
        elapsed_time = time.time() - start_time
        logger.info(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t masque calculé (en {elapsed_time:.2f}s)")
        return masks[0], scores[0] # (H,W)

    except Exception as e:
        logger.error(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t erreur lors de la prédiction. Aucun masque calculé")
        return None
