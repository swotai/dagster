from dagster import ModeDefinition, resource
from dagster._legacy import pipeline, solid


@resource
def external_service():
    ...


@solid(required_resource_keys={"external_service"})
def do_something():
    ...


@pipeline(
    mode_defs=[ModeDefinition(resource_defs={"external_service": external_service})]
)
def do_it_all():
    do_something()
