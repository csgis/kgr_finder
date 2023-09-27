# -*- coding: utf-8 -*-
"""
/***************************************************************************
  KgrFinder
  A QGIS plugin for detecting cultura places
 -------------------
  begin                : 2023-09-11
  copyright            : (C) 2023 by cuprit gbr
  email                : toni.schoenbuchner@cuprit.net
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QIcon, QColor

from qgis.PyQt.QtWidgets import QAction, QVBoxLayout
from qgis.gui import QgsMapTool, QgsRubberBand
from .resources import *

from qgis.core import QgsSettings, QgsWkbTypes, QgsGeometry, QgsRectangle, QgsVectorLayer, QgsField, QgsProject, QgsPointXY, QgsFeature, QgsFields
from qgis.gui import QgsOptionsWidgetFactory, QgsOptionsPageWidget
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QFormLayout, QCheckBox
import json
from qgis.gui import QgsCollapsibleGroupBox
from qgis.core import QgsCategorizedSymbolRenderer, QgsMarkerSymbol, QgsRendererCategory, QgsFillSymbol
from .data_apis import OverpassAPIQueryStrategy, iDAIGazetteerAPIQueryStrategy
from qgis.core import Qgis
from PyQt5.QtCore import Qt


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
        "osm_tags" : ["heritage"],
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
        self.createCheckBoxes(layout, "Settings", self.settings_tags, "settings_tags")
        self.createCheckBoxes(layout, "OSM – Cultural Tags", self.osm_tags, "osm_tags")
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

    def apply(self):
        for settings_key, checkboxes in self.section_checkboxes.items():
            kgr_tags = [tag for tag, checkbox in checkboxes if checkbox.isChecked()]
            QgsSettings().setValue(f"/KgrFinder/{settings_key}", kgr_tags) 

    def loadAndSetCheckboxes(self):
        for settings_key, checkboxes in self.section_checkboxes.items():
            kgr_tags = QgsSettings().value(f"/KgrFinder/{settings_key}", [])
            for tag, checkbox in checkboxes:
                checkbox.setChecked(tag in kgr_tags)
        
    def checkboxStateChanged(self):
        for settings_key, checkboxes in self.section_checkboxes.items():
            kgr_tags = [tag for tag, checkbox in checkboxes if checkbox.isChecked()]
            QgsSettings().setValue(f"/KgrFinder/{settings_key}", kgr_tags)




class KgrFinder:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        # save reference to the QGIS interface
        self.iface = iface
        self.tool = None

    def initGui(self):
        config_options_page = ConfigOptionsPage(None)

        # create action that will start plugin configuration
        self.action = QAction(QIcon(":/plugins/kgr_finder/greif.png"),
                            "KGR Finder",
                            self.iface.mainWindow())
             
        self.action.setObjectName("KGRAction")
        self.action.setCheckable(True)  # Make the action checkable
        self.action.toggled.connect(self.toggleTool)

        # add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&KGR plugins", self.action)

        self.options_factory = KgrFinderOptionsFactory()
        self.options_factory.setTitle('KGR Finder')
        iface.registerOptionsWidgetFactory(self.options_factory)


    def unload(self):
        # remove the plugin menu item and icon
        self.iface.removePluginMenu("&KGR plugins", self.action)
        self.iface.removeToolBarIcon(self.action)
        iface.unregisterOptionsWidgetFactory(self.options_factory)

        QgsSettings().remove("/KgrFinder/settings_tags")
        QgsSettings().remove("/KgrFinder/osm_tags")

    def toggleTool(self, checked):
        if checked:
            self.tool = FindKGRData(self.iface.mapCanvas())
            self.iface.mapCanvas().setMapTool(self.tool)
        else:
            self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = None

    def run(self):
        # create and show a configuration dialog or something similar
        print("TestPlugin: run called!")


class FindKGRData(QgsMapTool):
    def __init__(self, canvas):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setStrokeColor(QColor('red'))
        self.rubber_band.setWidth(1)
        self.is_drawing = False
        self.polygon_points = []

        selected_settings_tags = QgsSettings().value("/KgrFinder/settings_tags", [])
        self.api_strategies = []
        if "OSM abfragen" in selected_settings_tags:
            self.api_strategies.append(OverpassAPIQueryStrategy()) 
        if "iDAI abfragen" in selected_settings_tags:
            self.api_strategies.append(iDAIGazetteerAPIQueryStrategy()) 

    def canvasPressEvent(self, event):
        if self.is_drawing:
            self.polygon_points.append(self.toMapCoordinates(event.pos()))
            self.updateRubberBand()
        else:
            self.is_drawing = True
            self.polygon_points = [self.toMapCoordinates(event.pos())]
            self.updateRubberBand()
            self.rubber_band.show()

    def canvasReleaseEvent(self, event):
        if self.is_drawing:
            if event.button() == Qt.RightButton:
                self.is_drawing = False
                #self.rubber_band.reset()
                #self.rubber_band.hide()
                self.showPolygonCoordinates()

    def updateRubberBand(self):
        self.rubber_band.setToGeometry(QgsGeometry.fromPolygonXY([self.polygon_points]), None)
        self.rubber_band.show()

    def showPolygonCoordinates(self):
        drawn_polygon = QgsGeometry.fromPolygonXY([self.polygon_points])
        rect = drawn_polygon.boundingBox()

        drawn_x_min = rect.xMinimum()
        drawn_y_min = rect.yMinimum()
        drawn_x_max = rect.xMaximum()
        drawn_y_max = rect.yMaximum()

        point_layer = self.createLayer('Point')
        fields = point_layer.fields()

        polygon_layer = self.createLayer('Polygon')

        root = QgsProject.instance().layerTreeRoot()
        group = root.insertGroup(0, "KGR")
        group.addLayer(point_layer)
        group.addLayer(polygon_layer)

        categorized_renderer_point = self.createCategorizedRendererPoints(point_layer)
        point_layer.setRenderer(categorized_renderer_point)

        categorized_renderer_polygon = self.createCategorizedRendererPolygons(polygon_layer)
        polygon_layer.setRenderer(categorized_renderer_polygon)

        QgsProject.instance().addMapLayer(polygon_layer, False)
        QgsProject.instance().addMapLayer(point_layer, False)

        for strategy in self.api_strategies:
            data = strategy.query(drawn_x_min, drawn_y_min, drawn_x_max, drawn_y_max)
            elements = strategy.extractElements(data)
            attribute_mappings = strategy.getAttributeMappings()

            for element in elements:
                feature = self.createFeature(element, fields, attribute_mappings, strategy)

                if feature is None:
                    continue

                geometry_type = strategy.getGeometryType(element)
                if geometry_type == 'point':
                    if feature.geometry().within(drawn_polygon):
                        point_layer.dataProvider().addFeature(feature)
                elif geometry_type == 'polygon':
                    if feature.geometry().intersects(drawn_polygon):
                        polygon_layer.dataProvider().addFeature(feature)

            iface.messageBar().pushMessage("KGR", "Data from " + strategy.source + " loaded", level=Qgis.Success, duration=3)


    def createFeature(self, element, fields, attribute_mappings, strategy):
        geometry_type = strategy.getGeometryType(element)

        if geometry_type == 'point':
            lat, lon = strategy.extractLatLon(element)
            if lat is not None and lon is not None:
                point = QgsPointXY(lon, lat)
                geometry = QgsGeometry.fromPointXY(point)
        elif geometry_type == 'polygon':
            polygonNodes = strategy.extractPolygonNodes(element)
            if polygonNodes:
                polygon = QgsGeometry.fromPolygonXY([polygonNodes])
                geometry = polygon
            else:
                return None 
        else:
            return None

        feature = QgsFeature(fields)
        feature.setGeometry(geometry)


        # # Iterate over attribute_mappings and set attributes
        for attribute, mapping in attribute_mappings.items():
            if '.' in mapping:
                # Handle nested mappings like 'tags.name'
                parts = mapping.split('.')
                value = element
                for part in parts:
                    value = value.get(part, {})
            else:
                # Check if the mapping exists in the 'tags' dictionary
                if mapping.startswith('tags.'):
                    tag_key = mapping.split('tags.')[1]
                    value = element['tags'].get(tag_key, '')
                else:
                    value = element.get(mapping, '')
            value = str(value) if value else "-" 
            feature.setAttribute(attribute, value)
        
        feature.setAttribute('source', f"{strategy.source}")

        return feature

    def createFields(self):
        fields = QgsFields()
        fields.append(QgsField('lon', QVariant.String))
        fields.append(QgsField('lat', QVariant.String))
        fields.append(QgsField('name', QVariant.String))
        fields.append(QgsField('source', QVariant.String))
        fields.append(QgsField('description', QVariant.String, 'string', 5000))
        fields.append(QgsField('type', QVariant.String))
        fields.append(QgsField('id', QVariant.String))
        fields.append(QgsField('tags', QVariant.String, 'json', 5000))
        fields.append(QgsField('building', QVariant.String))

        return fields

    def createLayer(self, geometryType):
        fields = self.createFields()
        project_crs = QgsProject.instance().crs()
        layer = QgsVectorLayer(f'{geometryType}?crs={project_crs.authid()}', f'KGR ({geometryType.capitalize()})', 'memory')
        layer.dataProvider().addAttributes(fields)
        layer.updateFields()

        return layer

    def createCategorizedRendererPoints(self, layer):
        categorized_renderer = QgsCategorizedSymbolRenderer('source')

        osm_symbol = QgsMarkerSymbol.defaultSymbol(layer.geometryType())
        osm_symbol.setColor(QColor(255, 0, 0))  # Blue color
        osm_symbol.setSize(4)  # Increased size

        non_osm_symbol = QgsMarkerSymbol.defaultSymbol(layer.geometryType())
        non_osm_symbol.setColor(QColor(0, 0, 255))  # Red color
        non_osm_symbol.setSize(4)  # Increased size

        cat_osm = QgsRendererCategory('osm', osm_symbol, 'OSM Features')
        cat_non_osm = QgsRendererCategory('DAI', non_osm_symbol, 'DAI')

        categorized_renderer.addCategory(cat_osm)
        categorized_renderer.addCategory(cat_non_osm)

        return categorized_renderer

    def createCategorizedRendererPolygons(self, layer):
        categorized_renderer = QgsCategorizedSymbolRenderer('source')

        osm_symbol = QgsFillSymbol.createSimple({
            'color': '255,255,0,255',  # Yellow color with alpha
            'outline_style': 'solid',
            'outline_color': '0,0,0,255',  # Black color with alpha
            'outline_width': '0.5',  # Outline width
        })

        non_osm_symbol = QgsFillSymbol.createSimple({
            'color': '0,255,0,255',  # Green color with alpha
            'outline_style': 'solid',
            'outline_color': '0,0,0,255',  # Black color with alpha
            'outline_width': '0.5',  # Outline width
        })

        cat_osm = QgsRendererCategory('osm', osm_symbol, 'OSM Features')
        cat_non_osm = QgsRendererCategory('DAI', non_osm_symbol, 'DAI')

        categorized_renderer.addCategory(cat_osm)
        categorized_renderer.addCategory(cat_non_osm)

        return categorized_renderer

    def deactivate(self):
        self.rubber_band.reset()
        self.rubber_band.hide()
        QgsMapTool.deactivate(self)

