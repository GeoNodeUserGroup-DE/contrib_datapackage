import os
from pathlib import Path

from frictionless.fields import NumberField
from frictionless import (
    validate as fl_validate,
    Package, Resource, Pipeline, steps
)


from .exceptions import InvalidDataPackageFileException


def _handle_error(report_or_task):
    if report_or_task.valid:
        return

    if report_or_task.errors:
        for error in report_or_task.errors:
            if error.message:
                raise InvalidDataPackageFileException(error.message)
            else:
                raise InvalidDataPackageFileException("TODO handle nested errors!")


def validate(file):
    if not file:
        raise InvalidDataPackageFileException("base file is not provided")

    report = fl_validate(file)
    _handle_error(report)
    if report.tasks:
        [_handle_error(task) for task in report.tasks]


def process_rows(resource):
    schema = resource.schema

    def to_point_decimal(field):
        return steps.cell_convert(field_name=field.name, function=lambda x: float)

    fields = schema.fields
    fields = filter(lambda f: type(f) == NumberField, fields)
    fields = filter(lambda f: hasattr(f, 'decimal_char') and f.decimal_char != '.', fields)
    to_point_decimal_steps = map(lambda f: to_point_decimal(f), fields)
    
    pipeline = Pipeline(steps=[
        steps.table_normalize(),
        #*to_point_decimal_steps
    ],)
    
    orig_path = resource.path
    orig_file = f"{resource.basepath}/{orig_path}"
    # reset path after processing pipeline
    res = resource.transform(pipeline)
    resource.path = orig_path
    # do some override ceremony
    processed_file = f"{resource.basepath}/{resource.name}_processed.csv"
    res.write(processed_file)
    os.replace(processed_file, orig_file)

