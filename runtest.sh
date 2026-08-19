#!/bin/bash
set -e

# Resolve the repository root so this behaves the same however it is invoked.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

set -a
. "$ROOT_DIR/.env_test"
set +a

# --keepdb: CI pre-creates and migrates test_geonode/test_geonode_data, because
# CREATE EXTENSION postgis needs superuser and the geonode roles deliberately
# are not one. Without it Django would try to build the databases itself.
coverage run --branch --source=importer_datapackage \
    /usr/src/geonode/manage.py test -v 2 --keepdb --noinput importer_datapackage "$@"
