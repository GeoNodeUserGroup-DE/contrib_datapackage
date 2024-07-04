
import logging

from django.apps import AppConfig


logger = logging.getLogger(__name__)


class DataPackageConfig(AppConfig):
    name = "importer_datapackage"
    verbose_name = "Datapackage"

    def ready(self):
        super(DataPackageConfig, self).ready()
