# Datapackage Support for geonode-importer

This module provides a datapackage handler for the geonode-importer.
The app is compatible with geonode-importer v1.0.5, but can be used only with GeoNode v4.2.x.

The handler leverages the [OGR VRT format](https://gdal.org/drivers/vector/vrt.html) to import layers described in a [tabular data resource schema](https://specs.frictionlessdata.io/tabular-data-resource/).
To make this possible a schema mapping takes place.

The project is still a prototype and only a minimal set of possible features are supported.
Feel free to contribute by [creating an issue](https://github.com/GeoNodeUserGroup-DE/importer-datapackage/issues) [or even a PR](https://github.com/GeoNodeUserGroup-DE/importer-datapackage/pulls) on GitHub.

## Installation

The module can be installed as normal python module.
Add it to your `requirements.txt` and let it install via `pip`.
Once installed, the `importer_datapackage.handlers.datapackage.handler.DataPackageFileHandler` has to be added to the `IMPORTER_HANDLERS`.
Open the `settings.py` and add

```py
IMPORTER_HANDLERS = (
    'importer_datapackage.handlers.datapackage.handler.DataPackageFileHandler',
    *IMPORTER_HANDLERS,
)
```

Note: The module will be compatible [starting from GeoNode v4.2.0](https://github.com/GeoNode/geonode/commit/9ca2f13a083e9ca37cd368106864f32e33176499).

## Upload

A datapackage can be uploaded as ZIP-file.
In the ZIP-file a `datapackage.json` is expected to be found, along with any other file referenced from the `datapackage.json`.
At the moment only CSV-files were tested.

## Limitations

- no fancy formats or regexes
- primary keys are imported without any database constraints
- ...

## Funding

<img alt="Thünen Logo" align="middle" height="50" src="https://www.thuenen.de/typo3conf/ext/vc_theme/Resources/Public/Graphics/SVG-Logo.svg"/>

This contrib app was funded by the [Thünen-Institute](https://www.thuenen.de)