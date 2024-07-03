from pathlib import Path
from functools import reduce

import xml.etree.cElementTree as ET

class TabularDataHelper():

    def __init__(self, package):
        self.package = package
        self.resources = package.resources or []
        
    
    def parse_attribute_map(self, resource_name: str) -> list:
        """ Of type: [ [field, ftype, description, label, display_oder], ... ]"""
        
        resource = self.package.get_resource(resource_name)
        schema = resource.schema
        attribute_map = [
            [field.name, _parse_field_type(field)[0], field.description, field.title or field.name, None]
            for field in schema.fields
        ]
        return attribute_map
        
    def write_vrt_file(self, filename: str, folder: Path):
        
        if not filename:
            raise Exception("filename is missing")
        
        root = ET.Element("OGRVRTDataSource")
        for resource in self.resources:
            layer = ET.SubElement(root, "OGRVRTLayer", name=resource.name)
            source = Path(folder, resource.path) if folder else resource.path
            ET.SubElement(layer, "SrcDataSource").text = str(source)
            schema = resource.schema
            for field in schema.fields:
                (type, subtype) = _parse_field_type(field)
                normalized_fieldname = normalize(field.name).lower()
                ET.SubElement(layer, "Field", src=field.name, name=normalized_fieldname, type=type, subtype=subtype,)

        # write VRT file
        vrt_filename = Path(folder, filename) if folder else filename
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(vrt_filename)

        return vrt_filename

def normalize(fieldname):
    return fieldname.replace(" ", "_") if fieldname else fieldname
    

def _parse_field_type(field) -> tuple:

    # string -> String
    # number -> Real (precision?)
    # integer -> Integer
    # boolean (trueValues falseValues) -> String + subtype Boolean

    if not field.type:
        # String is the default 
        type = "String"
    else:
        if (field.type == "number"):
            type = "Real"
        elif (field.type == "integer"):
            type = "Integer"
        elif (field.type == "string"):
            type = "String"
        elif (field.type == "date"):
            type = "Date"
        elif (field.type == "time"):
            type = "Time"
        elif (field.type == "datetime"):
            type = "DateTime"
        else:
            # fallback
            type = "String"

    subtype = "None"
    return (type, subtype)
