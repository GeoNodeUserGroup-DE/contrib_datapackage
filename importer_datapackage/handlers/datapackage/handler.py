
import os
import sys
import logging

import importlib.resources as pkg_resources

from pathlib import Path
from osgeo import ogr

from django.conf import settings
from django.db.utils import DataError
from django.db.models import Q

from geonode.base.models import ResourceBase
from geonode.geoserver.helpers import set_attributes
from geonode.layers.models import Dataset
from geonode.resource.manager import resource_manager
from geonode.resource.models import ExecutionRequest
from geonode.resource.enumerator import ExecutionRequestAction as exa
from geonode.utils import set_resource_default_links

from importer.handlers.common.vector import BaseVectorFileHandler
from importer.orchestrator import orchestrator
from importer.utils import ImporterRequestAction as ira

from frictionless import Package

from .mapper import TabularDataHelper
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
        mapper = TabularDataHelper(package, self.fixup_name)
        vrt_file = mapper.write_vrt_file(f"{package.name}.vrt", folder)

        # update base file to be imported by ogr2ogr
        prepared_files = {
            "base_file": str(vrt_file),
            # "sld_file": str(self.load_local_resource("fake.sld")),
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

    # def can_handle_sld_file():
    #     return True

    def get_ogr2ogr_driver(self):
        return ogr.GetDriverByName("VRT")

    # def handle_sld_file(self, saved_dataset: Dataset, _exec: ExecutionRequest):
    #     sld_file = self.load_local_resource("fake.sld")
    #     resource_manager.exec(
    #         "set_style",
    #         None,
    #         instance=saved_dataset,
    #         sld_file=sld_file,
    #         sld_uploaded=True,
    #     )

    def create_geonode_resource(
        self,
        layer_name: str,
        alternate: str,
        execution_id: str,
        resource_type: Dataset = Dataset,
        asset=None,
        custom={},
    ):
        """
        Base function to create the resource into geonode. Each handler can specify
        and handle the resource in a different way
        """
        saved_dataset = resource_type.objects.filter(alternate__icontains=alternate)

        _exec = self._get_execution_request_object(execution_id)

        workspace = getattr(
            settings,
            "DEFAULT_WORKSPACE",
            getattr(settings, "CASCADE_WORKSPACE", "geonode"),
        )

        _overwrite = _exec.input_params.get("overwrite_existing_layer", False)
        # if the layer exists, we just update the information of the dataset by
        # let it recreate the catalogue
        if not saved_dataset.exists() and _overwrite:
            logger.warning(
                f"The dataset required {alternate} does not exists, but an overwrite is required, the resource will be created"
            )

        # TODO store other metadata from datapackage (license, keywords, etc.)

        saved_dataset = resource_manager.create(
            None,
            resource_type=resource_type,
            defaults=self.generate_resource_payload(
                layer_name, alternate, asset, _exec, workspace
            ),
            custom=custom,
        )

        saved_dataset.refresh_from_db()
        # self.handle_sld_file(saved_dataset, _exec)

        with open(self.load_local_resource("table-icon.jpg"), "rb") as icon:
            content = icon.read()
            resource_manager.set_thumbnail(None, instance=saved_dataset, thumbnail=content)

        set_resource_default_links(saved_dataset.get_real_instance(), saved_dataset)
        ResourceBase.objects.filter(alternate=alternate).update(dirty_state=False)

        self.apply_datapackage_attributes(saved_dataset, layer_name, _exec)

        saved_dataset.set_bbox_polygon(
            # for 'non-spatial' data we apply world bbox
            bbox=[
                -179.0, # west
                -89.0, # south,
                179.0, # east,
                89.0, #n north,
            ],
            srid="EPSG:4326",
        )

        # TODO update feature boundaries via featuretype recalculate
        # https://docs.geoserver.org/latest/en/user/rest/api/featuretypes.html#recalculate
        # https://gis.stackexchange.com/questions/199239/update-programmatically-bbox-of-wms-geoserver-layer


        saved_dataset.save()
        saved_dataset.refresh_from_db()
        return saved_dataset

    def apply_datapackage_attributes(
        self, saved_dataset: Dataset, layer_name: str, _exec: ExecutionRequest
    ):
        """
        Bring the dataset's attribute table in line with the datapackage schema:
        create it from the descriptor when GeoServer did not deliver one (see
        ensure_attributes), then apply the declared descriptions and labels.
        """
        _files = _exec.input_params.get("files")
        package_file = _files.get("package_file")
        package = Package(package_file)

        mapper = TabularDataHelper(package, self.fixup_name)
        attribute_map = mapper.parse_attribute_map(layer_name)

        self.ensure_attributes(saved_dataset, attribute_map)

        for la in saved_dataset.attribute_set.all():
            for attribute in attribute_map:
                field, ftype, description, label, display_order = attribute
                if field == la.attribute:
                    try:
                        la.description = description
                        la.attribute_label = label
                        la.save()
                    except DataError as e:
                        logger.error(f"Cannot save attribute {field} for layer {saved_dataset.name}: {e}")

                    continue

    def ensure_attributes(self, saved_dataset: Dataset, attribute_map: list):
        """
        Guarantee the dataset ends up with an attribute table.

        GeoNode derives the whole attribute table from a single WFS
        DescribeFeatureType round-trip, made deep inside resource_manager.create()
        (geonode.geoserver.helpers.set_attributes_from_geoserver). That call fails
        silently in three compounding ways:

          * a GeoServer ServiceExceptionReport is well-formed XML and is returned
            with HTTP 200, so it parses into an empty attribute list without ever
            raising - and the retry list in geonode.utils.HttpClient only covers
            connection errors and 5xx,
          * the WMS GetFeatureInfo fallback sits in the except branch that never
            runs, and could not work anyway for the geometry-less tables we
            publish,
          * both the failure and the resulting empty list are logged at debug
            level only.

        The stock vector handler survives this because it retries the same call
        via handle_xml_file() -> resource_manager.update(); we do not, so a single
        hiccup left the upload reporting success with no attribute table at all,
        and the very same package imported fine on the next attempt.
        See zalf-rdm/geonode#655 and zalf-rdm/geonode#705.

        The datapackage descriptor already carries the authoritative schema, so
        use it whenever GeoServer did not deliver one.
        """
        if saved_dataset.attribute_set.exists():
            return

        logger.warning(
            f"GeoServer reported no attributes for {saved_dataset.alternate}, "
            "falling back to the schema declared in the datapackage"
        )
        # Nothing to overwrite - the guard above makes this purely additive, but
        # it keeps set_attributes() from preferring stored values over ours.
        set_attributes(saved_dataset, attribute_map, overwrite=True)

    def generate_resource_payload(self, layer_name, alternate, asset, _exec, workspace):
        return dict(
            name=alternate,
            workspace=workspace,
            store=os.environ.get("GEONODE_GEODATABASE", "geonode_data"),
            subtype="tabular",
            alternate=f"{workspace}:{alternate}",
            dirty_state=True,
            title=layer_name,
            owner=_exec.user,
            asset=asset,
        )

    def overwrite_geonode_resource(
        self,
        layer_name: str,
        alternate: str,
        execution_id: str,
        resource_type: Dataset = Dataset,
        asset=None,
        custom={},
        
    ):
        dataset = resource_type.objects.filter(alternate__icontains=alternate)

        _exec = self._get_execution_request_object(execution_id)

        _overwrite = _exec.input_params.get("overwrite_existing_layer", False)
        # if the layer exists, we just update the information of the dataset by
        # let it recreate the catalogue
        if dataset.exists() and _overwrite:
            dataset = dataset.first()

            dataset = resource_manager.update(
                dataset.uuid, instance=dataset,  files=asset.location
            )

            self.handle_xml_file(dataset, _exec)
            # self.handle_sld_file(dataset, _exec)

            # Both resource_manager.update() calls above re-run
            # set_attributes_from_geoserver(); an empty WFS answer there does not
            # just skip the attribute table, it deletes the existing one.
            self.apply_datapackage_attributes(dataset, layer_name, _exec)

            dataset.refresh_from_db()
            return dataset
        elif not dataset.exists() and _overwrite:
            logger.warning(
                f"The dataset required {alternate} does not exists, but an overwrite is required, the resource will be created"
            )
            return self.create_geonode_resource(
                layer_name, alternate, execution_id, resource_type, asset, custom=custom,
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
