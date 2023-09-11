from rest_framework.exceptions import APIException
from rest_framework import status


class InvalidDataPackageFileException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The data package file provided is invalid"
    default_code = "invalid_datapackage"
    category = "importer"
