import czifile
from lxml import etree
import json

def list_czi_metadata(file_path, output_json=None):
    with czifile.CziFile(file_path) as czi:
        czi_xml_str = czi.metadata()
        czi_parsed = etree.fromstring(czi_xml_str)

        def xml_to_dict(element):
            children = list(element)
            if not children:
                return element.text.strip() if element.text else None
            result = {}
            for child in children:
                child_result = xml_to_dict(child)
                if child.tag not in result:
                    result[child.tag] = child_result
                else:
                    if isinstance(result[child.tag], list):
                        result[child.tag].append(child_result)
                    else:
                        result[child.tag] = [result[child.tag], child_result]
            return result

        czi_dict = xml_to_dict(czi_parsed)

        if output_json:
            with open(output_json, 'w') as json_file:
                json.dump(czi_dict, json_file, indent=4)

        return czi_dict
