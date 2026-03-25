# ======================================
# Auteur : Alexandre Guyot
# Date : 2026-03-25
# Description : Automask - mask tools
# ======================================

import os
import cv2
import numpy as np
from scipy import ndimage
from sam_utils import run_sam
import logging

# Récupère le logger
logger = logging.getLogger("Automask")

def compute_and_save_mask(image_path, csv_path, out_path, postfilter=None):
    """
    Appelle SAM via run_sam() et sauvegarde le mask PNG.
    Retourne True/False selon succès.
    """
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        logger.warning(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t Aucune annotation trouvée (calcul de masque non-effectué)")
        return None, None

    mask, score_sam = run_sam(image_path, csv_path)
    if score_sam > 1:
        score_sam = 1
    score_morpho = compacity_score(mask)
    score_final = np.mean([score_sam, score_morpho])

    logger.info(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t score de prédiction/morphologie : {score_sam:.2f}/{score_morpho:.2f}")
    logger.info(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t score final {score_final:.2f}")

    if mask is None:
        return None, None

    if postfilter is not None:
        logger.info(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t post-filtering (< {postfilter}px)...")
        mask = postfilter_mask(mask, postfilter)

    # mask → uint8
    mask_u8 = (mask.astype(np.uint8) * 255)

    try:
        cv2.imwrite(out_path, mask_u8)
        logger.info(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t Masque sauvegardé sous {out_path}")
        return mask, score_final
    except Exception as e:
        logger.error(f"[{os.path.splitext(os.path.basename(image_path))[0]}]\t Erreur lors du calcul ou sauvegarde du masque")
        return None, None

def postfilter_mask(mask, min_size):
    """
    Supprime toutes les régions (amas) de pixels 0 ou 1
    dont la taille est < min_size.

    mask : tableau numpy binaire 0/1
    min_size : seuil minimum en pixels
    """
    out = mask.copy()

    # ---- traiter les régions de 1 ----
    labeled, num = ndimage.label(out == 1)
    sizes = ndimage.sum(np.ones_like(out), labeled, range(1, num+1))

    for lbl, size in enumerate(sizes, start=1):
        if size < min_size:
            out[labeled == lbl] = 0   # les petites régions de 1 deviennent 0

    # ---- traiter les régions de 0 ----
    labeled, num = ndimage.label(out == 0)
    sizes = ndimage.sum(np.ones_like(out), labeled, range(1, num+1))

    for lbl, size in enumerate(sizes, start=1):
        if size < min_size:
            out[labeled == lbl] = 1   # les petites régions de 0 deviennent 1

    return out

def compacity_score(binary):
    """
    Score de compacité 2D (0 = très bruité, 1 = 2 zones lisses)

    Principes :
      - Nombre de régions : peu de régions = mieux
      - Rugosité : bordures longues vs surface = moins compact → score plus bas
    """
    binary = binary.astype(bool)
    scores = []

    for mask in [binary, ~binary]:
        # --- Nombre de régions ---
        labeled, n_features = ndimage.label(mask)
        if n_features == 0:
            scores.append(1.0)
            continue

        # Score nombre de régions : 2 régions → 1, beaucoup de régions → proche 0
        num_score = 2 / (n_features + 1)

        # --- Rugosité / Compacité ---
        # Bordure : pixels True ayant au moins un voisin False
        kernel = np.ones((3, 3), dtype=int)
        kernel[1, 1] = 0
        neighbors = ndimage.convolve(mask.astype(int), kernel, mode='constant', cval=0)
        edge_pixels = mask & (neighbors < 8)
        perimeter = edge_pixels.sum()
        area = mask.sum()

        if perimeter == 0:
            smoothness_score = 1.0
        else:
            # Compacité ~ area / perimeter, normalisé pour rester dans [0,1]
            ratio = area / perimeter
            # Normalisation empirique : ratio > 0.1 → lisse
            smoothness_score = np.clip(ratio / 0.1, 0, 1)

        # Combinaison multiplicative
        scores.append(num_score * smoothness_score)

    # Moyenne True / False
    return float(np.mean(scores))


def invert_and_save_mask(mask_path):
    """
    Inverse un masque binaire 0/1 (PNG) et le sauvegarde au même chemin.

    mask_path : chemin du PNG à inverser
    Retourne True si succès, False sinon
    """
    if not os.path.exists(mask_path):
        logger.error(f"Masque introuvable : {mask_path}")
        return False

    # Lecture
    mask_img = cv2.imread(mask_path, cv2.IMREAD_UNCHANGED)
    if mask_img is None:
        logger.error(f"Impossible de charger le masque : {mask_path}")
        return False

    # Gestion des canaux
    if len(mask_img.shape) == 3:
        if mask_img.shape[2] == 4:
            # RGBA → utiliser le canal A pour l'alpha si nécessaire
            alpha = mask_img[:, :, 3]
            mask_gray = cv2.cvtColor(mask_img[:, :, :3], cv2.COLOR_BGR2GRAY)
        else:
            mask_gray = cv2.cvtColor(mask_img, cv2.COLOR_BGR2GRAY)
            alpha = None
    else:
        mask_gray = mask_img
        alpha = None

    # Convertir en binaire 0/1
    mask_bin = (mask_gray > 127).astype(np.uint8)

    # Inversion
    mask_inv = 1 - mask_bin

    # Reconvertir en uint8 0/255
    mask_u8 = mask_inv * 255

    # Ajouter l'alpha si existant
    if alpha is not None:
        mask_u8 = cv2.merge([mask_u8, mask_u8, mask_u8, alpha])

    # Sauvegarde
    try:
        cv2.imwrite(mask_path, mask_u8)
        return True
    except Exception as e:
        return False
