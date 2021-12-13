from typing import Dict, Literal, Union, cast
from dagster import check
from dagster.config.field import Field

from .config_type import Array, Noneable, ConfigType, ConfigTypeKind, ScalarUnion
from .snap import ConfigSchemaSnapshot, snap_from_config_type


def iterate_config_types(config_type: ConfigType):
    check.inst_param(config_type, "config_type", ConfigType)
    if isinstance(config_type, (Array, Noneable)):
        yield from iterate_config_types(config_type.inner_type)

    if ConfigTypeKind.has_fields(config_type.kind):
        fields = cast(Dict[str, Field], config_type.fields)  # type: ignore
        for field in fields.values():
            yield from iterate_config_types(field.config_type)

    if isinstance(config_type, ScalarUnion):
        yield config_type.scalar_type
        yield from iterate_config_types(config_type.non_scalar_type)

    yield config_type


def config_schema_snapshot_from_config_type(
    config_type: Union[ConfigType, Literal[False]]
) -> ConfigSchemaSnapshot:
    config_type = check.inst_param(cast(ConfigType, config_type), "config_type", ConfigType)
    return ConfigSchemaSnapshot(
        {ct.key: snap_from_config_type(ct) for ct in iterate_config_types(config_type)}
    )
