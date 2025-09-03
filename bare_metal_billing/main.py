from decimal import Decimal
from datetime import datetime, timedelta
import json
import argparse
import logging

from nerc_rates import load_from_url

from bare_metal_billing import models, billing


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_time_from_string(time_str: str) -> datetime:
    return datetime.fromisoformat(time_str)


def parse_time_argument(arg):
    if isinstance(arg, str):
        return parse_time_from_string(arg)
    return arg


def parse_excluded_time_ranges(arg_list: list[str]) -> list[tuple[datetime, datetime]]:
    def check_overlapping_intervals(intervals: list[tuple[datetime, datetime]]):
        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        for i in range(1, len(sorted_intervals)):
            if sorted_intervals[i][0] < sorted_intervals[i - 1][1]:
                raise ValueError(
                    f"Overlapping time ranges: {sorted_intervals[i-1]} and {sorted_intervals[i]}"
                )

    time_ranges = []
    for time_range_str in arg_list:
        start_str, end_str = time_range_str.split(",")
        start_time, end_time = [parse_time_from_string(i) for i in (start_str, end_str)]
        if start_time >= end_time:
            raise ValueError(
                f"Start time {start_time} must be before end time {end_time}."
            )
        time_ranges.append((start_time, end_time))

    check_overlapping_intervals(time_ranges)
    return time_ranges


def default_start_argument():
    d = (datetime.today() - timedelta(days=1)).replace(day=1)
    d = d.replace(hour=0, minute=0, second=0, microsecond=0)
    return d


def default_end_argument():
    d = datetime.today()
    d = d.replace(hour=0, minute=0, second=0, microsecond=0)
    return d


def main():
    parser = argparse.ArgumentParser(
        prog="python -m bare_metal_billing.main",
        description="Simple Bare Metal Invoicing",
    )
    parser.add_argument(
        "--start",
        default=default_start_argument(),
        type=parse_time_argument,
        help=(
            "Start of the invoicing period. (YYYY-MM-DD)."
            " Defaults to start of last month if 1st of a month,"
            " or start of this month otherwise."
        ),
    )
    parser.add_argument(
        "--end",
        default=default_end_argument(),
        type=parse_time_argument,
        help=(
            "End of the invoicing period. (YYYY-MM-DD)."
            " Not inclusive. Defaults to today."
        ),
    )
    parser.add_argument(
        "--invoice-month",
        default=default_start_argument().strftime("%Y-%m"),
        help=(
            "Use the first column for Invoice Month, rather than Interval."
            " Defaults to month of start. (YYYY-MM)."
        ),
    )
    parser.add_argument(
        "bm_usage_file",
        help="Bare Metal usage JSON file to be processed",
    )
    parser.add_argument(
        "--rate-fc430-su", default=0, type=Decimal, help="Rate of FC430 SU/hr"
    )
    parser.add_argument(
        "--rate-fc830-su", default=0, type=Decimal, help="Rate of FC830 SU/hr"
    )
    parser.add_argument(
        "--rate-gpu-a100sxm4-su",
        default=0,
        type=Decimal,
        help="Rate of GPU A100 SXM4 SU/hr",
    )
    parser.add_argument(
        "--rate-gpu-h100-su", default=0, type=Decimal, help="Rate of GPU H100 SU/hr"
    )
    parser.add_argument(
        "--output-file",
        default="bm_invoices.csv",
        help="Output path for invoice in CSV format.",
    )
    parser.add_argument(
        "--use-nerc-rates",
        action="store_true",
        help=(
            "Set to use usage rates and su definitions from nerc-rates repo."
            "If not set, su defintions will be taken from cli arguments, or default"
            "to 0 for each SU's resources"
        ),
    )
    parser.add_argument(
        "--excluded-time-ranges",
        default=None,
        nargs="+",
        help="List of time ranges excluded from billing, in format of '<ISO timestamp>,<ISO timestamp>'.",
    )

    args = parser.parse_args()

    logger.info(f"Processing invoices for month {args.invoice_month}.")
    logger.info(f"Interval for processing {args.start} - {args.end}.")
    logger.info(f"Invoice file will be saved to {args.output_file}.")

    excluded_time_ranges = (
        parse_excluded_time_ranges(args.excluded_time_ranges)
        if args.excluded_time_ranges
        else None
    )

    su_rates_dict = {}
    if args.use_nerc_rates:
        nerc_repo_rates = load_from_url()
        for su_name in billing.BM_SU_LIST:
            su_rates_dict[su_name] = nerc_repo_rates.get_value_at(
                f"{su_name} SU Rate", args.invoice_month, Decimal
            )
    else:
        su_rates_dict = {
            "BM FC430": args.rate_fc430_su,
            "BM FC830": args.rate_fc830_su,
            "BM GPUA100SXM4": args.rate_gpu_a100sxm4_su,
            "BM GPUH100": args.rate_gpu_h100_su,
        }
    su_rates = models.SURates.model_validate(
        su_rates_dict,
    )

    with open(args.bm_usage_file, "r") as f:
        input_bm_json = json.load(f)

    input_invoice = models.BMUsageData.model_validate(input_bm_json)
    project_invoices = billing.get_project_invoices(
        input_invoice, args.start, args.end, excluded_time_ranges
    )

    invoice_writer = billing.InvoiceWriter(
        args.invoice_month,
        project_invoices,
        su_rates,
        args.output_file,
    )
    invoice_writer.write_csv()


if __name__ == "__main__":
    main()
