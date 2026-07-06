import logging
from pathlib import Path
import zipfile

from django.db.utils import DataError
from geonode.base.models import ResourceBase
from geonode.layers.models import Dataset
from geonode.resource.manager import resource_manager
from geonode.upload.handlers.common.vector import BaseVectorFileHandler
from geonode.upload.orchestrator import orchestrator
from osgeo import ogr

from .mapper import TabularDataHelper
from .util import process_rows, validate


logger = logging.getLogger("importer")


class DataPackageFileHandler(BaseVectorFileHandler):
    @property
    def supported_file_extension_config(self):
        return {
            "id": "datapackage",
            "formats": [
                {
                    "label": "Data Package",
                    "required_ext": ["zip"],
                    "optional_ext": ["xml", "sld"],
                }
            ],
            "actions": list(self.TASKS.keys()),
            "type": "vector",
        }

    @staticmethod
    def can_handle(_data) -> bool:
        json_file = _data.get("json_file")
        if not json_file:
            base_file = _data.get("base_file")
            if not base_file:
                return False

            base_path = Path(base_file) if isinstance(base_file, str) else Path(base_file.name)
            if base_path.suffix.lower() != ".zip":
                return False

            try:
                with zipfile.ZipFile(base_file, "r") as archive:
                    names = {Path(name).name for name in archive.namelist()}
            except zipfile.BadZipFile:
                return False
            finally:
                if hasattr(base_file, "seek"):
                    base_file.seek(0)

            return "datapackage.json" in names and BaseVectorFileHandler.can_handle(_data)

        filename = Path(json_file).name if isinstance(json_file, str) else json_file.name
        return filename == "datapackage.json" and BaseVectorFileHandler.can_handle(_data)

    @staticmethod
    def extract_params_from_data(_data, action=None):
        extracted_params, files = BaseVectorFileHandler.extract_params_from_data(_data, action=action)
        base_file = files.get("base_file")
        if isinstance(base_file, str) and base_file.lower().endswith(".zip"):
            files["zip_file"] = base_file
        return extracted_params, files

    @staticmethod
    def is_valid(files, user, **kwargs):
        validate(files.get("json_file"))
        return BaseVectorFileHandler.is_valid(files, user, **kwargs)

    def prepare_import(self, files, execution_id, **kwargs):
        from frictionless import Package

        package_file = files.get("json_file")
        package = Package(package_file)

        for resource in package.resources:
            process_rows(resource)

        folder = Path(package_file).parent
        mapper = TabularDataHelper(package, self.fixup_name)
        vrt_file = mapper.write_vrt_file(f"{package.name}.vrt", folder)

        prepared_files = {
            "base_file": str(vrt_file),
            "package_file": package_file,
        }
        files.update(prepared_files)

        execution = self._get_execution_request_object(execution_id)
        input_params = execution.input_params.copy()
        input_files = input_params.get("files", {}).copy()
        input_files.update(prepared_files)
        input_params["files"] = input_files
        orchestrator.update_execution_request_status(execution_id=str(execution_id), input_params=input_params)

    def get_ogr2ogr_driver(self):
        return ogr.GetDriverByName("VRT")

    def generate_resource_payload(self, layer_name, alternate, asset, execution, workspace):
        payload = super().generate_resource_payload(layer_name, alternate, asset, execution, workspace)
        payload["subtype"] = "tabular"
        return payload

    def create_geonode_resource(
        self,
        layer_name: str,
        alternate: str,
        execution_id: str,
        resource_type: Dataset = Dataset,
        asset=None,
    ):
        dataset = super().create_geonode_resource(
            layer_name,
            alternate,
            execution_id,
            resource_type=resource_type,
            asset=asset,
        )

        execution = self._get_execution_request_object(execution_id)
        package_file = execution.input_params.get("files", {}).get("package_file")
        if not package_file:
            return dataset

        from frictionless import Package

        package = Package(package_file)
        mapper = TabularDataHelper(package, self.fixup_name)
        attribute_map = mapper.parse_attribute_map(layer_name)

        for dataset_attribute in dataset.attribute_set.all():
            for field_name, _field_type, description, label, display_order in attribute_map:
                if field_name != dataset_attribute.attribute:
                    continue
                try:
                    dataset_attribute.description = description
                    dataset_attribute.attribute_label = label
                    dataset_attribute.display_order = display_order
                    dataset_attribute.save()
                except DataError as exc:
                    logger.error(
                        "Cannot save attribute %s for layer %s: %s",
                        field_name,
                        dataset.name,
                        exc,
                    )
                break

        dataset.set_bbox_polygon(bbox=[-180.0, -90.0, 180.0, 90.0], srid="EPSG:4326")
        ResourceBase.objects.filter(alternate=alternate).update(dirty_state=False)
        dataset.save()
        dataset.refresh_from_db()
        return dataset

    def handle_thumbnail(self, saved_dataset: Dataset, execution):
        try:
            resource_manager.set_thumbnail(None, instance=saved_dataset)
        except Exception:
            logger.info("Skipping thumbnail generation for tabular dataset %s", saved_dataset.pk)
