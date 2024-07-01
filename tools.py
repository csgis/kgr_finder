from PyQt5.QtCore import Qt
from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsFillSymbol,
    QgsGeometry,
    QgsMarkerSymbol,
    QgsPointXY,
    QgsProject,
    QgsRendererCategory,
    QgsSettings,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QPushButton,
    QMessageBox,
)
from qgis.utils import iface

from .data_apis import OverpassAPIQueryStrategy, iDAIGazetteerAPIQueryStrategy
from .resources import *
from .utils.logger import Logger

Log = Logger()


class FindKGRDataBaseTool(QgsMapTool):
    def __init__(self, canvas):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.polygon_points = []
        selected_settings_tags = QgsSettings().value("/KgrFinder/settings_tags", [])
        self.api_strategies = []
        self.polygons_features_must_be_within = []

        Log.log_debug(f"settings are {selected_settings_tags}")

        if "OSM abfragen" in selected_settings_tags:
            self.api_strategies.append(OverpassAPIQueryStrategy())
        if "iDAI abfragen" in selected_settings_tags:
            self.api_strategies.append(iDAIGazetteerAPIQueryStrategy())
        Log.log_debug(str(self.api_strategies))

    def checkAreaSize(self, x_min, y_min, x_max, y_max, threshold=500):
        area = (x_max - x_min) * (y_max - y_min)

        if area > threshold:
            reply = QMessageBox.question(
                iface.mainWindow(),
                "Large Polygon Detected",
                f"The selected area is {area:.2f} square meters, which is larger than {threshold} square meters. "
                "This may result in a long API request. Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.No:
                return None

        return True

    def addFeature(self, feature):
        self.polygons_features_must_be_within.append(feature)

    def setSelectedLayer(self, selected_layer):
        self.polygon_points = []

        if not selected_layer.selectedFeatureCount():
            features = selected_layer.getFeatures()
        else:
            features = selected_layer.selectedFeatures()

        for feature in features:
            geometry = feature.geometry()
            self.polygons_features_must_be_within.append(feature)
            if geometry.type() == QgsWkbTypes.PolygonGeometry:
                polygons = (
                    geometry.asMultiPolygon()[0]
                    if geometry.wkbType() == QgsWkbTypes.MultiPolygon
                    else [geometry.asPolygon()[0]]
                )
                for polygon in polygons:
                    polygon_points = [QgsPointXY(point) for point in polygon]
                    self.polygon_points.extend(polygon_points)

    def processPolygonCoordinates(self):
        outer_bounds_of_survey_polygons = QgsGeometry.fromPolygonXY(
            [self.polygon_points]
        )

        rect = outer_bounds_of_survey_polygons.boundingBox()

        drawn_x_min = rect.xMinimum()
        drawn_y_min = rect.yMinimum()
        drawn_x_max = rect.xMaximum()
        drawn_y_max = rect.yMaximum()
        if self.checkAreaSize(drawn_x_min, drawn_y_min, drawn_x_max, drawn_y_max):
            fields, point_layer, polygon_layer = self.createNewPolygonLayers()
            self.addFeaturesByStrategy(
                drawn_x_min,
                drawn_y_min,
                drawn_x_max,
                drawn_y_max,
                fields,
                polygon_layer,
                point_layer,
            )

    def createNewPolygonLayers(self):
        point_layer = self.createLayer("Point")
        fields = point_layer.fields()

        polygon_layer = self.createLayer("Polygon")

        root = QgsProject.instance().layerTreeRoot()
        group = root.insertGroup(0, "KGR")
        group.addLayer(point_layer)
        group.addLayer(polygon_layer)

        categorized_renderer_point = self.createCategorizedRendererPoints(point_layer)
        point_layer.setRenderer(categorized_renderer_point)

        categorized_renderer_polygon = self.createCategorizedRendererPolygons(
            polygon_layer
        )
        polygon_layer.setRenderer(categorized_renderer_polygon)

        QgsProject.instance().addMapLayer(polygon_layer, False)
        QgsProject.instance().addMapLayer(point_layer, False)

        return fields, point_layer, polygon_layer

    def addFeaturesByStrategy(
        self,
        drawn_x_min,
        drawn_y_min,
        drawn_x_max,
        drawn_y_max,
        fields,
        polygon_layer,
        point_layer,
    ):
        for strategy in self.api_strategies:
            data = strategy.query(drawn_x_min, drawn_y_min, drawn_x_max, drawn_y_max)
            elements = strategy.extractElements(data)
            attribute_mappings = strategy.getAttributeMappings()

            for element in elements:
                feature = self.createFeature(
                    element, fields, attribute_mappings, strategy
                )

                if feature is None:
                    continue

                geometry_type = strategy.getGeometryType(element)

                for f in self.polygons_features_must_be_within:
                    if geometry_type == "point" and f.geometry().contains(
                        feature.geometry()
                    ):
                        point_layer.dataProvider().addFeature(feature)

                    elif geometry_type == "polygon" and feature.geometry().intersects(
                        f.geometry()
                    ):
                        polygon_layer.dataProvider().addFeature(feature)

            iface.messageBar().pushMessage(
                "KGR",
                "Data from " + strategy.source + " loaded",
                level=Qgis.Success,
                duration=3,
            )

    def createFeature(self, element, fields, attribute_mappings, strategy):
        geometry_type = strategy.getGeometryType(element)

        if geometry_type == "point":
            lat, lon = strategy.extractLatLon(element)
            if lat is not None and lon is not None:
                point = QgsPointXY(lon, lat)
                geometry = QgsGeometry.fromPointXY(point)
        elif geometry_type == "polygon":
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

        # Iterate over attribute_mappings and set attributes
        for attribute, mapping in attribute_mappings.items():
            if "." in mapping:
                parts = mapping.split(".")
                value = element
                for part in parts:
                    if "[" in part and "]" in part:
                        # Handle indexed mappings
                        base_part, index = part.split("[")
                        index = int(index.rstrip("]"))
                        try:
                            value = value.get(base_part, [])[index]
                        except IndexError:
                            value = value.get(part, {})
                            pass
                    else:
                        value = value.get(part, {})
            else:
                if mapping.startswith("tags."):
                    tag_key = mapping.split("tags.")[1]
                    value = element["tags"].get(tag_key, "")
                else:
                    value = element.get(mapping, "")
            value = str(value) if value else "-"
            feature.setAttribute(attribute, value)

        feature.setAttribute("source", f"{strategy.source}")

        return feature

    def createFields(self):
        fields = QgsFields()
        fields.append(QgsField("lon", QVariant.String))
        fields.append(QgsField("lat", QVariant.String))
        fields.append(QgsField("name", QVariant.String))
        fields.append(QgsField("source", QVariant.String))
        fields.append(QgsField("description", QVariant.String, "string", 9000))
        fields.append(QgsField("type", QVariant.String))
        fields.append(QgsField("id", QVariant.String))
        fields.append(QgsField("tags", QVariant.String, "json", 9000))

        return fields

    def createLayer(self, geometryType):
        fields = self.createFields()
        project_crs = QgsProject.instance().crs()
        layer = QgsVectorLayer(
            f"{geometryType}?crs={project_crs.authid()}",
            f"KGR ({geometryType.capitalize()})",
            "memory",
        )
        layer.dataProvider().addAttributes(fields)
        layer.updateFields()

        return layer

    def createCategorizedRendererPoints(self, layer):
        categorized_renderer = QgsCategorizedSymbolRenderer("source")

        osm_symbol = QgsMarkerSymbol.defaultSymbol(layer.geometryType())
        osm_symbol.setColor(QColor(255, 0, 0))  # Blue color
        osm_symbol.setSize(4)  # Increased size

        non_osm_symbol = QgsMarkerSymbol.defaultSymbol(layer.geometryType())
        non_osm_symbol.setColor(QColor(0, 0, 255))  # Red color
        non_osm_symbol.setSize(4)  # Increased size

        cat_osm = QgsRendererCategory(
            "Open Street Map", osm_symbol, "Open Street point data"
        )
        cat_idai_gazetteer = QgsRendererCategory(
            "iDAI.Gazetteer", non_osm_symbol, "iDAI.Gazetteer point data"
        )

        categorized_renderer.addCategory(cat_osm)
        categorized_renderer.addCategory(cat_idai_gazetteer)

        return categorized_renderer

    def createCategorizedRendererPolygons(self, layer):
        categorized_renderer = QgsCategorizedSymbolRenderer("source")

        osm_symbol = QgsFillSymbol.createSimple(
            {
                "color": "255,255,0,255",  # Yellow color with alpha
                "outline_style": "solid",
                "outline_color": "0,0,0,255",  # Black color with alpha
                "outline_width": "0.5",  # Outline width
            }
        )

        non_osm_symbol = QgsFillSymbol.createSimple(
            {
                "color": "0,255,0,255",  # Green color with alpha
                "outline_style": "solid",
                "outline_color": "0,0,0,255",  # Black color with alpha
                "outline_width": "0.5",  # Outline width
            }
        )

        cat_osm = QgsRendererCategory(
            "Open Street Map", osm_symbol, "Open Street polygon data"
        )
        cat_idai_gazetteer = QgsRendererCategory(
            "iDAI.Gazetteer", non_osm_symbol, "iDAI.Gazetteer polygon data"
        )

        categorized_renderer.addCategory(cat_osm)
        categorized_renderer.addCategory(cat_idai_gazetteer)

        return categorized_renderer

    def deactivate(self):
        self.rubber_band.reset()
        self.rubber_band.hide()
        QgsMapTool.deactivate(self)


class DrawPolygonTool(FindKGRDataBaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)

        self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setStrokeColor(QColor("red"))
        self.rubber_band.setWidth(1)
        self.is_drawing = False
        self.polygons_features_must_be_within = []

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
                # self.rubber_band.reset()
                # self.rubber_band.hide()

                # # Create a new feature with the drawn polygon
                polygon_geometry = QgsGeometry.fromPolygonXY([self.polygon_points])
                feature = QgsFeature()
                feature.setGeometry(polygon_geometry)
                self.polygons_features_must_be_within.append(feature)

                self.processPolygonCoordinates()

    def updateRubberBand(self):
        self.rubber_band.setToGeometry(
            QgsGeometry.fromPolygonXY([self.polygon_points]), None
        )
        self.rubber_band.show()


class PolygonLayerDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QFormLayout()
        self.setLayout(layout)

        # Create a combo box to select polygon layers
        self.layer_combo = QComboBox(self)
        self.layer_combo.addItem("Select a layer")  # Placeholder item
        for layer in QgsProject.instance().mapLayers().values():
            if (
                isinstance(layer, QgsVectorLayer)
                and layer.geometryType() == QgsWkbTypes.PolygonGeometry
            ):
                self.layer_combo.addItem(layer.name())

        layout.addRow("Select Polygon Layer:", self.layer_combo)

        # Create a button to perform an action (if needed)
        self.button = QPushButton("search", self)
        self.button.clicked.connect(
            self.performAction
        )  # Connect the button click event to performAction method
        layout.addRow("", self.button)

    def performAction(self):
        self.accept()  # Accept the dialog when the button is clicked
