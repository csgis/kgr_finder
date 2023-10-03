from qgis.core import QgsSettings
from qgis.gui import (QgsCollapsibleGroupBox, QgsOptionsPageWidget,
                      QgsOptionsWidgetFactory)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QCheckBox, QFormLayout, QVBoxLayout, QTextEdit

from .resources import *


class KgrFinderOptionsFactory(QgsOptionsWidgetFactory):

    def __init__(self):
        super().__init__()

    def icon(self):
        return QIcon(':/plugins/kgr_finder/greif.png')

    def createWidget(self, parent):
        return ConfigOptionsPage(parent)


class ConfigOptionsPage(QgsOptionsPageWidget):

    osm_tags = [
        "heritage",
        "archaeological_site",
        "historic",
        "memorial",
        "statue",
        "tomb",
        "mosque",
        "place_of_worship",
        "museum",
        "artwork",
        "castle",
        "ruins",
        "monastery"
    ]

    settings_tags = [
        "OSM abfragen",
        "iDAI abfragen"
    ]

    initially_checked = {
        "osm_tags" : ["heritage", "memorial"],
        "settings_tags" : ["iDAI abfragen", "OSM abfragen"]
    }

    def __init__(self, parent):
        super().__init__(parent)
        layout = QFormLayout()
        self.setLayout(layout)

        for key in self.initially_checked.keys():
            current_value = QgsSettings().value(f"/KgrFinder/{key}", [])
            if not current_value and not self.anyCheckboxChecked(key):
                QgsSettings().setValue(f"/KgrFinder/{key}", self.initially_checked[key])

        self.section_checkboxes = {} 
        self.text_areas = {} 

        group_box_layout_settings = self.createCheckBoxes(layout, "Settings", self.settings_tags, "settings_tags")
        group_box_layout_osm = self.createCheckBoxes(layout, "OSM – Cultural Tags", self.osm_tags, "osm_tags")
        self.customTagsOsmTextarea(group_box_layout_osm)

        self.applyInitialSettings()
        self.loadAndSetCheckboxes()

    def applyInitialSettings(self):
        for key in self.initially_checked.keys():
            current_value = QgsSettings().value(f"/KgrFinder/{key}", [])
            if not current_value and not self.anyCheckboxChecked(key):
                QgsSettings().setValue(f"/KgrFinder/{key}", self.initially_checked[key])


    def anyCheckboxChecked(self, settings_key):
        osm_tags = QgsSettings().value(f"/KgrFinder/{settings_key}", [])
        return any(tag in osm_tags for tag in self.initially_checked[settings_key])

    def createCheckBoxes(self, layout, group_title, tags, settings_key):
        group_box = QgsCollapsibleGroupBox(group_title)
        group_box.setCollapsed(True)
        group_box_layout = QVBoxLayout()
        group_box.setLayout(group_box_layout)

        checkboxes = []

        for tag in tags:
            checkbox = QCheckBox(tag)
            checkbox.setStyleSheet("margin: 10px;")
            checkbox.stateChanged.connect(self.checkboxStateChanged)
            checkboxes.append((tag, checkbox))
            group_box_layout.addWidget(checkbox)

        layout.addWidget(group_box)

        # Save checkboxes in the dictionary
        self.section_checkboxes[settings_key] = checkboxes

        # Load selected tags from settings and set checkboxes
        kgr_tags = QgsSettings().value(f"/KgrFinder/{settings_key}", []) 
        for tag, checkbox in checkboxes:
            checkbox.setChecked(tag in kgr_tags)

        return group_box_layout

    def customTagsOsmTextarea(self, group_box_layout_osm):
        textarea = QTextEdit()
        textarea.setPlaceholderText("Enter additional OSM tags here")
        group_box_layout_osm.addWidget(textarea)

        self.text_areas["custom_osm_tags"] = textarea
        
    def apply(self):
        print(self.text_areas)
        print(self.text_areas["custom_osm_tags"].toPlainText())
        print(self.text_areas["custom_osm_tags"].toPlainText().splitlines())
        for settings_key, checkboxes in self.section_checkboxes.items():
            kgr_tags = [tag for tag, checkbox in checkboxes if isinstance(checkbox, QCheckBox) and  checkbox.isChecked()]
            QgsSettings().setValue(f"/KgrFinder/{settings_key}", kgr_tags) 



        QgsSettings().setValue(f"/KgrFinder/custom_osm_tags", self.text_areas["custom_osm_tags"].toPlainText().splitlines())


    def loadAndSetCheckboxes(self):
        for settings_key, checkboxes in self.section_checkboxes.items():
            kgr_tags = QgsSettings().value(f"/KgrFinder/{settings_key}", [])
            for tag, checkbox in checkboxes:
                checkbox.setChecked(tag in kgr_tags)
        
        custom_osm_tags = QgsSettings().value(f"/KgrFinder/custom_osm_tags", [])
        print(custom_osm_tags)
        print('\n'.join(custom_osm_tags))
        self.text_areas["custom_osm_tags"].setPlainText('\n'.join(custom_osm_tags))

    def checkboxStateChanged(self):
        for settings_key, checkboxes in self.section_checkboxes.items():
            kgr_tags = [tag for tag, checkbox in checkboxes if checkbox.isChecked()]
            QgsSettings().setValue(f"/KgrFinder/{settings_key}", kgr_tags)
