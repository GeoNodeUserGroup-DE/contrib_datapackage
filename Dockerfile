FROM geonode/geonode-base:latest-ubuntu-22.04

# This app is only usable against the GeoNode fork that carries the "tabular"
# subtype support (see README) - stock GeoNode does not build an attribute set
# for non-spatial datasets at all. Override at build time to test another ref:
#   docker build --build-arg GEONODE_REF=release-4.4.4 .
ARG GEONODE_REPO=https://github.com/zalf-rdm/geonode.git
ARG GEONODE_REF=GeoNode-v4.4.3-zalf00X

RUN rm -rf /usr/src/geonode
RUN git clone ${GEONODE_REPO} /usr/src/geonode \
    && cd /usr/src/geonode \
    && git checkout ${GEONODE_REF}

# Pulls in geonode-importer, frictionless and GDAL bindings - plus a pinned
# release of this very app, which the next step swaps for the checkout.
RUN pip install -r /usr/src/geonode/requirements.txt
RUN pip install coverage

RUN mkdir -p /usr/src/contrib_datapackage
COPY . /usr/src/contrib_datapackage/
WORKDIR /usr/src/contrib_datapackage

RUN pip uninstall -y importer_datapackage \
    && pip install --upgrade -e /usr/src/contrib_datapackage/
