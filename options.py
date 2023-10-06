from qgis.core import QgsSettings
from qgis.gui import (QgsCollapsibleGroupBox, QgsOptionsPageWidget,
                      QgsOptionsWidgetFactory)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (QCheckBox, QFormLayout, QLabel, QRadioButton,
                                 QTextEdit, QVBoxLayout)

from .resources import *


class KgrFinderOptionsFactory(QgsOptionsWidgetFactory):

    def __init__(self):
        super().__init__()

    def icon(self):
        return QIcon(':/plugins/kgr_finder/assets/greif.png')

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

    idai_gazetteer_filter = [
        "None",
        "populated-place",
        "archaeological-site",
        "archaeological-area",
        "building-institution"
    ]

    settings_tags = [
        "OSM abfragen",
        "iDAI abfragen"
    ]

    initially_checked = {
        "osm_tags" : ["heritage", "historic"],
        "settings_tags" : ["iDAI abfragen","OSM abfragen"],
        "idai_gazetteer_filter" : "archaeological-site"
    }

    labels = {
        "settings_tags" : "Which Api should be used?",
        "osm_tags": "Tags included in a OSM search. Only in use if settings have checked the API",
        "osm_custom_tags_textarea" : "Custom OSM Tags that should be respected (each on one line)",
        "idai_gazetteer_filter": "Please choose the location type that is used for a iDAI.gazetteer search",
        "idai_gazetteer_tags_tagarea": "Tags that should filter the result (each on one line). Tags act with AND operator."
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
        self.section_radio_buttons = {}

        group_box_layout_settings = self.createCheckBoxes(layout, "Settings", self.settings_tags, "settings_tags")
        group_box_layout_osm = self.createCheckBoxes(layout, "OSM – Cultural Tags", self.osm_tags, "osm_tags")
        self.createTextarea(group_box_layout_osm, "custom_osm_tags", self.labels["osm_custom_tags_textarea"])
        group_box_layout_gazetteer = self.createRadioButtons(layout, "IDAI Gazetteer Filter", self.idai_gazetteer_filter, "idai_gazetteer_filter")
        self.createTextarea(group_box_layout_gazetteer, "custom_gazetteer_tags", self.labels["idai_gazetteer_tags_tagarea"])

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

        # Add an informational label
        info_label = QLabel(self.labels[settings_key])
        group_box_layout.addWidget(info_label)

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

    def createTextarea(self, group_box_layout, key, info_label_text):
        textarea = QTextEdit()
        textarea.setPlaceholderText("tag1")

        # Add an informational label
        info_label = QLabel(info_label_text)
        info_label.setStyleSheet("font-style: italic;")

        group_box_layout.addWidget(info_label)

        group_box_layout.addWidget(textarea)

        self.text_areas[key] = textarea


    def createRadioButtons(self, layout, group_title, tags, settings_key):
        group_box = QgsCollapsibleGroupBox(group_title)
        group_box.setCollapsed(True)
        group_box_layout = QVBoxLayout()
        group_box.setLayout(group_box_layout)

        # Add an informational label
        info_label = QLabel(self.labels[settings_key])
        group_box_layout.addWidget(info_label)

        radio_buttons = []

        for tag in tags:
            radio_button = QRadioButton(tag)
            radio_button.setStyleSheet("margin: 10px;")
            radio_button.toggled.connect(self.radioButtonToggled)
            radio_buttons.append((tag, radio_button))
            group_box_layout.addWidget(radio_button)

        layout.addWidget(group_box)

        # Save radio buttons in the dictionary
        self.section_radio_buttons[settings_key] = radio_buttons

        # Load selected tag from settings and set radio buttons
        selected_tag = QgsSettings().value(f"/KgrFinder/{settings_key}", "")
        if not selected_tag and not any(button[1].isChecked() for button in radio_buttons):
            # If no saved setting and no radio button is checked, set the first one as checked
            for tag, radio_button in radio_buttons:
                if tag == self.initially_checked["gazetteer_filter"]:
                    radio_button.setChecked(tag == self.initially_checked["gazetteer_filter"])
        else:
            for tag, radio_button in radio_buttons:
                radio_button.setChecked(tag == selected_tag)

        return group_box_layout



    def radioButtonToggled(self, checked):
        sender = self.sender()
        if checked:
            for settings_key, radio_buttons in self.section_radio_buttons.items():
                selected_tag = next(tag for tag, radio_button in radio_buttons if radio_button.isChecked())
                QgsSettings().setValue(f"/KgrFinder/{settings_key}", selected_tag)


    def apply(self):

        for settings_key, checkboxes in self.section_checkboxes.items():
            kgr_tags = [tag for tag, checkbox in checkboxes if isinstance(checkbox, QCheckBox) and  checkbox.isChecked()]
            QgsSettings().setValue(f"/KgrFinder/{settings_key}", kgr_tags) 


        QgsSettings().setValue(f"/KgrFinder/custom_osm_tags", self.text_areas["custom_osm_tags"].toPlainText().splitlines())
        QgsSettings().setValue(f"/KgrFinder/custom_gazetteer_tags", self.text_areas["custom_gazetteer_tags"].toPlainText().splitlines())


    def loadAndSetCheckboxes(self):
        for settings_key, checkboxes in self.section_checkboxes.items():
            kgr_tags = QgsSettings().value(f"/KgrFinder/{settings_key}", [])
            for tag, checkbox in checkboxes:
                checkbox.setChecked(tag in kgr_tags)
        
        custom_osm_tags = QgsSettings().value(f"/KgrFinder/custom_osm_tags", [])
        custom_gazetteer_tags = QgsSettings().value(f"/KgrFinder/custom_gazetteer_tags", [])

        self.text_areas["custom_osm_tags"].setPlainText('\n'.join(custom_osm_tags))
        self.text_areas["custom_gazetteer_tags"].setPlainText('\n'.join(custom_gazetteer_tags))

    def checkboxStateChanged(self):
        for settings_key, checkboxes in self.section_checkboxes.items():
            kgr_tags = [tag for tag, checkbox in checkboxes if checkbox.isChecked()]
            QgsSettings().setValue(f"/KgrFinder/{settings_key}", kgr_tags)
