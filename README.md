# Datapackage Support for geonode-importer

This module provides a datapackage handler for the geonode-importer.
The app aims to be compatible with geonode-importer v1.0.9, but can be used only with GeoNode v4.3.x.

The handler leverages the [OGR VRT format](https://gdal.org/drivers/vector/vrt.html) to import layers described in a [tabular data resource schema](https://specs.frictionlessdata.io/tabular-data-resource/).
To make this possible a schema mapping takes place.

> :alert Warning:
>
> The project is under development and only a minimal set of possible features are supported.
> Check out the [development setup](https://github.com/GeoNodeUserGroup-DE/geonode-dev-datapackage) which is base on the [Geonode Docker blueprint](https://github.com/GeoNodeUserGroup-DE/geonode-blueprint-docker).
>
> Feel free to contribute by [creating an issue](https://github.com/GeoNodeUserGroup-DE/importer-datapackage/issues) [or even a PR](https://github.com/GeoNodeUserGroup-DE/importer-datapackage/pulls) on GitHub.

## Installation

The following steps are necessary so GeoNode is able to handle the frictionless datapackage format:

- Installation of the datapackage handler for the geonode-importer
- Manual integration of a UI code adjustments
- Configuration of the MapStore plugin

### Install Datapackage Handler

The module can be installed as normal python module.
Add it to your `requirements.txt` and let it install via `pip`.
For development let `pip` install direcly the branch of your current interest by adding to the `requirements.txt`:

```
-e git+https://github.com/GeoNodeUserGroup-DE/importer-datapackage.git@main#egg=importer_datapackage
```

The URL above references the `main` branch.

Once installed, the `importer_datapackage.handlers.datapackage.handler.DataPackageFileHandler` has to be added to the `IMPORTER_HANDLERS`.
Open the `settings.py` and add

```py
IMPORTER_HANDLERS = (
    'importer_datapackage.handlers.datapackage.handler.DataPackageFileHandler',
    *IMPORTER_HANDLERS,
)
```

### Geonode Mapstore Client Plugin

There is a geonode-mapstore-client plugin to preview tabular data.
To let the UI recognize and handle `tabular` datasets, you have to integrate code which resides in [branch datapackage_tabular-data](https://github.com/GeoNodeUserGroup-DE/geonode-mapstore-client/tree/datapackage_tabular-data) of the [GeoNodeUserGroup-DE geonode-mapstore-client fork](https://github.com/GeoNodeUserGroup-DE/geonode-mapstore-client).

## Configuration

To enable the geonode-mapstore-plugin add the following plugin configuration to your `localConfig.json`:

```json
"plugins": {
    
   "tabular_viewer":[
      {
         "name":"ActionNavbar",
         "cfg":{
            "containerPosition":"header",
            "titleItems":[
               {
                  "type":"plugin",
                  "name":"DetailViewerButton"
               }
            ],
            "leftMenuItems":[
               {
                  "labelId":"gnviewer.edit",
                  "type":"dropdown",
                  "disableIf":"{!context.resourceHasPermission(state('gnResourceData'), 'change_resourcebase')}",
                  "items":[
                     {
                        "type":"plugin",
                        "name":"DetailViewerButton"
                     },
                     {
                        "type":"link",
                        "href":"{'#/dataset/' + (state('gnResourceData') || {}).pk + '/edit/data'}",
                        "labelId":"gnviewer.editData",
                        "disableIf":"{!context.resourceHasPermission(state('gnResourceData'), 'change_dataset_data')}"
                     },
                     {
                        "type":"link",
                        "href":"{'#/dataset/' + (state('gnResourceData') || {}).pk + '/edit/style'}",
                        "labelId":"gnviewer.editStyle",
                        "disableIf":"{!context.resourceHasPermission(state('gnResourceData'), 'change_dataset_style')}"
                     },
                     {
                        "type":"link",
                        "href":"{context.getMetadataUrl(state('gnResourceData'))}",
                        "labelId":"gnviewer.editMetadata"
                     },
                     {
                        "type":"link",
                        "href":"{'/datasets/' + (state('gnResourceData') || {}).alternate + '/style_upload'}",
                        "labelId":"gnviewer.styleUpload",
                        "disableIf":"{!context.resourceHasPermission(state('gnResourceData'), 'change_dataset_style')}"
                     },
                     {
                        "type":"link",
                        "href":"{'/datasets/' + (state('gnResourceData') || {}).alternate + '/metadata_upload'}",
                        "labelId":"gnviewer.metadataUpload"
                     }
                  ]
               },
               {
                  "labelId":"gnviewer.view",
                  "type":"dropdown",
                  "disableIf":"{context.resourceHasPermission(state('gnResourceData'), 'change_resourcebase')}",
                  "items":[
                     {
                        "type":"link",
                        "href":"{context.getMetadataDetailUrl(state('gnResourceData'))}",
                        "labelId":"gnviewer.viewMetadata"
                     },
                     {
                        "type":"link",
                        "href":"{'#/dataset/' + (state('gnResourceData') || {}).pk + '/edit/data'}",
                        "labelId":"gnviewer.viewData",
                        "disableIf":"{state('gnResourceData') && (state('gnResourceData').subtype === 'raster' || state('gnResourceData').subtype === 'remote')}"
                     }
                  ]
               },
               {
                  "type":"plugin",
                  "name":"Share"
               },
               {
                  "type":"plugin",
                  "name":"DeleteResource",
                  "disableIf":"{!context.resourceHasPermission(state('gnResourceData'), 'delete_resourcebase')}"
               },
               {
                  "type":"divider",
                  "authenticated":true
               },
               {
                  "type":"plugin",
                  "name":"Print"
               },
               {
                  "labelId":"gnviewer.download",
                  "disablePluginIf":"{!state('selectedLayerPermissions').includes('download_resourcebase')}",
                  "type":"dropdown",
                  "items":[
                     {
                        "type":"plugin",
                        "name":"LayerDownload"
                     },
                     {
                        "type":"plugin",
                        "name":"IsoDownload"
                     },
                     {
                        "type":"plugin",
                        "name":"DublinCoreDownload"
                     }
                  ]
               }
            ],
            "rightMenuItems":[
               {
                  "type":"plugin",
                  "name":"FullScreen"
               }
            ]
         }
      },
      {
         "name":"Share",
         "cfg":{
            "containerPosition":"rightOverlay",
            "enableGeoLimits":true
         }
      },
      {
         "name":"DetailViewer",
         "cfg":{
            "containerPosition":"rightOverlay"
         }
      },
      {
         "name":"DeleteResource"
      },
      {
         "name":"FullScreen"
      },
      {
         "name":"IsoDownload"
      },
      {
         "name":"DublinCoreDownload"
      },
      {
         "name":"LayerDownload",
         "cfg":{
            "disablePluginIf":"{!state('selectedLayerPermissions').includes('download_resourcebase')}",
            "formats":[
               {
                  "name":"application/wfs-collection-1.1",
                  "label":"GML (WFS 1.1.0 FeatureCollection)",
                  "type":"vector",
                  "validServices":[
                     "wps"
                  ]
               },
               {
                  "name":"text/csv",
                  "label":"CSV",
                  "type":"vector",
                  "validServices":[
                     "wps"
                  ]
               }
            ]
         }
      },
      {
         "name":"FullScreen",
         "override":{
            "Toolbar":{
               "alwaysVisible":true
            }
         }
      },
      {
         "name":"Notifications"
      },
      {
         "name":"TabularPreview"
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
- primary keys are imported without any database constraints
- ...

## Funding

<img alt="Thünen Logo" align="middle" height="50" src="https://www.thuenen.de/typo3conf/ext/vc_theme/Resources/Public/Graphics/SVG-Logo.svg"/>

This contrib app was funded by the [Thünen-Institute](https://www.thuenen.de)
