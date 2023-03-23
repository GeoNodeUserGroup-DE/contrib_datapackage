from geonode.resource.manager import ResourceManager
from geonode.base.models import ResourceBase

from importer.utils import ImporterConcreteManager


class DatapackageResourceHandler(ImporterConcreteManager):
    
    def create(self, uuid, **kwargs) -> ResourceBase:
        return ResourceBase.objects.get(uuid=uuid)


datapackage_resource_manager = ResourceManager(concrete_manager=DatapackageResourceHandler())
