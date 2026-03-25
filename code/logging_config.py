# ======================================
# Auteur : Alexandre Guyot
# Date : 2026-03-25
# Description : Automask - logging
# ======================================

import logging
from PyQt5.QtCore import QObject, pyqtSignal
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Handler personnalisé pour Qt
class QPlainTextEditLogger(logging.Handler, QObject):
    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__()
        QObject.__init__(self, parent)
        self.log_signal.connect(self.append_log)

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg)

    def append_log(self, msg):
        # Méthode vide, sera connectée au QPlainTextEdit dans main.py
        pass

def setup_logging(log_text_edit):
    """
    Configure le logger pour Automask.
    Args:
        log_text_edit (QPlainTextEdit): Widget Qt pour afficher les logs.
    Returns:
        logging.Logger: Logger configuré.
    """
    logger = logging.getLogger("Automask")
    logger.setLevel(logging.INFO)

    # Formattage des messages
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Handler pour le fichier (avec rotation)
    file_handler = RotatingFileHandler(
        "./logs/automask.log",
        maxBytes=1024 * 1024,  # 1 Mo
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    # Handler pour Qt
    qt_handler = QPlainTextEditLogger()
    qt_handler.setFormatter(formatter)
    qt_handler.log_signal.connect(log_text_edit.appendPlainText)  # Connexion directe au QPlainTextEdit

    # Ajout des handlers
    logger.addHandler(file_handler)
    logger.addHandler(qt_handler)

    # Message de démarrage
    logger.info(f"=== Démarrage Automask - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    return logger
