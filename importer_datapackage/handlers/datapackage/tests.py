import uuid

from os import path
from mock import MagicMock, patch
from tempfile import TemporaryDirectory

from frictionless import Package
import xml.etree.cElementTree as ET

from django.test import TestCase
from django.contrib.auth import get_user_model
from geonode.storage.manager import StorageManager

from importer_datapackage.handlers.datapackage.handler import DataPackageFileHandler
from importer_datapackage.handlers.datapackage.mapper import TabularDataHelper
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
        cls.mapper = TabularDataHelper(cls.package)

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