import os

from .exceptions import InvalidDataPackageFileException


def _raise_validation_error(report_or_task):
    if report_or_task.valid:
        return

    for error in report_or_task.errors or []:
        if error.message:
            raise InvalidDataPackageFileException(error.message)
    raise InvalidDataPackageFileException()


def validate(file_path):
    if not file_path:
        raise InvalidDataPackageFileException("base file is not provided")

    from frictionless import validate as frictionless_validate

    report = frictionless_validate(file_path)
    _raise_validation_error(report)
    for task in report.tasks or []:
        _raise_validation_error(task)


def process_rows(resource):
    from frictionless import Pipeline, steps
    from frictionless.fields import NumberField

    schema = resource.schema

    number_fields = (
        field
        for field in schema.fields
        if isinstance(field, NumberField) and getattr(field, "decimal_char", ".") != "."
    )

    conversion_steps = [
        steps.cell_convert(
            field_name=field.name,
            function=lambda value, dc=field.decimal_char: float(value.replace(dc, ".")) if isinstance(value, str) else value,
        )
        for field in number_fields
    ]

    pipeline = Pipeline(
        steps=[
            steps.table_normalize(),
            *conversion_steps,
        ]
    )

    original_path = resource.path
    original_file = f"{resource.basepath}/{original_path}"
    transformed = resource.transform(pipeline)
    resource.path = original_path

    processed_file = f"{resource.basepath}/{resource.name}_processed.csv"
    transformed.write(processed_file)
    os.replace(processed_file, original_file)
