
import os
import sys
import logging

import importlib.resources as pkg_resources

from io import BytesIO
from pathlib import Path
from osgeo import ogr
from PIL import Image

from django.conf import settings
from django.db.models import Q

from geonode.base.models import ResourceBase
from geonode.layers.models import Dataset
from geonode.resource.manager import resource_manager
from geonode.resource.enumerator import ExecutionRequestAction as exa
from geonode.utils import set_resource_default_links

from importer.handlers.common.vector import BaseVectorFileHandler
from importer.orchestrator import orchestrator
from importer.utils import ImporterRequestAction as ira

from frictionless import Package

from .mapper import SchemaToVrtMapper
from .util import process_rows, validate

logger = logging.getLogger(__name__)


class DataPackageFileHandler(BaseVectorFileHandler):
    """
    Handler to import Data Package files into GeoNode data db
    It must provide the task_lists required to comple the upload
    """

    ACTIONS = {
        exa.IMPORT.value: (
            "start_import",
            "importer.import_resource",
            "importer.publish_resource",
            "importer.create_geonode_resource",
        ),
        exa.COPY.value: (
            "start_copy",
            "importer.copy_dynamic_model",
            "importer.copy_geonode_data_table",
            "importer.publish_resource",
            "importer.copy_geonode_resource",
        ),
        ira.ROLLBACK.value: (
            "start_rollback",
            "importer.rollback",
        ),
    }

    @property
    def supported_file_extension_config(self):
        return {
            "id": "datapackage",
            "label": "Data Package",
            "format": "archive",
            "ext": ["zip"],
            "requires": ["json", "csv"],
            # TODO thumbnail
            # "optional": ['png']
        }

    @staticmethod
    def can_handle(_data) -> bool:
        """
        This endpoint will return True or False if with the info provided
        the handler is able to handle the file or not
        """
        base = _data.get("json_file")
        if not base:
            return False

        filename = Path(base).name
        return filename == "datapackage.json"

    @staticmethod
    def is_valid(files, user):
        _file = files.get("json_file")

        # raises exception with proper validation messages if not valid
        validate(_file)
        return True

    def prepare_import(self, files, execution_id, **kwargs):
        _file = files.get("json_file")
        package = Package(_file)

        for resource in package.resources:
            process_rows(resource)

        folder = Path(_file).parent
        mapper = SchemaToVrtMapper(package)
        vrt_file = mapper.write_vrt_file(f"{package.name}.vrt", folder)

        # update base file to be imported by ogr2ogr
        prepared_files = {
            "base_file": str(vrt_file),
            "package_file": _file,
        }
        files.update(prepared_files)
        _exec = self._get_execution_request_object(execution_id)
        input_params = _exec.input_params
        input_params.get("files").update(prepared_files)

        _input = {**_exec.input_params}
        orchestrator.update_execution_request_status(
            execution_id=str(execution_id), input_params=_input
        )

    def can_handle_sld_file():
        return False

    def get_ogr2ogr_driver(self):
        return ogr.GetDriverByName("VRT")

    def create_geonode_resource(
        self,
        layer_name: str,
        alternate: str,
        execution_id: str,
        resource_type: Dataset = Dataset,
        files=None,
    ):
        """
        Base function to create the resource into geonode. Each handler can specify
        and handle the resource in a different way
        """
        saved_dataset = resource_type.objects.filter(alternate__icontains=alternate)

        _exec = self._get_execution_request_object(execution_id)
        _overwrite = _exec.input_params.get("overwrite_existing_layer", False)

        # if the layer exists, we just update the information of the dataset by
        # let it recreate the catalogue
        if not saved_dataset.exists() and _overwrite:
            logger.warning(
                f"The dataset required {alternate} does not exists, but an overwrite is required, the resource will be created"
            )

        workspace = getattr(
            settings,
            "DEFAULT_WORKSPACE",
            getattr(settings, "CASCADE_WORKSPACE", "geonode"),
        )

        # TODO store other metadata from datapackage (license, keywords, etc.)

        saved_dataset = resource_manager.create(
            None,
            resource_type=resource_type,
            defaults=dict(
                name=alternate,
                workspace=workspace,
                store=os.environ.get("GEONODE_GEODATABASE", "geonode_data"),
                subtype="tabular",
                alternate=f"{workspace}:{alternate}",
                dirty_state=True,
                title=layer_name,
                owner=_exec.user,
                # TODO do we need to keep reference to the originally uploaded file set
                # files=list(set(list(_exec.input_params.get("files", {}).values()) or list(files)))
            ),
        )

        saved_dataset.refresh_from_db()


        with open(self.load_local_resource("table-icon.jpg"), "rb") as icon:
            content = icon.read()
            resource_manager.set_thumbnail(None, instance=saved_dataset, thumbnail=content)

        # with self.load_local_resource("table-icon.png") as icon:
        #     # resource_manager.set_thumbnail(None, instance=saved_dataset, thumbnail=icon)
        #     with BytesIO() as output:
        #         img = Image.open(icon)
        #         img.save(output, format="PNG")
        #         content = output.getvalue()
        #     saved_dataset.save_thumbnail(icon.name, content)

        set_resource_default_links(saved_dataset.get_real_instance(), saved_dataset)
        ResourceBase.objects.filter(alternate=alternate).update(dirty_state=False)

        saved_dataset.refresh_from_db()
        return saved_dataset

    def overwrite_geonode_resource(
        self,
        layer_name: str,
        alternate: str,
        execution_id: str,
        resource_type: Dataset = Dataset,
        files=None,
    ):
        dataset = resource_type.objects.filter(alternate__icontains=alternate)

        _exec = self._get_execution_request_object(execution_id)

        _overwrite = _exec.input_params.get("overwrite_existing_layer", False)
        # if the layer exists, we just update the information of the dataset by
        # let it recreate the catalogue
        if dataset.exists() and _overwrite:
            dataset = dataset.first()

            dataset = resource_manager.update(
                dataset.uuid, instance=dataset, files=files
            )

            self.handle_xml_file(dataset, _exec)
            self.handle_sld_file(dataset, _exec)

            dataset.refresh_from_db()
            return dataset
        elif not dataset.exists() and _overwrite:
            logger.warning(
                f"The dataset required {alternate} does not exists, but an overwrite is required, the resource will be created"
            )
            return self.create_geonode_resource(
                layer_name, alternate, execution_id, resource_type, files
            )
        elif not dataset.exists() and not _overwrite:
            logger.warning(
                "The resource does not exists, please use 'create_geonode_resource' to create one"
            )
        return

    def extract_resource_to_publish(
        self, files, action, layer_name, alternate, **kwargs
    ):
        if action == exa.COPY.value:
            return [
                {
                    "name": alternate,
                    "crs": ResourceBase.objects.filter(
                        Q(alternate__icontains=layer_name)
                        | Q(title__icontains=layer_name)
                    )
                    .first()
                    .srid,
                }
            ]

        vrt_file = files.get("base_file")
        layers = self.get_ogr2ogr_driver().Open(vrt_file)
        if not layers:
            return []
        return [
            {
                "name": alternate or layer_name,
                "crs": (
                    self.identify_authority(_l) if _l.GetSpatialRef() else "EPSG:4326"
                ),
            }
            for _l in layers
            if self.fixup_name(_l.GetName()) == layer_name
        ]

    @staticmethod
    def create_ogr2ogr_command(files, original_name, overwrite, alternate):
        """
        Define the ogr2ogr command to be executed.
        This is a default command that is needed to import a vector file
        """
        return BaseVectorFileHandler.create_ogr2ogr_command(
            files, original_name, overwrite, alternate
        )

    def load_local_resource(self, name: str):
        module = pkg_resources.files(sys.modules["importer_datapackage"])
        return module.joinpath(f"handlers/datapackage/resources/{name}")

    def _select_valid_layers(self, all_layers):
        return all_layers
