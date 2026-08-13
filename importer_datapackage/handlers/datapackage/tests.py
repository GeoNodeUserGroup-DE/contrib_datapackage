import json
import shutil
import uuid

from os import path
from pathlib import Path
from mock import MagicMock, patch
from tempfile import TemporaryDirectory

from frictionless import Package
from osgeo import ogr
import xml.etree.cElementTree as ET

from django.test import TestCase
from django.contrib.auth import get_user_model
from geonode.storage.manager import StorageManager

from importer_datapackage.handlers.datapackage.handler import DataPackageFileHandler
from importer_datapackage.handlers.datapackage.mapper import TabularDataHelper
from importer_datapackage.handlers.datapackage.util import process_rows
from importer_datapackage.handlers.datapackage.exceptions import InvalidDataPackageFileException

def _absolute_path(filename: str):
    script = path.abspath(__file__)
    return path.join(path.dirname(script), filename)

def _write_vrtfile(dir, mapper): 
    return mapper.write_vrt_file("test.vrt", dir)

def _unzip(data):
    storage_manager = StorageManager(
        remote_files={"base_file": data.get("zip_file")}
    )
    storage_manager.clone_remote_files()
    data.update(storage_manager.get_retrieved_paths())
    return data

class TestSchemaToVrtMapper(TestCase):
    databases = ("default", "datastore")

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.package = Package(_absolute_path("data/datapackage.json"))
        cls.mapper = TabularDataHelper(cls.package, DataPackageFileHandler().fixup_name)

    def test_write_vrt_file(self):
        with TemporaryDirectory() as tmp_dir:
            actual = _write_vrtfile(tmp_dir, self.mapper)
            self.assertTrue(path.exists(actual))

    def test_field_mappings(self):
        with TemporaryDirectory() as tmp_dir:
            vrt_file = _write_vrtfile(tmp_dir, self.mapper)
            
            tree = ET.parse(vrt_file)
            root = tree.getroot()
            self.assertEqual("OGRVRTDataSource", root.tag)
            for child in root:
                self.assertEqual("OGRVRTLayer", child.tag)
                self.assertIsNotNone(child.attrib["name"])

class TestHandler(TestCase):
    
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user, _ = get_user_model().objects.get_or_create(username="admin")
    
    def test_can_handle_datapackage(self):
        valid_dp = _absolute_path("data/datapackage.json")
        handler = DataPackageFileHandler()
        
        self.assertTrue(handler.can_handle({"json_file": valid_dp}))
        
    def test_cannot_handle_non_datapackage(self):
        some_json = _absolute_path("data/geojson.json")
        handler = DataPackageFileHandler()
        
        self.assertFalse(handler.can_handle({"json_file": some_json}))
        
    def test_cannot_handle_missing_json_file(self):
        handler = DataPackageFileHandler()
        
        self.assertFalse(handler.can_handle({"json_file": None}))
    
    def test_valid_package_returns_true(self):
        valid_dp = _absolute_path("data/datapackage.json")
        handler = DataPackageFileHandler()
        
        result = handler.is_valid(files={"json_file": valid_dp}, user=self.user)
        self.assertTrue(result)
        
    def test_invalid_package_throws_exception(self):
        invalid_dp = _absolute_path("data/invalid_datapackage.json")
        handler = DataPackageFileHandler()
        
        with self.assertRaises(InvalidDataPackageFileException):
            handler.is_valid(files={"json_file": invalid_dp}, user=self.user)

    def test_unzipped_datapackage_provides_json_file(self):
        valid_zip = _absolute_path("data/valid_data.zip")
        files = _unzip({"zip_file": valid_zip})
        
        json_file = files.get("json_file")
        self.assertTrue("datapackage.json" in str(json_file))

    @patch('importer.handlers.common.vector.BaseVectorFileHandler._get_execution_request_object')
    @patch('importer.orchestrator.ImportOrchestrator.update_execution_request_status')
    def test_prepare_import_provides_vrt_file(self, get_exec_request, update):
        valid_zip = _absolute_path("data/valid_data.zip")
        files = _unzip({"zip_file": valid_zip})

        handler = DataPackageFileHandler()

        _uuid = str(uuid.uuid4())
        mocked_exec_object = {
            "execution_id": _uuid,
            "files": files,
            "original_name": "dataset",
            "handler_module_path": str(handler),
            "ovverwrite_layer": False,
            "alternate": "alternate",
            "input_params": {
                "files": {}
            }
        }
        get_exec_request.return_value = mocked_exec_object

        handler.prepare_import(files, _uuid)
        update.assert_called_once()
        
        # TODO test if base_file is now vrt file 
        
        # kall = update.call_args()
        # args = kall.kwargs
        # input_params = args["input_params"]
        # self.assertTrue(str(input_params["base_file"]).endswith(".vrt"))
        # self.assertEqual(input_params["package_file"], files.get("json_file"))
        

    # TODO Test driver
    # TODO Test create_geonode_resource (subtype)


def _write_package(tmp_dir, descriptor, csv_text, csv_name="data.csv"):
    (Path(tmp_dir) / csv_name).write_text(csv_text)
    json_path = Path(tmp_dir) / "datapackage.json"
    json_path.write_text(json.dumps(descriptor))
    return Package(str(json_path))


class TestVrtNullHandling(TestCase):
    """
    Regression coverage for a GDAL VRT quirk: casting an empty CSV cell to an
    Integer/Real VRT field yields 0, not NULL (Date/DateTime are unaffected).
    See the EMPTY_STRING_AS_NULL OpenOptions in mapper.write_vrt_file.

    The resource name deliberately differs from the CSV filename (a common,
    valid datapackage pattern) to also guard against a separate GDAL VRT bug:
    without an explicit SrcLayer, GDAL matches the VRT layer's own "name"
    against the source CSV's layer name (its filename minus extension), and
    silently imports zero features when they don't match.
    """

    _DESCRIPTOR = {
        "name": "synthetic",
        "resources": [
            {
                "name": "synthetic_data",
                "path": "data.csv",
                "format": "csv",
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "amount", "type": "number"},
                        {"name": "label", "type": "string"},
                        {"name": "measured_on", "type": "date"},
                    ]
                },
            }
        ],
    }

    _CSV = "id,amount,label,measured_on\n1,12,foo,2020-01-01\n2,,,\n"

    def test_empty_cells_are_null_not_zero(self):
        with TemporaryDirectory() as tmp_dir:
            package = _write_package(tmp_dir, self._DESCRIPTOR, self._CSV)
            mapper = TabularDataHelper(package, DataPackageFileHandler().fixup_name)
            vrt_file = mapper.write_vrt_file("test.vrt", tmp_dir)

            datasource = ogr.Open(str(vrt_file))
            layer = datasource.GetLayer(0)
            self.assertEqual(layer.GetFeatureCount(), 2)

            populated = layer.GetNextFeature()
            self.assertTrue(populated.IsFieldSetAndNotNull("id"))
            self.assertTrue(populated.IsFieldSetAndNotNull("amount"))
            self.assertTrue(populated.IsFieldSetAndNotNull("label"))
            self.assertTrue(populated.IsFieldSetAndNotNull("measured_on"))
            self.assertEqual(populated.GetField("amount"), 12.0)

            blank = layer.GetNextFeature()
            self.assertTrue(blank.IsFieldSetAndNotNull("id"))
            self.assertFalse(blank.IsFieldSetAndNotNull("amount"))
            self.assertFalse(blank.IsFieldSetAndNotNull("label"))
            self.assertFalse(blank.IsFieldSetAndNotNull("measured_on"))


class TestProcessRowsMissingValues(TestCase):
    """
    Locks in that util.process_rows() (the frictionless normalization step)
    already correctly empties a cell whose value matches a field's declared
    missingValues, for every field type - and leaves an undeclared sentinel
    (same literal text, no missingValues on that field) untouched.
    """

    _DESCRIPTOR = {
        "name": "synthetic",
        "resources": [
            {
                "name": "data",
                "path": "data.csv",
                "format": "csv",
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "amount", "type": "number", "missingValues": ["NA"]},
                        {"name": "measured_on", "type": "date", "missingValues": ["NA"]},
                        {"name": "note", "type": "string"},
                    ]
                },
            }
        ],
    }

    _CSV = "id,amount,measured_on,note\n1,12.5,2020-01-01,foo\n2,NA,NA,NA\n"

    def test_declared_missing_values_become_empty_cells(self):
        with TemporaryDirectory() as tmp_dir:
            package = _write_package(tmp_dir, self._DESCRIPTOR, self._CSV)
            process_rows(package.get_resource("data"))

            rows = (Path(tmp_dir) / "data.csv").read_text().strip().splitlines()
            self.assertEqual(rows[0], "id,amount,measured_on,note")
            self.assertEqual(rows[1], "1,12.5,2020-01-01,foo")
            # amount/measured_on declare missingValues -> emptied out;
            # note has no missingValues declared -> literal "NA" survives untouched
            self.assertEqual(rows[2], "2,,,NA")


class TestDataPackageEndToEndNullHandling(TestCase):
    """
    Combines process_rows() + write_vrt_file() exactly as prepare_import() does,
    against the bundled real-world fixture (laboratory_data.BD_bulk is a number
    field with missingValues=["NA"]), proving a declared missing value round-trips
    to a true NULL in the generated VRT layer rather than silently becoming 0.
    """

    def test_missing_number_value_is_null_in_vrt(self):
        with TemporaryDirectory() as tmp_dir:
            for fname in ("datapackage.json", "HORIZON_DATA.csv", "LABORATORY_DATA.csv"):
                shutil.copy(_absolute_path(f"data/{fname}"), path.join(tmp_dir, fname))

            package = Package(path.join(tmp_dir, "datapackage.json"))
            resource = package.get_resource("laboratory_data")
            process_rows(resource)

            mapper = TabularDataHelper(package, DataPackageFileHandler().fixup_name)
            vrt_file = mapper.write_vrt_file("test.vrt", tmp_dir)

            datasource = ogr.Open(str(vrt_file))
            layer = datasource.GetLayerByName("laboratory_data")

            null_count = 0
            set_count = 0
            layer.ResetReading()
            for feature in layer:
                if feature.IsFieldSetAndNotNull("bd_bulk"):
                    set_count += 1
                    self.assertNotEqual(feature.GetField("bd_bulk"), 0.0)
                else:
                    null_count += 1

            self.assertGreater(null_count, 0, "expected at least one NULL BD_bulk row (missingValues)")
            self.assertGreater(set_count, 0, "expected at least one populated BD_bulk row")