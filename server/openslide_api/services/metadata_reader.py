from lxml import etree
from pylibCZIrw import czi as pyczi

def find_metadata_keys(czi_file_path, keys):
    if isinstance(keys, str):
        keys = [keys]

    results = {}
    with pyczi.open_czi(czi_file_path) as czidoc:
        md_xmlstring = czidoc.raw_metadata
        md_xmlroot = etree.fromstring(md_xmlstring)

        for key in keys:
            element = md_xmlroot.find(f'.//{key}')
            results[key] = element.text if element is not None else None

    return results
