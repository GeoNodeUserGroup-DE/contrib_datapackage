FROM geonode/geonode-base:latest-ubuntu-24.04

# This app is only usable against the GeoNode fork that carries the "tabular"
# subtype support - stock GeoNode does not build an attribute set for
# non-spatial datasets at all. The fork also already declares this app in
# INSTALLED_APPS and IMPORTER_HANDLERS, so no settings patching is needed here.
# Override at build time to test another ref:
#   docker build --build-arg GEONODE_REF=issue_665 .
ARG GEONODE_REPO=https://github.com/zalf-rdm/geonode.git
ARG GEONODE_REF=main

RUN rm -rf /usr/src/geonode
RUN git clone ${GEONODE_REPO} /usr/src/geonode \
    && cd /usr/src/geonode \
    && git checkout ${GEONODE_REF}

WORKDIR /usr/src/geonode
# Pulls in GDAL, frictionless and - via the pyproject dependency - a pinned
# release of this very app, which the last step swaps for the checkout.
RUN yes w | pip install -e /usr/src/geonode
RUN pip install coverage

RUN mkdir -p /usr/src/contrib_datapackage
COPY . /usr/src/contrib_datapackage/
WORKDIR /usr/src/contrib_datapackage

RUN pip uninstall -y importer-datapackage || true
RUN pip install --upgrade -e /usr/src/contrib_datapackage/
