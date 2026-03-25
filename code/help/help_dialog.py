# ======================================
# Auteur : Alexandre Guyot
# Date : 2026-03-25
# Description : Automask - help
# ======================================

import os
import markdown

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextBrowser


def load_markdown(path):
    if not os.path.exists(path):
        return "<i>Fichier d’aide introuvable</i>"

    with open(path, encoding="utf-8") as f:
        md = f.read()

    return markdown.markdown(md, extensions=["extra"])


class HelpDialog(QDialog):
    def __init__(self, title, md_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 500)

        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(load_markdown(md_path))

        layout.addWidget(browser)
