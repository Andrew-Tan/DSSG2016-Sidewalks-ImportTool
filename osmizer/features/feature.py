import copy

import click
import jsonschema
from rtree import index
from collections import OrderedDict

# import lxml etree
try:
    from lxml import etree

    print('running with lxml.etree')
except ImportError:
    try:
        # Python 2.5
        import xml.etree.cElementTree as etree

        print('running with cElementTree on Python 2.5+')
    except ImportError:
        try:
            # Python 2.5
            import xml.etree.ElementTree as etree

            print('running with ElementTree on Python 2.5+')
        except ImportError:
            try:
                # normal cElementTree install
                import cElementTree as etree

                print('running with cElementTree')
            except ImportError:
                try:
                    # normal ElementTree install
                    import elementtree.ElementTree as etree

                    print('running with ElementTree')
                except ImportError:
                    print('Failed to import ElementTree from any known place')


class Feature:
    def __init__(self, json_database=None, schema=None):
        '''
        Load input json object and schema object

        :param json_database: the input json object
        :param schema: the schema json object
        '''
        self.json_database = json_database
        self.schema = schema

    def validate(self):
        '''
        Validate JSON input according to the schema

        :return: a boolean indicates if the input JSON match the schema
        '''
        if self.json_database is None or self.schema is None:
            raise ValueError('JSON input or schema not found')

        json_copy = copy.deepcopy(self.json_database)
        try:
            jsonschema.validate(json_copy, self.schema)
        except jsonschema.ValidationError as err:
            click.echo('Input JSON fail to match schema')
            click.echo('Error:\n')
            click.echo(err)
            return False
        except Exception as e:
            click.echo('Unexpected error: ', e)
            return False

        return True

    def convert(self):
        raise NotImplementedError('Implement convert before use')

    @staticmethod
    def __node_common_attribute__(node):
        '''
        Add common attributes for a node

        :param node: the node
        :return: None
        '''
        node.attrib['visible'] = 'true'

    @staticmethod
    def __way_common_attribute__(way):
        '''
        Add common attributes for a way

        :param node: the node
        :return: None
        '''
        way.attrib['action'] = 'modify'
        way.attrib['visible'] = 'true'

    @staticmethod
    def add_header(osm_xml_dom_root):
        '''
        Add additional information as header in osm node

        :param osm_xml_dom_root: the dom (WILL BE Modified)
        :return: None
        '''
        osm_xml_dom_root.attrib['version'] = str(0.6)
        osm_xml_dom_root.attrib['generator'] = 'OpenSidewalks Data Import Tool'

    @staticmethod
    def dedup(xml_dom, tolerance):
        '''Merge nodes which are duplicate in a DOM tree.

        :param xml_dom: the DOM tree whose nodes need to be merged.
        :param tolerance: how close (in degree) should the algorithm consider
                          one node is a duplicate of another.
        :return: a DOM tree whose duplicates are merged.

        '''
        # Sort out all nodes
        nodes_rtree = index.Index()
        nodes_dict = OrderedDict()

        for child in list(xml_dom):
            if child.tag == 'node' and ('lon' and 'lat') in child.attrib:
                child_id = int(child.attrib['id'])
                left = float(child.attrib['lon'])
                right = left
                bottom = float(child.attrib['lat'])
                top = bottom
                coordinate = (left, bottom, right, top)
                nodes_rtree.insert(child_id, coordinate, obj=coordinate)
                nodes_dict[child_id] = child
                # nodes.append(child)
                # OrderedDict consider

        while len(nodes_dict) > 0:
            # Pop next item
            current_pair = nodes_dict.popitem()
            to_id = current_pair[0]
            to_node = current_pair[1]

            left = float(to_node.attrib['lon'])
            right = left
            bottom = float(to_node.attrib['lat'])
            top = bottom

            # Remove from RTree
            nodes_rtree.delete(to_id, (left, bottom, right, top))

            tolerance_half = tolerance / 2.0
            bounding_box = (left - tolerance_half,
                            bottom - tolerance_half,
                            right + tolerance_half,
                            top + tolerance_half)

            hits = nodes_rtree.intersection(bounding_box, objects=True)
            from_ids = []
            for i in hits:
                from_id = i.id
                from_node = nodes_dict[from_id]
                # Remove from DOM
                from_node.getparent().remove(from_node)
                # Remove from RTree
                nodes_rtree.delete(from_id, i.object)
                # Pop from Dictionary
                nodes_dict.pop(from_id)
                # Add to from iDs list
                from_ids.append(from_id)
            Feature.__recursive_substitute_nd_id__(xml_dom, from_ids, to_id)

        return xml_dom

    @staticmethod
    def __can_group__(node_1, node_2, tolerance) -> bool:
        '''Decide if two nodes can be grouped(and be merged later).

        :param node_1: a node.
        :param node_2: another node.
        :param tolerance: how close (in degree) should the algorithm consider
                          one node is a duplicate of another.
        :return: a boolean indicates if two nodes can be grouped.
        '''
        # FIXME: shouldn't use special methods
        node_1_lon = node_1.attrib['lon']
        node_1_lat = node_1.attrib['lat']
        node_2_lon = node_1.attrib['lon']
        node_2_lat = node_2.attrib['lat']

        lon_diff = Feature.__distance__(node_1_lon, node_2_lon)
        lat_diff = Feature.__distance__(node_1_lat, node_2_lat)
        if lon_diff <= tolerance and lat_diff <= tolerance:
            return True
        else:
            return False

    @staticmethod
    def __distance__(num1, num2) -> float:
        '''Calculate distance of two numbers.

        :param num1: a number, do not necessarily have to be a number type.
        :param num2: another number, do not necessarily have to be a number
                     type.
        :return: a float of their distance.

        '''
        return abs(float(num1) - float(num2))

    @staticmethod
    def __substitute_nd_id__(xml_dom, from_nodes, to_node):
        '''Search through a DOM tree and merge a node.

        :param xml_dom: the DOM tree.
        :param to_node: the node that substitute_node is to be
                                    merged to.
        :param from_nodes: the node to be merged to representative_node.
        :return:

        '''
        to_id = to_node.attrib['id']
        from_ids = []
        for from_node in from_nodes:
            from_ids.append(from_node.attrib['id'])
        Feature.__recursive_substitute_nd_id__(xml_dom, from_ids, to_id)

        for from_node in from_nodes:
            from_node.getparent().remove(from_node)

    @staticmethod
    def __recursive_substitute_nd_id__(dom_member, from_ids, to_id):
        '''Recursive function which search through a DOM member and substitute
        the id.

        :param dom_member: a member of the DOM tree.
        :param to_id: The id of the node that substitute_id is to be merged to.
        :param from_id: The id of the node to be merged to representative_id.
        :return:

        '''
        if dom_member.tag == 'nd':
            if dom_member.attrib['ref'] in from_ids:
                dom_member.attrib['ref'] = to_id
            return

        for child in dom_member.getchildren():
            Feature.__recursive_substitute_nd_id__(child, from_ids, to_id)

    @staticmethod
    def merge(files_in):
        '''Merge two OSM XML files into one.

        :param files_in: an array(tuple) of file paths which refer to the files
                         to be merged.
        :return: a DOM object which contains all data in files_in.

        '''
        if len(files_in) < 1:
            click.echo('ERROR: No file input')
            return None
        first_load = True
        merged_dom = None
        parse_dom = None
        for file in files_in:
            parse_dom = Feature.__parse_xml_file__(file)

            if parse_dom is None:
                return None

            if first_load:
                first_load = False
                merged_dom = parse_dom
            else:
                Feature.__merge_doms__(merged_dom, parse_dom)
        return merged_dom

    @staticmethod
    def __parse_xml_file__(file_path):
        '''parse xml file to a DOM object from file, handle errors that might
        occur.

        :param file_path: the file path(string) to the import xml file.
        :return: a XML DOM object or None if any error occurs.

        '''
        parser = etree.XMLParser(encoding='utf-8', huge_tree=True)
        try:
            tree = etree.parse(file_path, parser)
        except etree.XMLSyntaxError:
            click.echo('Error occur while parsing XML file: %s' % file_path)
            for error in parser.error_log:
                click.echo(error.message)
            return None
        except Exception as e:
            click.echo('Unexpected Error: ', e)
            return None

        elt = etree.fromstring(etree.tostring(tree.getroot()))

        if Feature.__check_headers__(elt):
            return elt
        else:
            click.echo('Incorrect Header for file: %s' % file_path)
            return None

    @staticmethod
    def __check_headers__(dom_tree):
        '''Check whether the parsed XML DOM object have correct headers,
        including version and generator attributes.

        :param dom_tree: the XML DOM to be checked.
        :return: a boolean indicating whether the check is passed.

        '''
        root = dom_tree
        if root.tag != 'osm':
            return False

        root_attribs = root.attrib

        if root_attribs['version'] != '0.6':
            return False
        if root_attribs['generator'] != 'OpenSidewalks Data Import Tool':
            return False

        return True

    @staticmethod
    def __merge_doms__(target_dom, source_dom):
        '''Merge a DOM from another DOM

        :param target_dom: The DOM to be merged (This DOM tree WILL BE
                           modified).
        :param source_dom: Another DOM providing additional data set.
        :return: None

        '''
        for node in source_dom.findall('./'):
            target_dom.append(node)

    @staticmethod
    def to_xml(xml_dom, output_path):
        '''Export the DOM tree to file.

        :param xml_dom: the DOM tree which is to be exported.
        :param output_path: the path of the exported file.
        :return: a boolean indicates if the export progress is successful.

        '''
        et = etree.ElementTree(xml_dom)
        et.write(output_path, pretty_print=True, xml_declaration=True,
                 encoding='utf-8')
        return True