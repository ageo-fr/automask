# ======================================
# Auteur : Alexandre Guyot
# Date : 2026-03-25
# Description : Automask - help
# ======================================

import os
from pathlib import Path
import markdown

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextBrowser


def load_markdown(path, variables=None):
    path = Path(path)

    if not path.exists():
        return "<i>Fichier d’aide introuvable</i>"

    md = path.read_text(encoding="utf-8")

    # Remplacement des variables
    if variables:
        for key, value in variables.items():
            md = md.replace(
                "{{" + key + "}}",
                str(value)
            )

    return markdown.markdown(md, extensions=["extra"])


class HelpDialog(QDialog):
    def __init__(self, title, md_path, parent=None, variables=None):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(700, 500)

        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)

        browser.setHtml(
            load_markdown(md_path, variables)
        )

        layout.addWidget(browser)