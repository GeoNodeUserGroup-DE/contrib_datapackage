
import logging
import zipfile

from pathlib import Path
from osgeo import ogr

from django.db.utils import DataError

from geonode.base.models import ResourceBase
from geonode.geoserver.helpers import set_attributes
from geonode.layers.models import Dataset
from geonode.resource.manager import resource_manager

from geonode.upload.handlers.common.vector import BaseVectorFileHandler
from geonode.upload.orchestrator import orchestrator

from frictionless import Package

from .mapper import TabularDataHelper
from .util import process_rows, validate

logger = logging.getLogger(__name__)


class DataPackageFileHandler(BaseVectorFileHandler):
    """
    Handler to import Data Package files into GeoNode data db
    It must provide the task_lists required to comple the upload
    """

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
        """
        This endpoint will return True or False if with the info provided
        the handler is able to handle the file or not
        """
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
        _file = files.get("json_file")

        # raises exception with proper validation messages if not valid
        validate(_file)
        return BaseVectorFileHandler.is_valid(files, user, **kwargs)

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

    def get_ogr2ogr_driver(self):
        return ogr.GetDriverByName("VRT")

    def generate_resource_payload(self, layer_name, alternate, asset, _exec, workspace):
        payload = super().generate_resource_payload(layer_name, alternate, asset, _exec, workspace)
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
        saved_dataset = super().create_geonode_resource(
            layer_name,
            alternate,
            execution_id,
            resource_type=resource_type,
            asset=asset,
        )

        _exec = self._get_execution_request_object(execution_id)

        self.apply_datapackage_attributes(saved_dataset, layer_name, _exec)

        saved_dataset.set_bbox_polygon(
            # for 'non-spatial' data we apply world bbox
            bbox=[
                -180.0,  # west
                -90.0,  # south,
                180.0,  # east,
                90.0,  # north,
            ],
            srid="EPSG:4326",
        )
        ResourceBase.objects.filter(alternate=alternate).update(dirty_state=False)

        saved_dataset.save()
        saved_dataset.refresh_from_db()
        return saved_dataset

    def overwrite_geonode_resource(
        self,
        layer_name: str,
        alternate: str,
        execution_id: str,
        resource_type: Dataset = Dataset,
        asset=None,
    ):
        dataset = super().overwrite_geonode_resource(
            layer_name,
            alternate,
            execution_id,
            resource_type=resource_type,
            asset=asset,
        )
        if dataset is None:
            return dataset

        # refresh_geonode_resource() runs resource_manager.update() twice, and
        # each one re-runs set_attributes_from_geoserver(): an empty WFS answer
        # there does not just skip the attribute table, it deletes the existing
        # one. The base class also never re-applies our descriptions/labels.
        _exec = self._get_execution_request_object(execution_id)
        self.apply_datapackage_attributes(dataset, layer_name, _exec)
        dataset.refresh_from_db()
        return dataset

    def apply_datapackage_attributes(self, saved_dataset: Dataset, layer_name: str, _exec):
        """
        Bring the dataset's attribute table in line with the datapackage schema:
        create it from the descriptor when GeoServer did not deliver one (see
        ensure_attributes), then apply the declared descriptions and labels.
        """
        _files = _exec.input_params.get("files", {})
        package_file = _files.get("package_file")
        if not package_file:
            return

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
                        la.display_order = display_order
                        la.save()
                    except DataError as e:
                        logger.error(f"Cannot save attribute {field} for layer {saved_dataset.name}: {e}")

                    break

    def ensure_attributes(self, saved_dataset: Dataset, attribute_map: list):
        """
        Guarantee the dataset ends up with an attribute table.

        GeoNode derives the whole attribute table from WFS DescribeFeatureType
        round-trips (geonode.geoserver.helpers.set_attributes_from_geoserver,
        reached through resource_manager.create/update). That call still fails
        silently on GeoNode 5:

          * a GeoServer ServiceExceptionReport is well-formed XML returned with
            HTTP 200, so _get_xml() does not raise and it parses into an empty
            attribute list - which means neither the "will try WMS" fallback nor
            the exc_info logging added in 5.x ever kicks in,
          * the WMS GetFeatureInfo fallback could not work anyway for the
            geometry-less tables we publish (GeometryType wkbNone),
          * set_attributes() then treats the empty list as "this table has no
            columns", logs it at debug, and deletes any attribute already there.

        The upload still reports success, and the very same package imports fine
        on the next attempt. See zalf-rdm/geonode#655 and zalf-rdm/geonode#705.

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

    def handle_thumbnail(self, saved_dataset: Dataset, _exec):
        try:
            resource_manager.set_thumbnail(None, instance=saved_dataset)
        except Exception:
            logger.info(f"Skipping thumbnail generation for tabular dataset {saved_dataset.pk}")
