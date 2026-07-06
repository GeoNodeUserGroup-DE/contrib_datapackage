import logging
import xml.etree.cElementTree as ET
from collections.abc import Callable
from pathlib import Path


logger = logging.getLogger(__name__)


class TabularDataHelper:
    def __init__(self, package, fixup_name: Callable):
        self.package = package
        self.resources = package.resources or []
        self.fixup_name = fixup_name

    def parse_attribute_map(self, resource_name: str) -> list:
        resource = self._find_resource(resource_name)
        schema = resource.schema
        return [
            [
                self.fixup_name(field.name),
                _parse_field_type(field)[0],
                field.description,
                field.title or field.name,
                index,
            ]
            for index, field in enumerate(schema.fields)
        ]

    def _find_resource(self, resource_name: str):
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
            raise ValueError("filename is missing")

        root = ET.Element("OGRVRTDataSource")
        for resource in self.resources:
            layer = ET.SubElement(root, "OGRVRTLayer", name=resource.name)
            source = Path(folder, resource.path) if folder else resource.path
            ET.SubElement(layer, "SrcDataSource").text = str(source)
            ET.SubElement(layer, "GeometryType").text = "wkbNone"
            ET.SubElement(layer, "LayerSRS").text = "EPSG:4326"
            ET.SubElement(layer, "ExtentXMin").text = "-180"
            ET.SubElement(layer, "ExtentYMin").text = "-90"
            ET.SubElement(layer, "ExtentXMax").text = "180"
            ET.SubElement(layer, "ExtentYMax").text = "90"

            for field in resource.schema.fields:
                field_type, subtype = _parse_field_type(field)
                ET.SubElement(
                    layer,
                    "Field",
                    src=field.name or "",
                    name=self.fixup_name(field.name) or "",
                    type=field_type,
                    subtype=subtype,
                )

        vrt_filename = Path(folder, filename) if folder else Path(filename)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        try:
            with open(vrt_filename, "wb") as stream:
                tree.write(stream, encoding="UTF-8")
        except (TypeError, OSError):
            logger.exception("Could not create VRT file '%s'", vrt_filename)
            raise

        return vrt_filename


def _parse_field_type(field) -> tuple[str, str]:
    if not field.type:
        return "String", "None"

    mapping = {
        "number": "Real",
        "integer": "Integer",
        "string": "String",
        "date": "Date",
        "time": "Time",
        "datetime": "DateTime",
    }
    return mapping.get(field.type, "String"), "None"
