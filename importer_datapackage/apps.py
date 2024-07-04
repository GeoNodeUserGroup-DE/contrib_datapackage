
import logging

from django.apps import apps, AppConfig


logger = logging.getLogger(__name__)


_original_generator = None


def run_setup_hooks(*args, **kwargs):
    from django.conf import settings
    _original_generator = settings.THUMBNAIL_GENERATOR
    settings.THUMBNAIL_GENERATOR = "importer_datapackage.apps.create_thumbnail"


def create_thumbnail(instance, overwrite=False, check_bbox=False):
    if instance.subtype != "tabular":
        _original_generator(instance, overwrite, check_bbox)
    else:
        # do nothing
        pass


class DataPackageConfig(AppConfig):
    name = "importer_datapackage"
    verbose_name = "Datapackage"

    def ready(self):
        if not apps.ready:
            run_setup_hooks()
        super(DataPackageConfig, self).ready()
