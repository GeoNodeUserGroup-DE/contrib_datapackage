#!/bin/bash
set -a
. ./.env_test
set +a

coverage run --source='.' --omit="*/tests*" /usr/src/geonode/manage.py test importer_datapackage -v2 --noinput
