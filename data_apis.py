import requests
from qgis.core import QgsSettings
from abc import ABC, abstractmethod
from qgis.core import QgsCoordinateTransform, QgsProject, QgsCoordinateReferenceSystem, QgsPointXY
from qgis.core import Qgis
from qgis.utils import iface
import json
import copy


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

            # print("transformTo4326 vorher: ", x, y)


            project = QgsProject.instance()
            project_crs = project.crs()
            target_crs = QgsCoordinateReferenceSystem('EPSG:4326')
            transform = QgsCoordinateTransform(project_crs, target_crs, project)
            pt = QgsPointXY(x, y)
            pt = transform.transform(pt)

            # print("transformTo4326 nachher: ", pt.x(), pt.y())

            return pt.x(), pt.y()

    def transformCoordinates(self, x, y):
        # print("here is transformCoordinates")
        # print("got ", x, y)
        if x is not None and y is not None:

            # print("transformCoordinates vorher: ", x, y)

            project = QgsProject.instance()
            api_crs = QgsCoordinateReferenceSystem('EPSG:4326')

            # Create the coordinate transform
            target_crs = QgsProject.instance().crs()
            transform = QgsCoordinateTransform(api_crs, target_crs, project)
            
            # Apply the transformation
            pt = QgsPointXY(x, y)
            pt = transform.transform(pt)

            # print("transformCoordinates nachher: ", pt.x(), pt.y())

            return pt.y(), pt.x()
        else:
            return None, None


class OverpassAPIQueryStrategy(APIQueryStrategy):
    source = 'osm'

    def restructure_data(self, new_data):
        nodes = {element['id']: (element['lat'], element['lon']) for element in new_data['elements'] if element['type'] == 'node'}
        ways = {element['id']: element for element in new_data['elements'] if element['type'] == 'way'}

        # Build a set of all possible node IDs of all ways
        possible_node_ids = set()
        for way_id, node_ids in ways.items():
            possible_node_ids.update(node_ids['nodes'])

        # Filter out nodes where their ID is not in the list of possible node IDs
        new_data['elements'] = [element for element in new_data['elements'] if element['type'] != 'node' or element['id'] not in possible_node_ids]

        # Move nodes under the corresponding way element
        for way_id, node_ids in ways.items():
            way_nodes = [({"lon": nodes[node_id][1], "lat": nodes[node_id][0]}) for node_id in node_ids['nodes'] if node_id in nodes]
            ways[way_id]['nodes'] = way_nodes

        return new_data



    def query(self, x_min, y_min, x_max, y_max):
        x_min, y_min = self.transformTo4326(x_min, y_min)
        x_max, y_max = self.transformTo4326(x_max, y_max)

        selected_cultural_tags = QgsSettings().value("/FindOSMData/osm_tags", [])
        overpass_query = self.createOverpassQuery(selected_cultural_tags, x_min, y_min, x_max, y_max)

        try:
            response = requests.get("https://overpass-api.de/api/interpreter", params={'data': overpass_query})
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx and 5xx)
            data = response.json()

            # print("originanal data is")
            # print(data)

            new_data = copy.deepcopy(data)
            new_data = self.restructure_data(new_data)
            # print("new_data is")
            # print(json.dumps(new_data, indent=4))
            return new_data
            
            return data

        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            iface.messageBar().pushMessage("KGR", "Error in Overpass API Communication", level=Qgis.Critical, duration=3)

        except Exception as err:
            iface.messageBar().pushMessage("KGR", "Error in Overpass API Communication", level=Qgis.Critical, duration=3)
            print(f"An error occurred: {err}")

        return None  # Return None in case of an error

    def createOverpassQuery(self, tags, x_min, y_min, x_max, y_max):
        overpass_query = "[out:json];("

        for search_term in tags:

            key, sep, value = search_term.partition('=')
            key, value = [f"'{value}'" if value else '' for value in ( key, value)]
           
            print( key, sep, value )

            query = f'node[{key}{sep}{value}]({y_min},{x_min},{y_max},{x_max});'
            query += f'way[{key}{sep}{value}]({y_min},{x_min},{y_max},{x_max});>;'
            # query += f'relation["{tag}"]({y_min},{x_min},{y_max},{x_max});'
            overpass_query += query

        overpass_query += ");out;"
        return overpass_query

    def getAttributeMappings(self):
        return {
            'name': 'tags.name',
            'description': 'tags.description',
            'type': 'type',
            'id': 'id',
            'tags': 'tags',
            'building': 'tags.building',
        }

    def extractElements(self, data):
        # Extract elements from the Overpass API response
        return data.get('elements', [])

    def extractLatLon(self, element):
        lat = element.get('lat')
        lon = element.get('lon')
        if lon is not None and lat is not None:
            lat, lon = self.transformCoordinates(lon, lat)
            return lat, lon
        else:
            return None, None

    def extractPolygonNodes(self, element):
        nodes = element.get("nodes")
        if nodes is not None and len(nodes) >= 2:  # Make sure there are at least 3 nodes to form a polygon
            coordinates = [(node["lon"], node["lat"]) for node in nodes]  
            transformed_coordinates = [self.transformCoordinates(lat, lon) for lat, lon in coordinates]  # Switched lat and lon
            transformed_points = [QgsPointXY(lon, lat) for lat, lon in transformed_coordinates]  # Switched lon and lat
            return transformed_points
        else:
            return None  

    def getGeometryType(self, element):
        if element['type'] == 'node':
            return 'point'
        elif element['type'] == 'way':
            return 'polygon'
        else:
            return 'unknown'

class iDAIGazetteerAPIQueryStrategy(APIQueryStrategy):
    source = 'DAI'
  
    def query(self, x_min, y_min, x_max, y_max):
        x_min, y_min = self.transformTo4326(x_min, y_min)
        x_max, y_max = self.transformTo4326(x_max, y_max)

        try:
            # Construct the query URL
            gazeteer_url = f"https://gazetteer.dainst.org/search.json?q=%7B%22bool%22%3A%7B%22must%22%3A%5B%7B%22match%22%3A%7B%22types%22%3A%22archaeological-site%22%7D%7D%5D%7D%7D&fq=_exists_:prefLocation.coordinates%20OR%20_exists_:prefLocation.shape&polygonFilterCoordinates={x_min}&polygonFilterCoordinates={y_min}&polygonFilterCoordinates={x_max}&polygonFilterCoordinates={y_min}&polygonFilterCoordinates={x_max}&polygonFilterCoordinates={y_max}&polygonFilterCoordinates={x_min}&polygonFilterCoordinates={y_max}&limit=1000&type=extended&pretty=true"

            response = requests.get(gazeteer_url)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx and 5xx)
            data = response.json()
            print(json.dumps(data, indent=4))
            return data
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            iface.messageBar().pushMessage("KGR", "Error in DAI API Communication", level=Qgis.Critical, duration=3)

        except Exception as err:
            iface.messageBar().pushMessage("KGR", "Error in DAI API Communication", level=Qgis.Critical, duration=3)
            print(f"An error occurred: {err}")

        return None  # Return None in case of an error

    def getAttributeMappings(self):
        return {
            'source': 'dai',
            # 'name': 'tags.name',
            # 'description': 'tags.description',
            # 'type': 'type',
            'id': '@id',
            # 'tags': 'tags',
            # 'building': 'tags.building'
        }

    def extractElements(self, data):
        if not data: 
            return None
        # Extract elements from the Overpass API response
        return data.get('result', [])

    def extractPolygonNodes(self, element):
        def recursive_extract_coordinates(shape):
            coordinates = []
            if isinstance(shape, list):
                if len(shape) == 2 and isinstance(shape[0], (int, float)) and isinstance(shape[1], (int, float)):
                    return [(shape[0], shape[1])]  # Assuming it's a coordinate pair
                else:
                    for sub_shape in shape:
                        coordinates.extend(recursive_extract_coordinates(sub_shape))
            return coordinates

        shape = element.get('prefLocation', {}).get('shape', [])

        if shape is not None:
            coordinates = recursive_extract_coordinates(shape)
            
            if coordinates:
                transformed_coordinates = [self.transformCoordinates(lon, lat) for lon, lat in coordinates]
                transformed_points = [QgsPointXY(lon, lat) for lat, lon in transformed_coordinates]
                return transformed_points
                
        return None


    def extractLatLon(self, element):
        pref_location = element.get('prefLocation', {})
        coordinates = pref_location.get('coordinates', [])
        
        if len(coordinates) == 2:
            lat = coordinates[1]
            lon = coordinates[0]
            lat, lon = self.transformCoordinates(lon, lat)
            return lat, lon
        else:
            return None, None

    def getGeometryType(self, element):
        coordinates = element.get('prefLocation', {}).get('coordinates', [])
        shape = element.get('prefLocation', {}).get('shape', [])
        if shape:
             return 'polygon'
        elif len(coordinates) == 2:
            return 'point'
        else:
            return 'unknown'