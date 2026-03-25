# ======================================
# Auteur : Alexandre Guyot
# Date : 2026-03-25
# Description : Automask - main
# ======================================

import sys
import os
import configparser
import csv
from datetime import datetime
import torch # import avant open-cv et qt5 -> plus fiable

# Desactivate Warning GTK (Markdown)
os.environ["NO_AT_BRIDGE"] = "1"

# --- IMPORTS EXISTANTS ---
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QAction,
    QPushButton, QTreeWidget, QTreeWidgetItem, QFileDialog, QLineEdit,
    QDialog, QFormLayout, QLabel, QSplitter, QCheckBox, QProgressBar, QFrame, QGroupBox, QShortcut, QMessageBox, QSpinBox, QPlainTextEdit, QToolTip
)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QBrush, QIcon, QImage, qRgb, QKeySequence
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QThread, QTimer

import cv2 # à importer après PyQt5
import numpy as np

from mask_tools import compute_and_save_mask, invert_and_save_mask
from sam_utils import init_sam, SAM_PREDICTOR

from logging_config import setup_logging, QPlainTextEditLogger
from help.help_dialog import HelpDialog


# ======================================================================
# ===============  SETTINGS DIALOG  ====================================
# ======================================================================

class SettingsDialog(QDialog):
    def __init__(self, images_dir, annotations_dir, masks_dir, ask_on_start):
        super().__init__()
        self.setWindowTitle("Paramètres des dossiers")
        layout = QFormLayout(self)
        self.img_edit = QLineEdit(images_dir)
        self.ann_edit = QLineEdit(annotations_dir)
        self.mask_edit = QLineEdit(masks_dir)
        self.img_browse = QPushButton("...")
        self.ann_browse = QPushButton("...")
        self.mask_browse = QPushButton("...")
        self.img_browse.clicked.connect(lambda: self.browse_dir(self.img_edit))
        self.ann_browse.clicked.connect(lambda: self.browse_dir(self.ann_edit))
        self.mask_browse.clicked.connect(lambda: self.browse_dir(self.mask_edit))
        row_img = QHBoxLayout(); row_img.addWidget(self.img_edit); row_img.addWidget(self.img_browse)
        row_ann = QHBoxLayout(); row_ann.addWidget(self.ann_edit); row_ann.addWidget(self.ann_browse)
        row_mask = QHBoxLayout(); row_mask.addWidget(self.mask_edit); row_mask.addWidget(self.mask_browse)
        layout.addRow("Dossier images :", row_img)
        layout.addRow("Dossier annotations :", row_ann)
        layout.addRow("Dossier masques :", row_mask)
        self.chk_startup = QCheckBox("Ne plus ouvrir au démarrage")
        self.chk_startup.setChecked(not ask_on_start)
        self.setMinimumWidth(500)
        layout.addRow(self.chk_startup)
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)

    def browse_dir(self, lineedit):
        d = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier", lineedit.text())
        if d: lineedit.setText(d)

    def get_paths(self):
        return self.img_edit.text(), self.ann_edit.text(), self.mask_edit.text()

    def get_ask_on_start(self):
        return not self.chk_startup.isChecked()
# ======================================================================
# =======================  IMAGE VIEWER  ================================
# ======================================================================

class ImageViewer(QWidget):
    points_changed = pyqtSignal()

    def __init__(self, logger, parent=None):
        super().__init__(parent)
        self.logger = logger  # le logger centralisé
        self.image = None
        self.current_image_name = None
        self.points = []
        self.mask = None
        self.show_mask = False
        self.offset = QPoint(0, 0)
        self.last_pos = None
        self.zoom = 1.0
        self.auto_fit = True
        self.setMinimumSize(400, 300)

    def load_image(self, path):
        self.image = QPixmap(path)
        self.current_image_name = os.path.splitext(os.path.basename(path))[0]
        self.points = []
        self.mask = None
        self.offset = QPoint(0, 0)
        if self.image:
            w_ratio = self.width() / self.image.width()
            h_ratio = self.height() / self.image.height()
            self.zoom = min(w_ratio, h_ratio, 1.0)
            self.auto_fit = True
        self.logger.info(f"[{self.current_image_name}]\t chargement image")
        self.update()

    def resizeEvent(self, event):
        if self.auto_fit and self.image:
            w_ratio = self.width() / self.image.width()
            h_ratio = self.height() / self.image.height()
            self.zoom = min(w_ratio, h_ratio, 1.0)
            self.update()
        super().resizeEvent(event)

    def load_points(self, points):
        self.points = [QPoint(p[0], p[1]) for p in points]
        self.points_changed.emit()
        self.logger.info(f"[{self.current_image_name}]\t chargement CSV ({len(points)} point(s)")
        self.update()

    def load_mask(self, mask_path):
        mask_pix = QPixmap(mask_path)
        img = mask_pix.toImage().convertToFormat(QImage.Format_ARGB32)
        mask = img.createMaskFromColor(qRgb(255, 255, 255), Qt.MaskOutColor)
        img.setAlphaChannel(mask)
        self.mask = QPixmap.fromImage(img)
        self.update()

    def toggle_mask(self):
        self.show_mask = not self.show_mask
        self.update()

    def reload_mask(self, mask_path):
        """Recharge le masque depuis le disque"""
        if os.path.exists(mask_path):
            self.load_mask(mask_path)
        else:
            self.mask = None
        self.update()

    def clear_points(self):
        if self.points:
            self.points = []
            self.points_changed.emit()
            self.logger.info(f"[{self.current_image_name}]\t suppression des points")
            self.update()

    def remove_last_point(self):
        if self.points:
            self.points.pop()
            self.points_changed.emit()
            self.logger.info(f"[{self.current_image_name}]\t suppression du dernier point")
            self.update()

    def add_point(self, x, y):
        self.points.append(QPoint(int(x), int(y)))
        self.points_changed.emit()
        self.logger.info(f"[{self.current_image_name}]\t ajout point ({x:.2f}, {y:.2f})")
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.image:
            # Calculer la position du clic par rapport à l'image (en tenant compte du zoom et de l'offset)
            img_x = (event.pos().x() - self.offset.x()) / self.zoom
            img_y = (event.pos().y() - self.offset.y()) / self.zoom

            # Vérifier si le clic est à l'intérieur des limites de l'image
            if 0 <= img_x < self.image.width() and 0 <= img_y < self.image.height():
                self.add_point(img_x, img_y)

            else:
                # Optionnel : Afficher un message ou un feedback visuel pour indiquer que le clic est hors de l'image
                self.logger.info(f"[{self.current_image_name}]\t clic hors de l'image / point non ajouté.")

        elif event.button() == Qt.RightButton:
            self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.RightButton and self.last_pos:
            delta = event.pos() - self.last_pos
            self.offset += delta
            self.last_pos = event.pos()
            self.auto_fit = False
            self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120
        self.zoom = max(0.1, self.zoom + delta * 0.1)
        self.auto_fit = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        if self.image:
            iw = int(self.image.width() * self.zoom)
            ih = int(self.image.height() * self.zoom)
            scaled = self.image.scaled(iw, ih, Qt.KeepAspectRatio)
            painter.drawPixmap(self.offset, scaled)

        if self.show_mask and self.mask:
            iw = int(self.mask.width() * self.zoom)
            ih = int(self.mask.height() * self.zoom)
            painter.setOpacity(0.80)
            scaled_mask = self.mask.scaled(iw, ih, Qt.KeepAspectRatio)
            painter.drawPixmap(self.offset, scaled_mask)

        painter.setPen(QPen(QColor(0, 255, 0), 8))
        painter.setBrush(QBrush(QColor(0, 255, 0)))
        size = 6
        for p in self.points:
            px = int(p.x() * self.zoom + self.offset.x())
            py = int(p.y() * self.zoom + self.offset.y())
            painter.drawEllipse(px - size // 2, py - size // 2, size, size)

        # ===============================
        # Overlay nom du fichier
        # ===============================
        if self.current_image_name:
            painter.setRenderHint(QPainter.Antialiasing)

            text = self.current_image_name

            font = painter.font()
            font.setPointSize(18)
            font.setBold(True)
            painter.setFont(font)

            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(text)
            text_height = metrics.height()

            margin = 15
            x = self.width() - text_width - margin
            y_top = margin

            # Fond
            bg_rect = (
                x - 10,
                y_top - 5,
                text_width + 20,
                text_height + 10
            )

            painter.setBrush(QColor(255, 255, 255, 80))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(*bg_rect, 8, 8)

            # Texte centré verticalement
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(
                bg_rect[0] + 10,  # x : marge interne
                bg_rect[1],  # y : coin supérieur
                bg_rect[2],  # largeur
                bg_rect[3],  # hauteur
                Qt.AlignVCenter | Qt.AlignLeft,
                text
            )


# ======================================================================
# ===============  GESTION TRI      ====================================
# ======================================================================

class TreeItem(QTreeWidgetItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.score = None  # stocke le score (float ou None)

    def set_score(self, value):
        """Met à jour le score et affiche dans la 4ème colonne"""
        self.score = value
        self.setText(3, f"{value:.2f}" if value is not None else "")

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()

        # Annot. / Mask : tri logique
        if column in (1, 2):
            a = self.data(column, Qt.ItemDataRole.UserRole)
            b = other.data(column, Qt.ItemDataRole.UserRole)
            return a < b

        # Score : tri numérique
        if column == 3:
            a = self.score if self.score is not None else -1
            b = other.score if other.score is not None else -1
            return a < b

        # Image : tri alphabétique
        return self.text(column) < other.text(column)

# ======================================================================
# ========================= BATCH THREAD ================================
# ======================================================================

class BatchThread(QThread):
    progress = pyqtSignal(int)
    file_done = pyqtSignal(int, int)
    finished = pyqtSignal()
    score = pyqtSignal(str, object)
    stopped = False

    def __init__(self, file_list, images_dir, annotations_dir, masks_dir, overwrite, postfilter):
        super().__init__()
        self.file_list = file_list
        self.images_dir = images_dir
        self.annotations_dir = annotations_dir
        self.masks_dir = masks_dir
        self.overwrite = overwrite
        self.stopped = False
        self.postfilter = postfilter

    def run(self):
        total = len(self.file_list)
        for idx, fname in enumerate(self.file_list):
            if self.stopped:
                break

            base = os.path.splitext(fname)[0]
            img_path  = os.path.join(self.images_dir, fname)
            csv_path  = os.path.join(self.annotations_dir, base + "_points.csv")
            mask_path = os.path.join(self.masks_dir, base + "_mask.png")

            # Appel SAM
            mask, score = compute_and_save_mask(img_path, csv_path, mask_path, postfilter=self.postfilter)


            # Mettre à jour
            self.score.emit(fname, score)
            self.progress.emit(int((idx+1) / total * 100))
            self.file_done.emit(idx + 1, total)  # <-- envoie X/N

        self.finished.emit()

    def stop(self):
        self.stopped = True

# ======================================================================
# ====================  SAM ===============================
# ======================================================================

class SamInitThread(QThread):
    finished_init = pyqtSignal(bool, str)

    def __init__(self, model_type, checkpoint):
        super().__init__()
        self.model_type = model_type
        self.checkpoint = checkpoint

    def run(self):
        ok = init_sam(self.model_type, self.checkpoint)
        self.finished_init.emit(ok, "")


# ======================================================================
# ====================  MAIN WINDOW (GUI) ===============================
# ======================================================================

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automask - Outils de segmentation automatique d'image")
        self.config_path = "settings.ini"

        # Crée le log avant l'UI
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setVisible(True)
        self.logger = setup_logging(self.log_text)  # Logger centralisé
        self.images_dir = None
        self.annotations_dir = None
        self.masks_dir = None
        self.sam_model = None
        self.sam_checkpoint = None
        self.load_config()
        self._updating_selection = False  # Flag pour éviter les rappels inutiles
        self._last_selected_item = None  # Pour suivre l'élément actuellement sélectionné

        for d in (self.images_dir, self.annotations_dir, self.masks_dir):
            os.makedirs(d, exist_ok=True)

        self.scores = {}  # initialise le dictionnaire des scores
        self.load_scores()


        self.init_ui()
        self.init_shortcuts()
        self.populate_list()

        # Ouvrir paramètres au démarrage si activé
        QTimer.singleShot(100, self.maybe_open_settings)

        #print("Initializing SAM backend...")
        #init_sam(model_type=self.sam_model, checkpoint=self.sam_checkpoint)
        self.sam_ready = False
        self.start_sam_backend()


        self._ignore_point_changes = False
        self.btn_stop.setEnabled(False)

    # -----------------------------
    def maybe_open_settings(self):
        if getattr(self, "ask_on_start", True):
            self.open_settings()

    def load_config(self):
        config = configparser.ConfigParser()
        if os.path.exists("settings.ini"):
            config.read("settings.ini")
            self.images_dir = config.get('paths',
                                         'images', fallback='images')
            self.annotations_dir = config.get('paths',
                                              'annotations', fallback='annotations')
            self.masks_dir = config.get('paths',
                                        'masks', fallback='masks')
            self.ask_on_start = config.getboolean('paths',
                                        'ask_on_start', fallback=True)
            self.sam_model = config.get('model',
                                        'sam_model', fallback='sam_model')
            self.sam_checkpoint = config.get('model',
                                        'sam_checkpoint', fallback='sam_checkpoint')

        else:
            self.logger.error("Le fichier de paramétrage settings.ini n'a pas été trouvé")
            print ("Le fichier de paramétrage settings.ini n'a pas été trouvé")
            sys.exit()

        self.logger.info("")
        self.logger.info("Configuration Automask : ")
        self.logger.info(f"\t Dossier images : {self.images_dir}")
        self.logger.info(f"\t Dossier masques : {self.masks_dir}")
        self.logger.info(f"\t Dossier annotations : {self.annotations_dir}")
        self.logger.info(f"\t Modele SAM : {self.sam_model} ({self.sam_checkpoint})")
        self.logger.info("")

    def save_config(self):
        config = configparser.ConfigParser()
        config['paths'] = {
            'images': self.images_dir,
            'annotations': self.annotations_dir,
            'masks': self.masks_dir,
            'ask_on_start': str(self.ask_on_start)
        }
        config['model'] = {
            'sam_model': self.sam_model,
            'sam_checkpoint': self.sam_checkpoint
        }
        with open(self.config_path, 'w') as f:
            config.write(f)

    # -----------------------------
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)  # Layout horizontal principal
        splitter = QSplitter(Qt.Horizontal)  # Splitter principal

        # ---- Left panel (buttons + tree)
        left_panel = QSplitter(Qt.Vertical)
        left_panel.setHandleWidth(5)

        # ---- Top buttons panel
        top_panel = QWidget()
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(2, 2, 2, 2)
        top_layout.setSpacing(5)

        # Navigation
        nav_group = QGroupBox("Navigation")
        nav_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        self.btn_prev = QPushButton("Image préc.️")
        self.btn_next = QPushButton("Image suiv.")
        row1.addWidget(self.btn_prev)
        row1.addWidget(self.btn_next)

        row2 = QHBoxLayout()
        self.btn_zoom_reset = QPushButton("Reset zoom")
        self.btn_refresh_list = QPushButton("Rafraichir liste")
        row2.addWidget(self.btn_zoom_reset)
        row2.addWidget(self.btn_refresh_list)

        nav_layout.addLayout(row1)
        nav_layout.addLayout(row2)
        nav_group.setLayout(nav_layout)
        top_layout.addWidget(nav_group)

        # Annotation
        anno_group = QGroupBox("Annotation")
        anno_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        self.btn_del_last = QPushButton("Annuler dernier point (ctrl+Z)")
        self.btn_clear = QPushButton("Supprimer tous les points (ctrl+x)")
        row1.addWidget(self.btn_del_last)
        row1.addWidget(self.btn_clear)

        anno_layout.addLayout(row1)
        anno_group.setLayout(anno_layout)
        top_layout.addWidget(anno_group)

        # --- Mask Group ---
        mask_group = QGroupBox("Segmentation / Masque automatique")
        mask_layout = QVBoxLayout()

        # Ligne 1 : Calcul masque + filtrage
        row1 = QHBoxLayout()
        self.btn_mask_calc = QPushButton("Calculer masque\n(Ctrl+Entrée)")
        self.btn_mask_calc.setMinimumHeight(40)
        self.btn_mask_calc.setStyleSheet("""
        QPushButton {
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #45A049;
        }
        QPushButton:disabled {
            background-color: #888888;
            color: #dddddd;
        }
        """)

        row1.addWidget(self.btn_mask_calc)
        self.filter_checkbox = QCheckBox("Filtrage (suppression zones < ...)")
        self.filter_window = QSpinBox()
        self.filter_window.setRange(1, 1000000)
        self.filter_window.setValue(10000)
        row1.addWidget(self.filter_checkbox)
        row1.addWidget(self.filter_window)
        self.filter_window.setSuffix(" px")
        mask_layout.addLayout(row1)

        # Ligne 2 : Inverser masque + affichage masque
        row2 = QHBoxLayout()
        self.btn_mask_invert = QPushButton("Inverser masque (Ctrl+I)")
        self.btn_mask_toggle = QPushButton("Affichage masque (espace)️")
        self.btn_mask_toggle.setCheckable(True)
        self.btn_mask_toggle.setChecked(False)
        row2.addWidget(self.btn_mask_toggle)
        row2.addWidget(self.btn_mask_invert)
        self.batch_checkbox = QCheckBox("Ecraser résultat (si existant)")
        row2.addWidget(self.batch_checkbox)
        mask_layout.addLayout(row2)

        # Ligne 3 : Supprimer masque
        row3 = QHBoxLayout()
        self.btn_mask_del = QPushButton("Supprimer masque (Ctrl+D)")
        row3.addWidget(self.btn_mask_del)
        mask_layout.addLayout(row3)

        # Ligne 4 : Progression + Stop
        row4 = QHBoxLayout()
        self.batch_progress = QProgressBar()
        self.batch_progress.setMinimum(0)
        self.batch_progress.setMaximum(100)
        self.batch_progress.setTextVisible(True)
        self.batch_progress.setFormat("Idle")
        self.btn_stop = QPushButton("stop")
        self.btn_stop.setEnabled(False)
        row4.addWidget(self.batch_progress)
        row4.addWidget(self.btn_stop)
        mask_layout.addLayout(row4)

        mask_group.setLayout(mask_layout)
        top_layout.addWidget(mask_group)

        # ---- Tree
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Image", "Annot.", "Masque", "Score"])
        self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree_widget.setSortingEnabled(True)
        header = self.tree_widget.header()
        header.setSortIndicatorShown(True)  # Affiche la flèche de tri
        header.setSectionsClickable(True)  # Permet de cliquer sur les en-têtes pour trier

        # Fixer largeur colonnes
        self.tree_widget.setColumnWidth(0, 250)  # Image
        self.tree_widget.setColumnWidth(1, 150)  # Annot.
        self.tree_widget.setColumnWidth(2, 150)  # Mask
        self.tree_widget.setColumnWidth(3, 100)  # Score

        left_panel.addWidget(top_panel)
        left_panel.addWidget(self.tree_widget)
        splitter.addWidget(left_panel)

        # Splitter vertical pour ImageViewer + logs
        right_panel = QSplitter(Qt.Vertical)
        right_panel.setHandleWidth(5)

        # ImageViewer
        self.viewer = ImageViewer(logger=self.logger)
        right_panel.addWidget(self.viewer)

        # Bandeau logs
        right_panel.addWidget(self.log_text)
        # Activer menu contextuel (clear)
        self.log_text.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_text.customContextMenuRequested.connect(self.show_log_context_menu)

        # fixer la taille initiale
        right_panel.setSizes([600, 150])  # ImageViewer 600px, logs 150px

        # Ajoute le splitter droit au splitter horizontal principal
        splitter.addWidget(right_panel)

        # ---- Ajout du splitter au layout principal ----
        main_layout.addWidget(splitter)
        self.setCentralWidget(main_widget)

        # ---------- FIXER LARGEUR GAUCHE ET HAUTEUR TOP_PANEL ----------
        splitter.setSizes([300, 800])  # largeur gauche / droite
        left_panel.setSizes([50, 500])  # top_panel / tree

        # Overwrite mask
        self.skip_overwrite_confirmation = False
        self.compute_running = False

        # Connections
        self.btn_prev.clicked.connect(self.prev_image)
        self.btn_next.clicked.connect(self.next_image)
        self.btn_zoom_reset.clicked.connect(self.reset_zoom)
        self.btn_refresh_list.clicked.connect(self.populate_list)
        self.btn_del_last.clicked.connect(self.del_last_point)
        self.btn_clear.clicked.connect(self.clear_points)
        self.btn_mask_calc.clicked.connect(self.compute_mask)
        self.btn_mask_invert.clicked.connect(self.invert_mask)
        self.btn_mask_del.clicked.connect(self.delete_mask)
        self.btn_mask_toggle.clicked.connect(self.toggle_mask_checked)
        self.tree_widget.itemSelectionChanged.connect(self.on_select)
        self.viewer.points_changed.connect(self.auto_save_current)
        self.viewer.points_changed.connect(self.update_icons)
        self.btn_stop.clicked.connect(self.stop_compute)

        # ===== MENU BAR =====
        menubar = self.menuBar()

        menu_settings = menubar.addMenu("Configuration")
        action_settings = QAction("Préférences", self)
        action_settings.triggered.connect(self.open_settings)
        menu_settings.addAction(action_settings)

        menu_aide = menubar.addMenu("Aide")

        action_apropos = QAction("À propos", self)
        action_apropos.setToolTip("Informations sur Automask")
        action_apropos.triggered.connect(self.show_about)

        action_shortcuts = QAction("Raccourcis clavier", self)
        action_shortcuts.setToolTip("Liste des raccourcis disponibles")
        action_shortcuts.triggered.connect(self.show_shortcuts)

        action_doc = QAction("Documentation", self)
        action_doc.setToolTip("Ouvrir la documentation utilisateur")
        action_doc.triggered.connect(self.open_documentation)

        menu_aide.addAction(action_shortcuts)
        menu_aide.addSeparator()
        menu_aide.addAction(action_doc)
        menu_aide.addSeparator()
        menu_aide.addAction(action_apropos)


    # -----------------------------
    def init_shortcuts(self):
        for key in (Qt.Key_Left, Qt.Key_Up):
            QShortcut(QKeySequence(key), self).activated.connect(self.prev_image)

        for key in (Qt.Key_Right, Qt.Key_Down):
            QShortcut(QKeySequence(key), self).activated.connect(self.next_image)

        QShortcut(QKeySequence("Ctrl+X"), self).activated.connect(self.clear_points)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.del_last_point)
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.compute_mask)
        QShortcut(QKeySequence("Ctrl+Enter"), self).activated.connect(self.compute_mask)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.delete_mask)
        QShortcut(QKeySequence("Ctrl+I"), self).activated.connect(self.invert_mask)

        QShortcut(QKeySequence(Qt.Key_Space), self).activated.connect(
            lambda: [self.btn_mask_toggle.toggle(), self.toggle_mask_checked()]
        )

    # =====================================================================
    # ====================== LOG MANAGEMENT ===============================
    # =====================================================================

    def show_log_context_menu(self, pos):
        menu = self.log_text.createStandardContextMenu()  # récupère le menu standard
        menu.addSeparator()  # sépare les options
        clear_action = menu.addAction("Clear")
        clear_action.triggered.connect(self.log_text.clear)
        menu.exec_(self.log_text.mapToGlobal(pos))

    # =====================================================================
    # ====================== LIST MANAGEMENT ===============================
    # =====================================================================

    def populate_list(self):
        # Sauvegarde des fichiers sélectionnés avant de vider le tree
        selected_items = [i.data(0, Qt.UserRole) for i in self.tree_widget.selectedItems()]
        self.tree_widget.clear()

        # Récupère les fichiers image et les trie alphabétiquement
        files = sorted(
            [f for f in os.listdir(self.images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        )

        for fname in files:
            base = os.path.splitext(fname)[0]
            csv_path = os.path.join(self.annotations_dir, base + "_points.csv")
            mask_path = os.path.join(self.masks_dir, base + "_mask.png")

            ann_present = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
            mask_present = os.path.exists(mask_path)

            item = TreeItem()
            item.setText(0, fname)
            item.setData(0, Qt.UserRole, fname)

            # Icônes annotation / masque
            item.setIcon(1, QIcon("icons/pencil.png") if ann_present else QIcon("icons/pencil_gray.png"))
            item.setData(1, Qt.UserRole, int(ann_present))

            item.setIcon(2, QIcon("icons/mask.png") if mask_present else QIcon("icons/mask_gray.png"))
            item.setData(2, Qt.UserRole, int(mask_present))

            # --- Nouvelle colonne Score ---
            score = self.scores.get(fname, None)
            item.set_score(score)

            self.tree_widget.addTopLevelItem(item)

            # Rétablir la sélection si le fichier était sélectionné
            if fname in selected_items:
                item.setSelected(True)

            self.update_tree_header_info()

        # ----- Tri ascendant par défaut sur la colonne Image -----
        self.tree_widget.sortItems(0, Qt.AscendingOrder)
        header = self.tree_widget.header()
        header.setSortIndicator(0, Qt.AscendingOrder)
        header.setSortIndicatorShown(True)

    def update_tree_header_info(self):
        total_items = self.tree_widget.topLevelItemCount()
        ann_count = 0
        mask_count = 0

        for i in range(total_items):
            item = self.tree_widget.topLevelItem(i)
            if item.data(1, Qt.UserRole):  # Annotation présente
                ann_count += 1
            if item.data(2, Qt.UserRole):  # Masque présent
                mask_count += 1

        headers = [
            f"Image ({total_items})",
            f"Annot. ({ann_count}/{total_items})",
            f"Masque ({mask_count}/{total_items})",
            "Score"
        ]

        for i, text in enumerate(headers):
            self.tree_widget.headerItem().setText(i, text)

    def on_select(self):
        items = self.tree_widget.selectedItems()
        if not items:
            return

        # Empêche le auto-save pendant un changement d’image
        self._ignore_point_changes = True

        try:
            item = items[-1]
            fname = item.data(0, Qt.UserRole)

            # Vérifie si l'élément sélectionné a changé
            if hasattr(self, '_last_selected_item') and self._last_selected_item == fname:
                return

            self._last_selected_item = fname
            base = os.path.splitext(fname)[0]

            img_path = os.path.join(self.images_dir, fname)
            self.viewer.load_image(img_path)

            pts = self.load_points_file(base)
            if pts:
                self.viewer.load_points(pts)
            else:
                self.viewer.clear_points()

            self.load_mask_file(base)

        finally:
            # Réactivation après chargement complet
            self._ignore_point_changes = False

    def on_update_item(self, fname, score):
        """Met à jour le score d'une image et l'UI."""
        # Mettre à jour le dictionnaire et le CSV
        self.scores[fname] = score
        self.save_score(fname, score)

        # Mettre à jour la ligne dans le tree
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            if item.data(0, Qt.UserRole) == fname:
                item.set_score(score)  # Met à jour la colonne Score
                item.setIcon(2, QIcon("icons/mask.png"))  # Icône Mask
                break

        current_items = self.tree_widget.selectedItems()
        if current_items:
            current_fname = current_items[-1].data(0, Qt.UserRole)
            if current_fname == fname:
                base = os.path.splitext(fname)[0]
                mask_path = os.path.join(self.masks_dir, base + "_mask.png")
                self.viewer.reload_mask(mask_path)

    def update_icons(self, items=None):
        """
        Met à jour les icônes d'annotation et de masque pour les items donnés.
        Si items=None, utilise la sélection actuelle du tree.
        """
        if items is None:
            items = self.tree_widget.selectedItems()
        if not items:
            return

        for item in items:
            fname = item.data(0, Qt.UserRole)
            base = os.path.splitext(fname)[0]

            # --- Annotation ---
            points = []
            # Si c'est l'image courante dans le viewer, prendre les points
            current_items = self.tree_widget.selectedItems()
            if current_items and current_items[-1].data(0, Qt.UserRole) == fname:
                points = self.viewer.points

            if points:
                item.setIcon(1, QIcon("icons/pencil.png"))
                item.setData(1, Qt.UserRole, 1)
            else:
                item.setIcon(1, QIcon("icons/pencil_gray.png"))
                item.setData(1, Qt.UserRole, 0)

            # --- Mask ---
            mask_path = os.path.join(self.masks_dir, base + "_mask.png")
            if os.path.exists(mask_path):
                item.setIcon(2, QIcon("icons/mask.png"))
                item.setData(2, Qt.UserRole, 1)
            else:
                item.setIcon(2, QIcon("icons/mask_gray.png"))
                item.setData(2, Qt.UserRole, 0)

        # Forcer le repaint du tree pour appliquer les icônes
        self.tree_widget.viewport().update()

    # =====================================================================
    # ================= SAVE / LOAD POINTS ================================
    # =====================================================================

    def save_points(self, fname):
        base = os.path.splitext(fname)[0]
        csv_path = os.path.join(self.annotations_dir, base + "_points.csv")
        os.makedirs(self.annotations_dir, exist_ok=True)

        points_list = [[int(p.x()), int(p.y())] for p in self.viewer.points]

        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            for x, y in points_list:
                f.write(f"{x},{y}\n")

        #self.populate_list()

    def load_points_file(self, base):
        csv_path = os.path.join(self.annotations_dir, base + "_points.csv")
        points = []

        if os.path.exists(csv_path):
            with open(csv_path, mode='r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row:  # ligne vide
                        continue

                    x, y = map(int, row)
                    points.append([x, y])
        return points

    def load_mask_file(self, base):
        mask_path = os.path.join(self.masks_dir, base + "_mask.png")
        if os.path.exists(mask_path):
            self.viewer.load_mask(mask_path)

    # =====================================================================
    # ======================= SCORE FILE            =======================
    # =====================================================================

    def save_score(self, fname, score):
        """Met à jour un score en mémoire + persistance disque"""
        if score is None:
            self.scores.pop(fname, None)
        else:
            self.scores[fname] = score

        self.save_score_file()

    def load_scores(self):
        """Charge le fichier score.csv et retourne un dict {fname: score}"""
        self.scores = {}
        score_file = os.path.join(self.masks_dir, "score.csv")
        if os.path.exists(score_file):
            with open(score_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) == 2:
                        fname, score = row
                        try:
                            self.scores[fname] = float(score)
                        except ValueError:
                            pass  # ignore les lignes invalides

    def save_score_file(self):
        """Écrit l'intégralité du score.csv depuis self.scores"""
        score_file = os.path.join(self.masks_dir, "score.csv")
        os.makedirs(self.masks_dir, exist_ok=True)

        with open(score_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for fname, score in self.scores.items():
                if score is not None:
                    writer.writerow([fname, score])


    # =====================================================================
    # ======================= NAVIGATION / ACTIONS =========================
    # =====================================================================

    def prev_image(self):
        self.auto_save_current()
        items = self.tree_widget.selectedItems()
        if not items:
            return

        current_item = items[-1]

        # Liste des items dans l'ordre affiché à l'écran
        visible_items = [self.tree_widget.topLevelItem(i) for i in range(self.tree_widget.topLevelItemCount())]

        try:
            idx = visible_items.index(current_item)
        except ValueError:
            return

        if idx > 0:
            self.tree_widget.setCurrentItem(visible_items[idx - 1])

    def next_image(self):
        self.auto_save_current()
        items = self.tree_widget.selectedItems()
        if not items:
            return

        current_item = items[-1]
        visible_items = [self.tree_widget.topLevelItem(i) for i in range(self.tree_widget.topLevelItemCount())]

        try:
            idx = visible_items.index(current_item)
        except ValueError:
            return

        if idx < len(visible_items) - 1:
            self.tree_widget.setCurrentItem(visible_items[idx + 1])

    def auto_save_current(self):
        if getattr(self, "_ignore_point_changes", False):
            return

        items = self.tree_widget.selectedItems()
        if items:
            fname = items[-1].data(0, Qt.UserRole)
            self.save_points(fname)

    def reset_zoom(self):
        if self.viewer.image:
            self.viewer.offset = QPoint(0, 0)
            self.viewer.auto_fit = True

            w_ratio = self.viewer.width() / self.viewer.image.width()
            h_ratio = self.viewer.height() / self.viewer.image.height()
            self.viewer.zoom = min(w_ratio, h_ratio, 1.0)

            self.viewer.update()

    def clear_points(self):
        # Supprime les points dans le viewer
        self.viewer.clear_points()
        self.auto_save_current()
        self.update_icons()

    def del_last_point(self):
        if self.viewer.points:
            self.viewer.remove_last_point()
            self.auto_save_current()
            self.update_icons()

    def toggle_mask_checked(self):
        self.viewer.show_mask = self.btn_mask_toggle.isChecked()
        self.viewer.update()

    def stop_compute(self):
        if hasattr(self, "batch_thread") and self.compute_running:
            self.batch_thread.stop()
            self.compute_running = False
            self.batch_progress.setFormat("Calcul stoppé manuellement")
            self.btn_mask_calc.setEnabled(True)  # Compute réactivé
            self.btn_stop.setEnabled(False)  # STOP désactivé
            self.logger.info("Calcul stoppé par l'utilisateur")

    def update_progress_text(self, current, total):
        self.batch_progress.setFormat(f"Calcul image {current} / {total}")

    # =====================================================================
    # ============================ SAM  ===================================
    # =====================================================================

    def start_sam_backend(self):
        self.logger.info("Initialisation SAM en arrière-plan…")
        self.btn_mask_calc.setEnabled(False)

        self.sam_thread = SamInitThread(
            self.sam_model,
            self.sam_checkpoint
        )

        self.sam_thread.finished_init.connect(self.on_sam_ready)
        self.sam_thread.start()

    def on_sam_ready(self, ok, msg):
        if not ok:
            QMessageBox.critical(
                self,
                "Erreur SAM",
                "Impossible d'initialiser SAM"
            )
            return

        self.sam_ready = True
        self.btn_mask_calc.setEnabled(True)
        self.batch_progress.setFormat("SAM prêt")
        self.logger.info("SAM initialisé")
        self.logger.info("========================")

    # =====================================================================
    # ============================ MASK ===================================
    # =====================================================================

    def compute_mask(self):

        # --- Sécurité : SAM pas encore prêt ---
        if not getattr(self, "sam_ready", False):
            QMessageBox.warning(
                self,
                "SAM non prêt",
                "Le modèle SAM est encore en cours d'initialisation.\nVeuillez patienter."
            )
            return

        items = self.tree_widget.selectedItems()
        if not items:
            return

        file_list = [i.data(0, Qt.UserRole) for i in items]
        overwrite = self.batch_checkbox.isChecked()

        # --- Filtrage si overwrite désactivé ---
        if not overwrite:
            files_to_keep = []
            for fname in file_list:
                base = os.path.splitext(fname)[0]
                mask_path = os.path.join(self.masks_dir, base + "_mask.png")

                if not os.path.exists(mask_path):
                    files_to_keep.append(fname)
                else:
                    self.logger.info(
                        f"[{base}]\t masque existant (cocher 'Écraser résultat' pour recalcul)"
                    )

            file_list = files_to_keep

        if not file_list:
            return

        # --- Initialisation UI ---
        self.compute_running = True
        self.batch_progress.setValue(0)
        self.batch_progress.setFormat("Calcul en cours …")
        self.batch_progress.setTextVisible(True)

        self.btn_mask_calc.setEnabled(False)
        self.btn_stop.setEnabled(True)

        postfilter = (
            self.filter_window.value()
            if self.filter_checkbox.isChecked()
            else None
        )

        # --- Lancement du thread batch ---
        self.batch_thread = BatchThread(
            file_list=file_list,
            images_dir=self.images_dir,
            annotations_dir=self.annotations_dir,
            masks_dir=self.masks_dir,
            overwrite=overwrite,
            postfilter=postfilter
        )

        # --- Connexions ---
        self.batch_thread.progress.connect(self.batch_progress.setValue)
        self.batch_thread.score.connect(self.on_update_item)
        self.batch_thread.file_done.connect(self.update_progress_text)
        self.batch_thread.finished.connect(self.compute_finished)

        self.batch_thread.start()

    def invert_mask(self):
        """Inverse les masques sélectionnés (binaire 0/1)"""
        items = self.tree_widget.selectedItems()
        if not items:
            return

        overwrite = self.batch_checkbox.isChecked()

        # Parcours de tous les items sélectionnés
        for item in items:
            fname = item.data(0, Qt.UserRole)
            base = os.path.splitext(fname)[0]
            mask_path = os.path.join(self.masks_dir, base + "_mask.png")

            # Vérifier si le masque existe déjà
            if os.path.exists(mask_path) and not overwrite:
                self.logger.info(f"[{base}]\t masque existant (cocher 'Ecraser résultat' pour inversion)")
                continue

            if not os.path.exists(mask_path):
                self.logger.info(f"[{base}]\t aucun masque à inverser")
                continue

            if invert_and_save_mask(mask_path):
                self.logger.info(f"[{base}]\t masque inversé")

                # Recharge le masque si c'est l'image courante
                current_items = self.tree_widget.selectedItems()
                if current_items and current_items[-1].data(0, Qt.UserRole) == fname:
                    self.viewer.reload_mask(mask_path)

            else:
                self.logger.warning(f"[{base}]\t impossible d'inverser le masque")

    def delete_mask(self):
        items = self.tree_widget.selectedItems()

        for item in items:
            fname = item.data(0, Qt.UserRole)
            base = os.path.splitext(fname)[0]
            mask_path = os.path.join(self.masks_dir, base + "_mask.png")

            if os.path.exists(mask_path):
                os.remove(mask_path)
                self.logger.info(f"[{base}]\t suppression du masque")

                # Supprime aussi le score
                self.save_score(fname, None)

                # Recharge le viewer si c’est l’image courante
                current_items = self.tree_widget.selectedItems()
                if current_items and current_items[-1].data(0, Qt.UserRole) == fname:
                    self.viewer.reload_mask(mask_path)

                # --- Met à jour la colonne Score ---
                item.set_score(None)

        # Met à jour uniquement les icônes des items sélectionnés
        self.update_icons(items)

    def compute_finished(self):
        self.compute_running = False
        self.batch_progress.setValue(100)
        self.batch_progress.setFormat("Calcul terminé")
        self.btn_mask_calc.setEnabled(True)  # Compute réactivé
        self.btn_stop.setEnabled(False)  # STOP désactivé
        self.populate_list()


    # =====================================================================
    # ========================== SETTINGS ==================================
    # =====================================================================

    def open_settings(self):
        dlg = SettingsDialog(self.images_dir, self.annotations_dir, self.masks_dir, self.ask_on_start)
        if dlg.exec_():
            self.images_dir, self.annotations_dir, self.masks_dir = dlg.get_paths()
            self.ask_on_start = dlg.get_ask_on_start()
            self.save_config()
            self.populate_list()

    # =====================================================================
    # ========================== HELP =====================================
    # =====================================================================

    def show_about(self):
        dlg = HelpDialog("À propos", "./help/about.md", self)
        dlg.exec_()

    def show_shortcuts(self):
        dlg = HelpDialog("Raccourcis clavier", "./help/shortcuts.md", self)
        dlg.exec_()

    def open_documentation(self):
        dlg = HelpDialog("Aide Automask", "./help/help.md", self)
        dlg.exec_()

    # =====================================================================
    # ========================== CLOSE WINDOW ==================================
    # =====================================================================

    def closeEvent(self, event):
        # Retirer proprement le handler Qt pour éviter les erreurs atexit
        if hasattr(self, "logger") and self.logger:
            self.logger.info(f"=== Fermeture Automask - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            self.logger.info(f"____________________________________________________________________________")
            for handler in self.logger.handlers[:]:
                if isinstance(handler, QPlainTextEditLogger):
                    self.logger.removeHandler(handler)
        super().closeEvent(event)


# ======================================================================
# ============================= MAIN ===================================
# ======================================================================

if __name__ == "__main__":

    # MODE CLI
    if "--cli" in sys.argv:
        run_cli()
        sys.exit(0)

    # MODE GUI
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    win.showMaximized()
    sys.exit(app.exec_())
