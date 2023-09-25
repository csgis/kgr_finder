

# Import the code for the DockWidget
import os.path
from qgis.core import QgsSettings
from qgis.gui import  QgsOptionsPageWidget
from qgis.PyQt.QtWidgets import QFormLayout, QCheckBox, QLabel
import json

class ConfigOptionsPage(QgsOptionsPageWidget):

    cultural_tags = [
        "place_of_worship",
        "Historic",
        "Museum",
        "Memorial",
        "Artwork",
        "Castle",
        "Ruins",
        "Archaeological Site",
        "Monastery",
        "Cultural Centre",
        "Library",
        "heritage"
    ]

    def __init__(self, parent):
        super().__init__(parent)
        layout = QFormLayout()
        self.setLayout(layout)

        # Add a headline
        headline = QLabel("Please choose OSM Tags")
        headline.setStyleSheet("font-size: 14px; margin: 10px;")
        layout.addRow(headline)

        # Create checkboxes for cultural OSM tags
        self.checkboxes = []

        for tag in self.cultural_tags:
            checkbox = QCheckBox(tag)
            checkbox.setStyleSheet("margin-left: 10px;")

            layout.addWidget(checkbox)
            checkbox.stateChanged.connect(self.checkboxStateChanged)
            self.checkboxes.append((tag, checkbox))

        # Load selected tags from settings and set checkboxes
        selected_tags = QgsSettings().value("/KgrFinder/cultural_tags", []) 
        for tag, checkbox in self.checkboxes:
            checkbox.setChecked(tag in selected_tags)

    def checkboxStateChanged(self):
        selected_tags = [tag for tag, checkbox in self.checkboxes if checkbox.isChecked()]
        QgsSettings().setValue("/KgrFinder/cultural_tags", selected_tags)  # Save selected tags to settings
