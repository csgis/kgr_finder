import copy
import json
import urllib.parse
from abc import ABC, abstractmethod

from qgis.core import (Qgis, QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform, QgsNetworkAccessManager,
                       QgsPointXY, QgsProject, QgsSettings)
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.utils import iface

from .utils.logger import Logger

Log = Logger()

class APIQueryStrategy(ABC):
    source = None

    @abstractmethod
    def query(self, selected_tags, x_min, y_min, x_max, y_max):
        pass

    @abstractmethod
    def extractElements(self, data):
        pass

    @abstractmethod
    def getAttributeMappings(self):
        pass

    @abstractmethod
    def extractLatLon(self, element):
        pass

    @abstractmethod
    def getGeometryType(self, element):
        pass

    def transformTo4326(self, x, y):
        if x is not None and y is not None:
            project = QgsProject.instance()
            project_crs = project.crs()
            target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(project_crs, target_crs, project)
            pt = QgsPointXY(x, y)
            pt = transform.transform(pt)
            return pt.x(), pt.y()
        return None, None

    def transformCoordinates(self, x, y):
        if x is not None and y is not None:
            project = QgsProject.instance()
            api_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            target_crs = QgsProject.instance().crs()
            transform = QgsCoordinateTransform(api_crs, target_crs, project)
            pt = QgsPointXY(x, y)
            pt = transform.transform(pt)
            return pt.y(), pt.x()
        return None, None


class OverpassAPIQueryStrategy(APIQueryStrategy):
    source = "Open Street Map"

    def restructure_data(self, new_data):
        nodes = {
            element["id"]: (element["lat"], element["lon"])
            for element in new_data["elements"]
            if element["type"] == "node"
        }
        ways = {
            element["id"]: element
            for element in new_data["elements"]
            if element["type"] == "way"
        }

        # Build a set of all possible node IDs of all ways
        possible_node_ids = set()
        for way_id, node_ids in ways.items():
            possible_node_ids.update(node_ids["nodes"])

        # Filter out nodes where their ID is not in the list of possible node IDs
        new_data["elements"] = [
            element
            for element in new_data["elements"]
            if element["type"] != "node" or element["id"] not in possible_node_ids
        ]

        # Move nodes under the corresponding way element
        for way_id, node_ids in ways.items():
            way_nodes = [
                ({"lon": nodes[node_id][1], "lat": nodes[node_id][0]})
                for node_id in node_ids["nodes"]
                if node_id in nodes
            ]
            ways[way_id]["nodes"] = way_nodes

        return new_data

    def query(self, x_min, y_min, x_max, y_max):
        x_min, y_min = self.transformTo4326(x_min, y_min)
        x_max, y_max = self.transformTo4326(x_max, y_max)

        selected_cultural_tags = QgsSettings().value("/KgrFinder/osm_tags", [])
        custom_osm_tags = QgsSettings().value("/KgrFinder/custom_osm_tags", [])
        selected_tags = selected_cultural_tags + custom_osm_tags

        overpass_query = self.createOverpassQuery(
            selected_tags, x_min, y_min, x_max, y_max
        )

        url = f"https://overpass-api.de/api/interpreter?data={overpass_query}"
        Log.log_debug(f"called url {url}")

        request = QNetworkRequest(QUrl(url))
        reply = QgsNetworkAccessManager.instance().blockingGet(request)

        if reply.error():
            if reply.errorString():
                Log.log_error(reply.errorString())

        if reply.content():
            data = str(reply.content(), "utf-8")
            data = json.loads(data)
            new_data = copy.deepcopy(data)
            new_data = self.restructure_data(new_data)
            return new_data

        return None

    def createOverpassQuery(self, tags, x_min, y_min, x_max, y_max):
        overpass_query = "[out:json];("

        for search_term in tags:
            key, sep, value = search_term.partition("=")
            key, value = [f"'{value}'" if value else "" for value in (key, value)]

            query = f"node[{key}{sep}{value}]({y_min},{x_min},{y_max},{x_max});"
            query += f"way[{key}{sep}{value}]({y_min},{x_min},{y_max},{x_max});>;"
            # query += f'relation["{tag}"]({y_min},{x_min},{y_max},{x_max});'
            overpass_query += query

        overpass_query += ");out;"
        return overpass_query

    def getAttributeMappings(self):
        return {
            "name": "tags.name",
            "description": "tags.description",
            "type": "type",
            "id": "id",
            "tags": "tags",
            "lat": "lat",
            "lon": "lon"
        }

    def extractElements(self, data):
        if not data:
            return []
        # Extract elements from the Overpass API response
        return data.get("elements", [])

    def extractLatLon(self, element):
        lat = element.get("lat")
        lon = element.get("lon")
        if lon is not None and lat is not None:
            lat, lon = self.transformCoordinates(lon, lat)
            return lat, lon
        else:
            return None, None

    def extractPolygonNodes(self, element):
        nodes = element.get("nodes")
        if (
            nodes is not None and len(nodes) >= 2
        ):  # Make sure there are at least 3 nodes to form a polygon
            coordinates = [(node["lon"], node["lat"]) for node in nodes]
            transformed_coordinates = [
                self.transformCoordinates(lat, lon) for lat, lon in coordinates
            ]  # Switched lat and lon
            transformed_points = [
                QgsPointXY(lon, lat) for lat, lon in transformed_coordinates
            ]  # Switched lon and lat
            return transformed_points
        else:
            return None

    def getGeometryType(self, element):
        if element["type"] == "node":
            return "point"
        elif element["type"] == "way":
            return "polygon"
        else:
            return "unknown"


class iDAIGazetteerAPIQueryStrategy(APIQueryStrategy):
    source = "iDAI.Gazetteer"

    def query(self, x_min, y_min, x_max, y_max):
        x_min, y_min = self.transformTo4326(x_min, y_min)
        x_max, y_max = self.transformTo4326(x_max, y_max)

        idai_gazetteer_filter = QgsSettings().value("/KgrFinder/idai_gazetteer_filter", "None")
        custom_gazetteer_tags = QgsSettings().value("/KgrFinder/custom_gazetteer_tags", [])

        BASE_URL = "https://gazetteer.dainst.org/search.json?q="

        options = ""

        # Build idai_gazetteer_filter_str
        idai_gazetteer_filter_str = '{"match":{"types":"'+idai_gazetteer_filter+'"}}' if idai_gazetteer_filter != "None" else ""

        # Build idai_gazetteer_custom_tags_str
        idai_gazetteer_custom_tags_str = ', '.join(['{"match":{"tags":"'+tag+'"}}' for tag in custom_gazetteer_tags])

        # Combine filter and custom tags if both are present
        if idai_gazetteer_filter_str and idai_gazetteer_custom_tags_str:
            idai_gazetteer_filter_str += ','

        # Construct the options JSON string
        options = '{"bool":{"must":['+idai_gazetteer_filter_str+idai_gazetteer_custom_tags_str+']}}'
        options = urllib.parse.quote_plus(options)
        
        url = BASE_URL + options
        q_string = "&fq=_exists_:prefLocation.coordinates OR _exists_:prefLocation.shape"
        q_string += "&polygonFilterCoordinates="
        q_string += f'{x_min}&polygonFilterCoordinates={y_min}&polygonFilterCoordinates={x_max}+'
        q_string += f'&polygonFilterCoordinates={y_min}&polygonFilterCoordinates={x_max}&polygonFilterCoordinates={y_max}'
        q_string += f'&polygonFilterCoordinates={x_min}&polygonFilterCoordinates={y_max}'
        q_string += "&limit=1000&type=extended&pretty=true"
        url = url + q_string
        
        request = QNetworkRequest(QUrl(url))
        Log.log_debug(f"called url {url}")
        reply = QgsNetworkAccessManager.instance().blockingGet(request)

        if reply.error():
            if reply.errorString():
                Log.log_debug(reply.errorString())
                iface.messageBar().pushMessage(
                    "KGR", reply.errorString(), level=Qgis.Critical, duration=3
                )

        if reply.content():
            data = str(reply.content(), "utf-8")
            data = json.loads(data)
            new_data = copy.deepcopy(data)
            return new_data

        return None

    def getAttributeMappings(self):
        return {
            'name': 'prefName.title',
            # 'description': 'types',
            'type': 'types',
            "id": "@id",
            # 'tags': 'tags',
            "lat": "prefLocation.coordinates[1]",
            "lon": "prefLocation.coordinates[0]",
        }

    def extractElements(self, data):
        if not data:
            return []
        # Extract elements from the Overpass API response
        return data.get("result", [])

    def extractPolygonNodes(self, element):
        def recursive_extract_coordinates(shape):
            coordinates = []
            if isinstance(shape, list):
                if (
                    len(shape) == 2
                    and isinstance(shape[0], (int, float))
                    and isinstance(shape[1], (int, float))
                ):
                    return [(shape[0], shape[1])]  # Assuming it's a coordinate pair
                else:
                    for sub_shape in shape:
                        coordinates.extend(recursive_extract_coordinates(sub_shape))
            return coordinates

        shape = element.get("prefLocation", {}).get("shape", [])

        if shape is not None:
            coordinates = recursive_extract_coordinates(shape)

            if coordinates:
                transformed_coordinates = [
                    self.transformCoordinates(lon, lat) for lon, lat in coordinates
                ]
                transformed_points = [
                    QgsPointXY(lon, lat) for lat, lon in transformed_coordinates
                ]
                return transformed_points

        return None

    def extractLatLon(self, element):
        pref_location = element.get("prefLocation", {})
        coordinates = pref_location.get("coordinates", [])

        if len(coordinates) == 2:
            lat = coordinates[1]
            lon = coordinates[0]
            lat, lon = self.transformCoordinates(lon, lat)
            return lat, lon
        else:
            return None, None

    def getGeometryType(self, element):
        coordinates = element.get("prefLocation", {}).get("coordinates", [])
        shape = element.get("prefLocation", {}).get("shape", [])
        if shape:
            return "polygon"
        elif len(coordinates) == 2:
            return "point"
        else:
            return "unknown"
