import unittest

from os import path
from unittest import TestCase
from tempfile import TemporaryDirectory

from frictionless import Package, validate
import xml.etree.cElementTree as ET

from subprocess import PIPE, Popen
from osgeo import ogr

from importer.handlers.datapackage.mapper import SchemaToVrtMapper

def _absolute_path(filename: str):
    script = path.abspath(__file__)
    return path.join(path.dirname(script), filename)

def write_vrtfile(dir, mapper): 
    vrt_file = path.join(dir, "test.vrt")
    return mapper.write_vrt_file(vrt_file)

class TestSchemaToVrtMapper(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.package = Package(_absolute_path("datapackage.json"))
        cls.mapper = SchemaToVrtMapper(cls.package)

    def test_write_vrt_file(self):
        with TemporaryDirectory() as tmp_dir:
            actual = write_vrtfile(tmp_dir, self.mapper)
            self.assertTrue(path.exists(actual))

    def test_field_mappings(self):
        with TemporaryDirectory() as tmp_dir:
            vrt_file = write_vrtfile(tmp_dir, self.mapper)
            
            tree = ET.parse(vrt_file)
            root = tree.getroot()
            self.assertEqual("OGRVRTDataSource", root.tag)
            for child in root:
                self.assertEqual("OGRVRTLayer", child.tag)
                self.assertIsNotNone(child.attrib["name"])
            

# def absolute_path(filename):
#     script = os.path.realpath(__file__)
#     return os.path.join(os.path.dirname(script), filename)


# def write_vrt_file(layername, resources, filename):
#     if not resources or not filename:
#         return
#     root = ET.Element("OGRVRTDataSource")
#     # unionLayer = ET.SubElement(root, "OGRVRTUnionLayer", name=layername)
#     # ET.SubElement(unionLayer, "FieldStrategy").text = "Intersection"
#     for resource in resources:
#         layer = ET.SubElement(root, "OGRVRTLayer", name=resource.name)
#         source = absolute_path(resource.path)
#         ET.SubElement(layer, "SrcDataSource").text = source
#         schema = resource.schema
#         for field in schema.fields:

#             # string -> String
#             # number -> Real (precision?)
#             # integer -> Integer
#             # boolean (trueValues falseValues) -> String + subtype Boolean

#             type = "Real" if field.type == "number" else "String"
#             ET.SubElement(layer, "Field", name=field.name, type=type)

#     tree = ET.ElementTree(root)
#     ET.indent(tree, space="  ")
#     tree.write(absolute_path(filename))


# filename = absolute_path("invalid_datapackage.json")

# report = validate(filename)
# if not report.valid:
#     raise Exception(f"invalid datapackage '{filename}': {report.error.message}")

# package = Package(filename)
# resources = package.resources

# layername = package.name
# vrt_filename = absolute_path(layername + ".vrt")
# write_vrt_file(layername, resources, vrt_filename)

# ogr_exe = "/usr/bin/ogr2ogr"
# options = ""  # "--config PG_USE_COPY YES "

# db_host = "db"
# db_port = 5432
# db_user = "postgres"
# db_password = "postgres"
# db_name = "geonode_data"
# options += (
#     "-f PostgreSQL PG:\" dbname='%s' host=%s port=%s user='%s' password='%s' \" "
#     % (db_name, db_host, db_port, db_user, db_password)
# )
# options += f"{vrt_filename}"

# commands = [ogr_exe] + options.split(" ")

# print(commands)
# process = Popen(" ".join(commands), stdout=PIPE, stderr=PIPE, shell=True)


# def normalize_ogr2ogr_error(err, original_name):
#     getting_errors = [y for y in err.split('\n') if 'ERROR ' in y]
#     return ', '.join([x.split(original_name)[0] for x in getting_errors if 'ERROR' in x])


# stdout, stderr = process.communicate()
# if stderr is not None and stderr != b"" and b"ERROR" in stderr or b'Syntax error' in stderr:
#     try:
#         err = stderr.decode()
#     except Exception:
#         err = stderr.decode("latin1")
#     message = normalize_ogr2ogr_error(err, layername)
#     raise Exception(f"{message} for layer {layername}")


if __name__ == '__main__':
    unittest.main()