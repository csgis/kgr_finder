import requests
from qgis.core import QgsSettings
from abc import ABC, abstractmethod
from qgis.core import QgsCoordinateTransform, QgsProject, QgsCoordinateReferenceSystem, QgsPointXY

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



class OverpassAPIQueryStrategy(APIQueryStrategy):
    source = 'osm'

    def query(self, x_min, y_min, x_max, y_max):
        selected_cultural_tags = QgsSettings().value("/FindOSMData/cultural_tags", [])
        overpass_query = self.createOverpassQuery(selected_cultural_tags, x_min, y_min, x_max, y_max)
        
        response = requests.get("https://overpass-api.de/api/interpreter", params={'data': overpass_query})
        data = response.json()

        return data

    def createOverpassQuery(self, tags, x_min, y_min, x_max, y_max):
        overpass_query = "[out:json];\n("

        for tag in tags:
            query = f'node["{tag}"]({y_min},{x_min},{y_max},{x_max});'

            query += f'way["{tag}"]({y_min},{x_min},{y_max},{x_max});'
            query += f'relation["{tag}"]({y_min},{x_min},{y_max},{x_max});'
            overpass_query += query

        overpass_query += ");\nout center;\n"

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
        return lat, lon

    def getGeometryType(self, element):
        if element['type'] == 'node':
            return 'point'
        else:
            return 'unknown'

class iDAIGazetteerAPIQueryStrategy(APIQueryStrategy):
    source = 'DAI'
  
    def query(self, x_min, y_min, x_max, y_max):
        # Construct the query URL
        gazeteer_url = f"https://gazetteer.dainst.org/search.json?q=%7B%22bool%22%3A%7B%22must%22%3A%5B%7B%22match%22%3A%7B%22types%22%3A%22archaeological-site%22%7D%7D%5D%7D%7D&fq=_exists_:prefLocation.coordinates&polygonFilterCoordinates={x_min}&polygonFilterCoordinates={y_min}&polygonFilterCoordinates={x_max}&polygonFilterCoordinates={y_min}&polygonFilterCoordinates={x_max}&polygonFilterCoordinates={y_max}&polygonFilterCoordinates={x_min}&polygonFilterCoordinates={y_max}&limit=1000&type=extended&pretty=true"

        # Make the API request
        response = requests.get(gazeteer_url)
        data = response.json()

        return data

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
        # Extract elements from the Overpass API response
        return data.get('result', [])

    def extractLatLon(self, element):
        pref_location = element.get('prefLocation', {})
        coordinates = pref_location.get('coordinates', [])
        
        if len(coordinates) == 2:
            lat = coordinates[1]
            lon = coordinates[0]
            return lat, lon
        else:
            return None, None

    def getGeometryType(self, element):
        coordinates = element.get('prefLocation', {}).get('coordinates', [])
        if len(coordinates) == 2:
            return 'point'
        else:
            return 'unknown'