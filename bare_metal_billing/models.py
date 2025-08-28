from decimal import Decimal
from typing import Annotated
import datetime
import logging

import pydantic


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def parse_date(v: str | datetime.date) -> datetime.date:
    if isinstance(v, str):
        return datetime.datetime.fromisoformat(v)
    return v


PositiveDecimalField = Annotated[Decimal, pydantic.Field(ge=0)]
PositiveIntField = Annotated[int, pydantic.Field(gt=-1)]
DateField = Annotated[datetime.datetime, pydantic.BeforeValidator(parse_date)]


class BMNodeUsage(pydantic.BaseModel):
    uuid: Annotated[str, pydantic.Field(alias="UUID")]
    resource: Annotated[str, pydantic.Field(alias="Resource")]
    resource_class: Annotated[str, pydantic.Field(alias="Resource Class")]
    project: Annotated[str, pydantic.Field(alias="Project")]
    start_time: Annotated[DateField, pydantic.Field(alias="Start Time")]
    expire_time: Annotated[DateField | None, pydantic.Field(alias="Expire Time")] = None


class BMUsageData(pydantic.RootModel):
    root: list[BMNodeUsage]

    @pydantic.model_validator(mode="after")
    def validate_expire_time(self):
        validated_list = []
        for node_usage in self.root:
            if node_usage.expire_time:
                if node_usage.expire_time < node_usage.start_time:
                    logger.warning(
                        f"Ignoring node lease with Expire Time before Start Time: UUID {node_usage.uuid}"
                    )
                    continue
            validated_list.append(node_usage)
        self.root = validated_list
        return self


class ProjectUsage(pydantic.BaseModel, validate_assignment=True):
    project_name: str
    su_hours: dict[str, PositiveIntField]

    def add_usage(self, su_type: str, hours: PositiveIntField):
        if su_type not in self.su_hours:
            self.su_hours[su_type] = 0
        self.su_hours[su_type] += hours


class SURates(pydantic.RootModel):
    root: dict[str, PositiveDecimalField]
