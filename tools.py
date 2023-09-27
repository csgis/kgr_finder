from PyQt5.QtCore import Qt
from qgis.core import (Qgis, QgsCategorizedSymbolRenderer, QgsFeature,
                       QgsField, QgsFields, QgsFillSymbol, QgsGeometry,
                       QgsMarkerSymbol, QgsPointXY, QgsProject,
                       QgsRendererCategory, QgsSettings, QgsVectorLayer,
                       QgsWkbTypes)
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QComboBox, QDialog, QFormLayout, QPushButton
from qgis.utils import iface

from .data_apis import OverpassAPIQueryStrategy, iDAIGazetteerAPIQueryStrategy
from .resources import *


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

    def setSelectedLayer(self, selected_layer):
        selected_geometry = selected_layer.getFeatures().__next__().geometry()
        
        # Convert the selected geometry to a list of QgsPointXY
        self.polygon_points = [QgsPointXY(point) for point in selected_geometry.asPolygon()[0]]

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
                self.processPolygonCoordinates()

    def updateRubberBand(self):
        self.rubber_band.setToGeometry(QgsGeometry.fromPolygonXY([self.polygon_points]), None)
        self.rubber_band.show()

    def processPolygonCoordinates(self):
        drawn_polygon = QgsGeometry.fromPolygonXY([self.polygon_points])
        rect = drawn_polygon.boundingBox()

        drawn_x_min = rect.xMinimum()
        drawn_y_min = rect.yMinimum()
        drawn_x_max = rect.xMaximum()
        drawn_y_max = rect.yMaximum()

        fields, point_layer, polygon_layer = self.createNewPolygonLayers()
        self.addFeaturesByStrategy(drawn_x_min, drawn_y_min, drawn_x_max, drawn_y_max, fields, polygon_layer, point_layer, drawn_polygon)


    def createNewPolygonLayers(self):
      
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

        return fields, point_layer, polygon_layer


    def addFeaturesByStrategy(self, drawn_x_min, drawn_y_min, drawn_x_max, drawn_y_max, fields, polygon_layer, point_layer, drawn_polygon):

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

class PolygonLayerDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QFormLayout()
        self.setLayout(layout)

        # Create a combo box to select polygon layers
        self.layer_combo = QComboBox(self)
        self.layer_combo.addItem('Select a layer')  # Placeholder item
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                self.layer_combo.addItem(layer.name())

        layout.addRow("Select Polygon Layer:", self.layer_combo)

        # Create a button to perform an action (if needed)
        self.button = QPushButton('search', self)
        self.button.clicked.connect(self.performAction)  # Connect the button click event to performAction method
        layout.addRow("Search Data:", self.button)

    def performAction(self):
        self.accept()  # Accept the dialog when the button is clicked