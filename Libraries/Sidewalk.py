from Libraries import Feature
from Libraries.OSMIDGenerator import OSMIDGenerator
from lxml import etree


class Sidewalk(Feature.Feature):
    def __init__(self, sidewalks_json):
        schema_path = 'Schemas/Sidewalk_Schema.json'
        super().__init__(sidewalks_json, open(schema_path))

    def convert(self):
        """
        Convert sidewalks GeoJSON data to DOM tree, features may be duplicated due to the structure of JSON

        :return: a DOM tree structure which is equivalent to the sidewalks json database
        """
        dom_root = etree.Element('osm')
        id_generator = OSMIDGenerator()

        for elt in self.json_database['features']:
            if elt['geometry']['type'] == 'LineString':
                osm_way = etree.SubElement(dom_root, 'way')
                osm_way.attrib['id'] = str(id_generator.get_next())
                osm_way.attrib['user'] = 'TestUSER'
                osm_way.attrib['uid'] = '1'
                osm_way.attrib['visible'] = 'true'
                for coordinate in elt['geometry']['coordinates']:
                    osm_node = etree.SubElement(dom_root, 'node')
                    osm_node.attrib['id'] = str(id_generator.get_next())
                    osm_node.attrib['lon'] = str(coordinate[0])
                    osm_node.attrib['lat'] = str(coordinate[1])
                    osm_nd = etree.SubElement(osm_way, 'nd')
                    osm_nd.attrib['ref'] = osm_node.attrib['id']
                if elt['properties'] is not None:
                    for prop_key in elt['properties']:
                        osm_tag = etree.SubElement(osm_way, 'tag')
                        osm_tag.attrib['k'] = prop_key
                        osm_tag.attrib['v'] = str(elt['properties'][prop_key])

        return dom_root
