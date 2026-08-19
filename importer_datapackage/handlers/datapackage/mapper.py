import logging
from pathlib import Path
from collections.abc import Callable

import xml.etree.cElementTree as ET

logger = logging.getLogger(__name__)

class TabularDataHelper():

    def __init__(self, package, fixup_name: Callable):
        self.package = package
        self.resources = package.resources or []
        self.fixup_name = fixup_name
        
    
    def parse_attribute_map(self, resource_name: str) -> list:
        """
        The datapackage schema in the shape GeoNode's Attribute table expects:
        [ [field, ftype, description, label, display_order], ... ]

        ftype is the XSD type GeoNode stores in Attribute.attribute_type - the
        same one it would otherwise read back from GeoServer's WFS
        DescribeFeatureType - derived from the very OGR type we write into the
        VRT, so the declared type cannot drift from the imported column.
        """

        resource = self._find_resource(resource_name)
        schema = resource.schema
        attribute_map = [
            [self.fixup_name(field.name), _xsd_field_type(field), field.description, field.title or field.name, index]
            for index, field in enumerate(schema.fields)
        ]
        return attribute_map

    def _find_resource(self, resource_name: str):
        """Find a resource by name, falling back to normalized-name matching."""
        try:
            resource = self.package.get_resource(resource_name)
        except Exception:
            resource = None
        if resource is not None:
            return resource

        normalized_target = (resource_name or "").strip().lower()
        for package_resource in self.resources:
            original_name = (package_resource.name or "").strip().lower()
            normalized_name = self.fixup_name(package_resource.name)
            if original_name == normalized_target or normalized_name == normalized_target:
                return package_resource

        raise LookupError(f'Resource "{resource_name}" does not exist in datapackage')

    def write_vrt_file(self, filename: str, folder: Path):
        
        if not filename:
            raise Exception("filename is missing")
        
        root = ET.Element("OGRVRTDataSource")
        for resource in self.resources:
            layer = ET.SubElement(root, "OGRVRTLayer", name=resource.name)
            source = Path(folder, resource.path) if folder else resource.path
            ET.SubElement(layer, "SrcDataSource").text = str(source)

            # Without this, GDAL falls back to matching the VRT layer's own
            # "name" against the underlying CSV's layer name (its filename
            # without extension). If a resource's declared name differs from
            # its CSV file's basename, that lookup silently fails and the
            # layer imports with zero features - no error anywhere.
            ET.SubElement(layer, "SrcLayer").text = Path(source).stem

            # Without this, an empty CSV cell for a numeric (Integer/Real) field
            # is cast to 0 instead of NULL by GDAL's VRT driver, silently turning
            # missing values into real data. Date/DateTime fields are unaffected.
            open_options = ET.SubElement(layer, "OpenOptions")
            ET.SubElement(open_options, "OOI", key="EMPTY_STRING_AS_NULL").text = "YES"

            ET.SubElement(layer, "GeometryType").text = "wkbNone"
            ET.SubElement(layer, "LayerSRS").text = "EPSG:4326"
            ET.SubElement(layer, "ExtentXMin").text = "-180"
            ET.SubElement(layer, "ExtentYMin").text = "-90"
            ET.SubElement(layer, "ExtentXMax").text = "180"
            ET.SubElement(layer, "ExtentYMax").text = "90"

            schema = resource.schema
            for field in schema.fields:
                (type, subtype) = _parse_field_type(field)
                normalized_fieldname = self.fixup_name(field.name)

                attrib = {
                    "src": field.name or "",
                    "name": normalized_fieldname or "",
                    # "alternativeName": field.title or "", # GDAL >=3.7
                    # "comment": field.description or "", # GDAL >=3.7
                    "type": type,
                }
                if subtype:
                    attrib["subtype"] = subtype
                ET.SubElement(layer, "Field", **attrib)

        # write VRT file
        vrt_filename = Path(folder, filename) if folder else filename
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        try:
            with open(vrt_filename, "wb") as f:
                tree.write(f, encoding="UTF-8")
        except TypeError:
            logger.error(f"Could not create VRT file '{vrt_filename}'", exc_info=True)

        return vrt_filename


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

    subtype = None
    return (type, subtype)


# OGR field type (see _parse_field_type) -> the XSD type GeoServer reports for
# the PostGIS column ogr2ogr creates from it.
_OGR_TO_XSD_TYPE = {
    "String": "xsd:string",
    "Integer": "xsd:int",
    "Real": "xsd:double",
    "Date": "xsd:date",
    "Time": "xsd:time",
    "DateTime": "xsd:dateTime",
}


def _xsd_field_type(field) -> str:
    (type, _) = _parse_field_type(field)
    return _OGR_TO_XSD_TYPE.get(type, "xsd:string")
