# Datapackage Support for geonode-importer

This contrib app provides a datapackage handler for the geonode-importer.
The app aims to be compatible with geonode-importer v1.0.9, but can be used only with GeoNode v4.3.x.

The handler leverages the [OGR VRT format](https://gdal.org/drivers/vector/vrt.html) to import non-spatial datasets described in a [tabular data resource schema](https://specs.frictionlessdata.io/tabular-data-resource/).
To make this possible a schema mapping takes place.

> :wrench: Development Hint
>
> There are lots of adjustments made in both `GeoNode`, `geonode-mapstore-client` which are necessary to integrate `tabular` data.
> You should be able to the see all needed changes by comparing branches:
>
> * 🔄 [Compare GeoNode changes](https://github.com/GeoNode/geonode/compare/GeoNode:4.3.0..GeoNodeUserGroup-DE:datapackage_tabular-data)
> * 🔄 [Compare geonode-mapstore-client changes](https://github.com/GeoNode/geonode-mapstore-client/compare/GeoNode:v4.3.0..GeoNodeUserGroup-DE:datapackage_tabular-data) (you can ignore all changes under `/geonode_mapstore_client/client/static/mapstore/dist` of course)
>
> Check out the [development setup](https://github.com/GeoNodeUserGroup-DE/geonode-dev-datapackage) (based on the [Geonode Docker blueprint](https://github.com/GeoNodeUserGroup-DE/geonode-blueprint-docker)).

Feel free to contribute by [creating an issue](https://github.com/GeoNodeUserGroup-DE/importer-datapackage/issues) [or even a PR](https://github.com/GeoNodeUserGroup-DE/importer-datapackage/pulls) on GitHub.

## Installation

The following steps are necessary so GeoNode is able to handle the frictionless datapackage format:

- Installation of the datapackage handler for the geonode-importer
- Manual integration of a UI code adjustments
- Configuration of the MapStore plugin

### Install Datapackage Handler

The module can be installed as normal Django contrib app: 

```python
INSTALLED_APPS += (
   importer_datapackage
)
```

Install all necessary dependencies via `pip install -r requirements.txt`.
For development let `pip` install the branch of your current interest:

```
-e git+https://github.com/GeoNodeUserGroup-DE/importer-datapackage.git@main#egg=importer_datapackage
```

The URL above references the `main` branch.

Once installed, the `importer_datapackage.handlers.datapackage.handler.DataPackageFileHandler` has to be added to the `IMPORTER_HANDLERS`.
Open the `settings.py` and add

```py
IMPORTER_HANDLERS = [
    'importer_datapackage.handlers.datapackage.handler.DataPackageFileHandler',
    *IMPORTER_HANDLERS,
]
```

### Geonode Mapstore Client Plugin

There is a geonode-mapstore-client plugin to preview tabular data.
To let the UI recognize and handle `tabular` datasets, you have to integrate code which resides in [branch datapackage_tabular-data](https://github.com/GeoNodeUserGroup-DE/geonode-mapstore-client/tree/datapackage_tabular-data) of the [GeoNodeUserGroup-DE geonode-mapstore-client fork](https://github.com/GeoNodeUserGroup-DE/geonode-mapstore-client).

## Configuration

To enable the geonode-mapstore-plugin add the following plugin configuration to your `localConfig.json`:

```json
"plugins": {
  
  "tabular_viewer": [
    {
      "name": "ActionNavbar",
      "cfg": {
        "containerPosition": "header",
        "leftMenuItems": [
          {
            "type": "link",
            "size": "md",
            "href": "#/all",
            "labelId": "gnviewer.allResources"
          },
          {
            "type": "plugin",
            "size": "md",
            "name": "DetailViewerButton"
          },
          {
            "labelId": "gnviewer.resource",
            "showPendingChangesIcon": true,
            "type": "dropdown",
            "items": [
              {
                "type": "plugin",
                "name": "Share"
              },
              {
                "type": "divider",
                "disableIf": "{state('isNewResource') || !context.resourceHasPermission(state('gnResourceData'), 'delete_resourcebase')}"
              },
              {
                "type": "plugin",
                "name": "DeleteResource",
                "disableIf": "{!context.resourceHasPermission(state('gnResourceData'), 'delete_resourcebase')}"
              }
            ]
          },
          {
            "labelId": "gnviewer.view",
            "type": "dropdown",
            "items": [
              {
                "type": "plugin",
                "name": "DetailViewerButton"
              },
              {
                "type": "link",
                "href": "{context.getMetadataDetailUrl(state('gnResourceData'))}",
                "labelId": "gnviewer.viewMetadata"
              }
            ]
          },
          {
            "labelId": "gnviewer.edit",
            "type": "dropdown",
            "disableIf": "{!context.resourceHasPermission(state('gnResourceData'), 'change_resourcebase')}",
            "items": [
              {
                "type": "link",
                "href": "{context.getMetadataUrl(state('gnResourceData'))}",
                "labelId": "gnviewer.editMetadata"
              },
              {
                "type": "link",
                "href": "{'/datasets/' + (state('gnResourceData') || {}).alternate + '/metadata_upload'}",
                "labelId": "gnviewer.metadataUpload"
              }
            ]
          },
          {
            "labelId": "gnviewer.view",
            "type": "dropdown",
            "disableIf": "{context.resourceHasPermission(state('gnResourceData'), 'change_resourcebase')}",
            "items": [
              {
                "type": "link",
                "href": "{context.getMetadataDetailUrl(state('gnResourceData'))}",
                "labelId": "gnviewer.viewMetadata"
              }
            ]
          },
          {
            "labelId": "gnviewer.download",
            "disablePluginIf": "{!state('selectedLayerPermissions').includes('download_resourcebase')}",
            "type": "dropdown",
            "items": [
              {
                "type": "plugin",
                "name": "LayerDownload"
              },
              {
                "type": "plugin",
                "name": "IsoDownload"
              },
              {
                "type": "plugin",
                "name": "DublinCoreDownload"
              }
            ]
          }
        ],
        "rightMenuItems": [
          {
            "type": "plugin",
            "name": "FullScreen"
          }
        ]
      }
    },
    {
      "name": "Share",
      "cfg": {
        "containerPosition": "rightOverlay",
        "enableGeoLimits": true
      }
    },
    {
      "name": "DetailViewer",
      "cfg": {
        "containerPosition": "rightOverlay",
        "tabs": [
          {
            "type": "tab",
            "id": "info",
            "labelId": "gnviewer.info",
            "items": [
              {
                "type": "text",
                "labelId": "gnviewer.title",
                "value": "{context.get(state('gnResourceData'), 'title')}"
              },
              {
                "type": "link",
                "labelId": "gnviewer.owner",
                "href": "{'/people/profile/' + context.get(state('gnResourceData'), 'owner.username')}",
                "value": "{context.getUserResourceName(context.get(state('gnResourceData'), 'owner'))}",
                "disableIf": "{!context.get(state('gnResourceData'), 'owner.username')}"
              },
              {
                "type": "date",
                "format": "YYYY-MM-DD HH:mm",
                "labelId": "{'gnviewer.'+context.get(state('gnResourceData'), 'date_type')}",
                "value": "{context.get(state('gnResourceData'), 'date')}"
              },
              {
                "type": "date",
                "format": "YYYY-MM-DD HH:mm",
                "labelId": "gnviewer.created",
                "value": "{context.get(state('gnResourceData'), 'created')}"
              },
              {
                "type": "date",
                "format": "YYYY-MM-DD HH:mm",
                "labelId": "gnviewer.lastModified",
                "value": "{context.get(state('gnResourceData'), 'last_updated')}"
              },
              {
                "type": "query",
                "labelId": "gnviewer.resourceType",
                "value": "{context.get(state('gnResourceData'), 'resource_type')}",
                "pathname": "/",
                "query": {
                  "f": "{context.get(state('gnResourceData'), 'resource_type')}"
                }
              },
              {
                "type": "{context.isDocumentExternalSource(state('gnResourceData')) ? 'link' : 'text'}",
                "labelId": "gnviewer.sourceType",
                "value": "{context.get(state('gnResourceData'), 'sourcetype', '').toLowerCase()}",
                "href": "{context.get(state('gnResourceData'), 'href')}"
              },
              {
                "type": "link",
                "labelId": "gnviewer.doi",
                "href": "{'https://doi.org/' + context.get(state('gnResourceData'), 'doi')}",
                "value": "{context.get(state('gnResourceData'), 'doi')}"
              },
              {
                "type": "query",
                "labelId": "gnviewer.category",
                "value": "{context.get(state('gnResourceData'), 'category.gn_description')}",
                "pathname": "/",
                "query": {
                  "filter{category.identifier}": "{context.get(state('gnResourceData'), 'category.identifier')}"
                }
              },
              {
                "type": "link",
                "labelId": "gnviewer.pointOfContact",
                "value": "{context.getUserResourceNames(context.get(state('gnResourceData'), 'poc'))}",
                "disableIf": "{!context.get(state('gnResourceData'), 'poc')}"
              },
              {
                "type": "query",
                "labelId": "gnviewer.keywords",
                "value": "{context.get(state('gnResourceData'), 'keywords')}",
                "valueKey": "name",
                "pathname": "/",
                "queryTemplate": {
                  "filter{keywords.slug.in}": "${slug}"
                }
              },
              {
                "type": "query",
                "labelId": "gnviewer.regions",
                "value": "{context.get(state('gnResourceData'), 'regions')}",
                "valueKey": "name",
                "pathname": "/",
                "queryTemplate": {
                  "filter{regions.code.in}": "${code}"
                }
              },
              {
                "type": "text",
                "labelId": "gnviewer.attribution",
                "value": "{context.get(state('gnResourceData'), 'attribution')}"
              },
              {
                "type": "text",
                "labelId": "gnviewer.language",
                "value": "{context.get(state('gnResourceData'), 'language')}"
              },
              {
                "type": "html",
                "labelId": "gnviewer.supplementalInformation",
                "value": "{context.get(state('gnResourceData'), 'supplemental_information')}"
              },
              {
                "type": "date",
                "format": "YYYY-MM-DD HH:mm",
                "labelId": "gnviewer.temporalExtent",
                "value": {
                  "start": "{context.get(state('gnResourceData'), 'temporal_extent_start')}",
                  "end": "{context.get(state('gnResourceData'), 'temporal_extent_end')}"
                }
              },
              {
                "type": "link",
                "style": "label",
                "labelId": "gnviewer.viewFullMetadata",
                "href": "{context.getMetadataDetailUrl(state('gnResourceData'))}",
                "disableIf": "{!context.getMetadataDetailUrl(state('gnResourceData'))}"
              }
            ]
          },
          {
            "type": "locations",
            "id": "locations",
            "labelId": "gnviewer.locations",
            "items": "{({extent: context.get(state('gnResourceData'), 'extent')})}"
          },
          {
            "type": "attribute-table",
            "id": "attributes",
            "labelId": "gnviewer.attributes",
            "disableIf": "{context.get(state('gnResourceData'), 'resource_type') !== 'dataset'}",
            "items": "{context.get(state('gnResourceData'), 'attribute_set')}"
          },
          {
            "type": "linked-resources",
            "id": "related",
            "labelId": "gnviewer.linkedResources.label",
            "items": "{context.get(state('gnResourceData'), 'linkedResources')}"
          },
          {
            "type": "assets",
            "id": "assets",
            "labelId": "gnviewer.assets",
            "items": "{context.get(state('gnResourceData'), 'assets')}"
          }
        ]
      }
    },
    {
      "name": "DeleteResource"
    },
    {
      "name": "FullScreen"
    },
    {
      "name": "IsoDownload"
    },
    {
      "name": "DublinCoreDownload"
    },
    {
      "name": "LayerDownload",
      "cfg": {
        "disablePluginIf": "{!state('selectedLayerPermissions').includes('download_resourcebase')}",
        "defaultSelectedService": "wfs",
        "hideServiceSelector": true,
        "formats": [
          { "name": "excel", "label": "Excel", "validServices": ["wfs"] },
          { "name": "csv", "label": "CSV", "validServices": ["wfs"] }
        ]
      }
    },
    {
      "name": "FullScreen",
      "override": {
        "Toolbar": {
          "alwaysVisible": true
        }
      }
    },
    {
      "name": "Notifications"
    },
    {
      "name": "TabularPreview"
    }
  ],
  "tabular-collection_viewer": [
    {
      "name": "ActionNavbar",
      "cfg": {
        "containerPosition": "header",
        "leftMenuItems": [
          {
            "type": "link",
            "size": "md",
            "href": "#/all",
            "labelId": "gnviewer.allResources"
          },
          {
            "type": "plugin",
            "size": "md",
            "name": "DetailViewerButton"
          },
          {
            "labelId": "gnviewer.edit",
            "type": "dropdown",
            "disableIf": "{!context.resourceHasPermission(state('gnResourceData'), 'change_resourcebase')}",
            "items": [
              {
                "type": "link",
                "href": "{context.getMetadataUrl(state('gnResourceData'))}",
                "labelId": "gnviewer.editMetadata"
              },
              {
                "type": "link",
                "href": "{'/datasets/' + (state('gnResourceData') || {}).alternate + '/metadata_upload'}",
                "labelId": "gnviewer.metadataUpload"
              }
            ]
          },
          {
            "labelId": "gnviewer.view",
            "type": "dropdown",
            "items": [
              {
                "type": "plugin",
                "name": "DetailViewerButton"
              },
              {
                "type": "link",
                "href": "{context.getMetadataDetailUrl(state('gnResourceData'))}",
                "labelId": "gnviewer.viewMetadata"
              }
            ]
          },
          {
            "type": "plugin",
            "name": "Share"
          },
          {
            "type": "plugin",
            "name": "DeleteResource",
            "disableIf": "{!context.resourceHasPermission(state('gnResourceData'), 'delete_resourcebase')}"
          },
          {
            "type": "divider",
            "authenticated": true
          },
          {
            "labelId": "gnviewer.download",
            "disablePluginIf": "{!state('selectedLayerPermissions').includes('download_resourcebase')}",
            "type": "dropdown",
            "items": [
              {
                "type": "plugin",
                "name": "LayerDownload"
              },
              {
                "type": "plugin",
                "name": "IsoDownload"
              },
              {
                "type": "plugin",
                "name": "DublinCoreDownload"
              }
            ]
          }
        ],
        "rightMenuItems": [
          {
            "type": "plugin",
            "name": "FullScreen"
          }
        ]
      }
    },
    {
      "name": "Share",
      "cfg": {
        "containerPosition": "rightOverlay",
        "enableGeoLimits": true
      }
    },
    {
      "name": "DetailViewer",
      "cfg": {
        "containerPosition": "rightOverlay",
        "tabs": [
          {
            "type": "tab",
            "id": "info",
            "labelId": "gnviewer.info",
            "items": [
              {
                "type": "text",
                "labelId": "gnviewer.title",
                "value": "{context.get(state('gnResourceData'), 'title')}"
              },
              {
                "type": "link",
                "labelId": "gnviewer.owner",
                "href": "{'/people/profile/' + context.get(state('gnResourceData'), 'owner.username')}",
                "value": "{context.getUserResourceName(context.get(state('gnResourceData'), 'owner'))}",
                "disableIf": "{!context.get(state('gnResourceData'), 'owner.username')}"
              },
              {
                "type": "date",
                "format": "YYYY-MM-DD HH:mm",
                "labelId": "{'gnviewer.'+context.get(state('gnResourceData'), 'date_type')}",
                "value": "{context.get(state('gnResourceData'), 'date')}"
              },
              {
                "type": "date",
                "format": "YYYY-MM-DD HH:mm",
                "labelId": "gnviewer.created",
                "value": "{context.get(state('gnResourceData'), 'created')}"
              },
              {
                "type": "date",
                "format": "YYYY-MM-DD HH:mm",
                "labelId": "gnviewer.lastModified",
                "value": "{context.get(state('gnResourceData'), 'last_updated')}"
              },
              {
                "type": "query",
                "labelId": "gnviewer.resourceType",
                "value": "{context.get(state('gnResourceData'), 'resource_type')}",
                "pathname": "/",
                "query": {
                  "f": "{context.get(state('gnResourceData'), 'resource_type')}"
                }
              },
              {
                "type": "{context.isDocumentExternalSource(state('gnResourceData')) ? 'link' : 'text'}",
                "labelId": "gnviewer.sourceType",
                "value": "{context.get(state('gnResourceData'), 'sourcetype', '').toLowerCase()}",
                "href": "{context.get(state('gnResourceData'), 'href')}"
              },
              {
                "type": "link",
                "labelId": "gnviewer.doi",
                "href": "{'https://doi.org/' + context.get(state('gnResourceData'), 'doi')}",
                "value": "{context.get(state('gnResourceData'), 'doi')}"
              },
              {
                "type": "query",
                "labelId": "gnviewer.category",
                "value": "{context.get(state('gnResourceData'), 'category.gn_description')}",
                "pathname": "/",
                "query": {
                  "filter{category.identifier}": "{context.get(state('gnResourceData'), 'category.identifier')}"
                }
              },
              {
                "type": "link",
                "labelId": "gnviewer.pointOfContact",
                "value": "{context.getUserResourceNames(context.get(state('gnResourceData'), 'poc'))}",
                "disableIf": "{!context.get(state('gnResourceData'), 'poc')}"
              },
              {
                "type": "query",
                "labelId": "gnviewer.keywords",
                "value": "{context.get(state('gnResourceData'), 'keywords')}",
                "valueKey": "name",
                "pathname": "/",
                "queryTemplate": {
                  "filter{keywords.slug.in}": "${slug}"
                }
              },
              {
                "type": "query",
                "labelId": "gnviewer.regions",
                "value": "{context.get(state('gnResourceData'), 'regions')}",
                "valueKey": "name",
                "pathname": "/",
                "queryTemplate": {
                  "filter{regions.code.in}": "${code}"
                }
              },
              {
                "type": "text",
                "labelId": "gnviewer.attribution",
                "value": "{context.get(state('gnResourceData'), 'attribution')}"
              },
              {
                "type": "text",
                "labelId": "gnviewer.language",
                "value": "{context.get(state('gnResourceData'), 'language')}"
              },
              {
                "type": "html",
                "labelId": "gnviewer.supplementalInformation",
                "value": "{context.get(state('gnResourceData'), 'supplemental_information')}"
              },
              {
                "type": "date",
                "format": "YYYY-MM-DD HH:mm",
                "labelId": "gnviewer.temporalExtent",
                "value": {
                  "start": "{context.get(state('gnResourceData'), 'temporal_extent_start')}",
                  "end": "{context.get(state('gnResourceData'), 'temporal_extent_end')}"
                }
              },
              {
                "type": "link",
                "style": "label",
                "labelId": "gnviewer.viewFullMetadata",
                "href": "{context.getMetadataDetailUrl(state('gnResourceData'))}",
                "disableIf": "{!context.getMetadataDetailUrl(state('gnResourceData'))}"
              }
            ]
          },
          {
            "type": "locations",
            "id": "locations",
            "labelId": "gnviewer.locations",
            "items": "{({extent: context.get(state('gnResourceData'), 'extent')})}"
          },
          {
            "type": "linked-resources",
            "id": "related",
            "labelId": "gnviewer.linkedResources.label",
            "items": "{context.get(state('gnResourceData'), 'linkedResources')}"
          },
          {
            "type": "assets",
            "id": "assets",
            "labelId": "gnviewer.assets",
            "items": "{context.get(state('gnResourceData'), 'assets')}"
          }
        ]
      }
    },
    {
      "name": "DeleteResource"
    },
    {
      "name": "FullScreen"
    },
    {
      "name": "IsoDownload"
    },
    {
      "name": "DublinCoreDownload"
    },
    {
      "name": "LayerDownload",
      "cfg": {
        "disablePluginIf": "{!state('selectedLayerPermissions').includes('download_resourcebase')}",
        "defaultSelectedService": "wfs",
        "hideServiceSelector": true,
        "formats": [
          { "name": "excel", "label": "Excel", "validServices": ["wfs"] },
          { "name": "csv", "label": "CSV", "validServices": ["wfs"] }
        ]
      }
    },
    {
      "name": "FullScreen",
      "override": {
        "Toolbar": {
          "alwaysVisible": true
        }
      }
    },
    {
      "name": "Notifications"
    },
    {
      "name": "TabularCollectionViewer"
    }
  ]
}

```

## Upload

A datapackage can be uploaded as ZIP-file.
In the ZIP-file a `datapackage.json` is expected to be found, along with any other file referenced from the `datapackage.json`.
At the moment only CSV-files were tested.

You can use [this test zip file](./importer_datapackage/handlers/datapackage/data/valid_data.zip) to start.

## Limitations

- no fancy formats or regexes
- geonode-mapstore-client currently [mixes file specs for upload](https://github.com/GeoNodeUserGroup-DE/importer-datapackage/issues/3)
- primary keys are imported without any database constraints
- ...

Also check [the issues page](https://github.com/GeoNodeUserGroup-DE/importer-datapackage/issues) for more quirks and findings.

## Funding

This contrib app was funded by

| Logo | Funder |
|------|--------|
| <img alt="Thünen Logo" align="middle" height="50" src="https://www.thuenen.de/typo3conf/ext/vc_theme/Resources/Public/Graphics/SVG-Logo.svg"/> | [Thünen-Institute](https://www.thuenen.de) | 
| <img alt="ZALF Logo" align="middle" height="50" src="https://www.zalf.de/_layouts/15/images/zalfweb/logo_zalf.png"/> | [Leibniz Centre for Agricultural Landscape Research](https://www.zalf.de/) |


