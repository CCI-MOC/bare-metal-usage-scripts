import csv
import math
import logging
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass

from bare_metal_billing import models


BM_SU_LIST = [
    "BM FC430",
    "BM FC830",
    "BM GPUA100SXM4",
    "BM GPUH100",
]

RESOURCE_CLASS_2_SU_MAPPING = {
    "lenovo-sd665nv3-h100": "BM GPUH100",
    "lenovo-sd650nv2-a100": "BM GPUA100SXM4",
    "sd650nv2": "BM GPUA100SXM4",
    "fc430": "BM FC430",
    "fc830": "BM FC830",
}

SU_RESOURCE_LIST = ["vCPUs", "RAM", "GPUs"]


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class InvoiceWriter:
    HEADERS = [
        "Invoice Month",
        "Project - Allocation",
        "Project - Allocation ID",
        "Manager (PI)",
        "Cluster Name",
        "Invoice Email",
        "Invoice Address",
        "Institution",
        "Institution - Specific Code",
        "SU Hours (GBhr or SUhr)",
        "SU Type",
        "Rate",
        "Cost",
    ]

    invoice_month: str
    project_invoices: list[models.ProjectUsage]
    su_rates: models.SURates
    output_file: str

    def write_csv(self):
        csv_rows = [self.HEADERS]
        for project_invoice in self.project_invoices:
            for su_type, su_hour in project_invoice.su_hours.items():
                csv_rows.append(
                    (
                        self.invoice_month,
                        project_invoice.project_name,
                        project_invoice.project_name,
                        "",
                        "bm",  # Cluster Name
                        "",
                        "",
                        "",
                        "",
                        su_hour,
                        su_type,
                        self.su_rates.root.get(
                            su_type, Decimal(0)
                        ),  # Unknown SU types are not billed
                        self.su_rates.root.get(su_type, Decimal(0)) * su_hour,
                    )
                )

        with open(self.output_file, "w") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerows(csv_rows)


def _get_su_type(lease_info: models.BMNodeUsage):
    rc = lease_info.resource_class
    return RESOURCE_CLASS_2_SU_MAPPING.get(rc, rc)


def _get_running_time(
    lease_info: models.BMNodeUsage, start_time: datetime, end_time: datetime
):
    start_time = _clamp_time(lease_info.start_time, start_time, end_time)
    end_time = (
        end_time
        if lease_info.expire_time
        is None  # Assumes lease is still running if no expire time given
        else _clamp_time(lease_info.expire_time, start_time, end_time)
    )
    return math.ceil((end_time - start_time).total_seconds() / 3600)


def _clamp_time(time, min_time, max_time):
    if time < min_time:
        time = min_time
    if time > max_time:
        time = max_time
    return time


def get_project_invoices(
    bm_usage_data: models.BMUsageData, start_time: datetime, end_time: datetime
) -> list[models.ProjectUsage]:
    project_usage_dict = {}
    for lease_info in bm_usage_data.root:
        project_name = lease_info.project
        if project_name == "":
            logger.error(f"Lease {lease_info.uuid} has empty project name.")

        project_usage_dict.setdefault(
            project_name, models.ProjectUsage(project_name=project_name, su_hours={})
        )

        su_type = _get_su_type(lease_info)
        if su_type not in BM_SU_LIST:
            logger.warning(
                f"Unknown resource class {lease_info.resource_class} (resource {lease_info.resource}) in lease {lease_info.uuid}."
            )
        su_hours = _get_running_time(lease_info, start_time, end_time)

        project_usage_dict[project_name].add_usage(su_type, su_hours)

    return list(project_usage_dict.values())
