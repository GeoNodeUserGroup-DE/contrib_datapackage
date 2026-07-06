from setuptools import find_packages, setup


def read_file(path: str):
    with open(path, "r") as file:
        return file.read()


setup_requires = [
    "wheel",
]

setup(
    name="importer-datapackage",
    version="5.0.0+datapackage001",
    url="https://github.com/52north/geonode-contribs",
    description="Datapackage handler for the geonode-importer",
    long_description=read_file("README.md"),
    author="52north",
    author_email="info@52north.org",
    platforms="any",
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Django",
        "License :: OSI Approved :: GNU General Public License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
    ],
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "setuptools>=59",
        "frictionless>=5.18.0",
        # NOTE: no geonode_importer dependency on GeoNode >= 5 — the importer
        # is part of GeoNode core (geonode.upload), and geonode_importer's
        # pins (gdal<=3.4.3) conflict with GeoNode 5 installations.
    ],
)
