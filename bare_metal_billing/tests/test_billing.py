import tempfile
from unittest import TestCase
from datetime import datetime

from bare_metal_billing import billing, models


HOURS_IN_DAY = 24


class BillingTestBase(TestCase):
    def _get_project_invoice_list(
        self,
        project_names,
        su_hours=None,
    ):
        if not su_hours:
            su_hours = [{}] * len(project_names)
        project_invoice_list = []
        for i in range(len(project_names)):
            project_invoice_list.append(
                models.ProjectUsage.model_validate(
                    {"project_name": project_names[i], "su_hours": su_hours[i]}
                )
            )

        return project_invoice_list


class TestInvoiceWriter(BillingTestBase):
    TEST_SU_RATES = models.SURates({"SU 1": 1.5, "SU 2": 2.5})

    def test_write_csv(self):
        """Two projects, which uses a few different SUs each and an unknown SU type"""
        test_invoice_month = "2025-01"
        test_project_invoice_list = self._get_project_invoice_list(
            ["P1", "P2"],
            [
                {
                    "SU 1": 24,
                    "SU 2": 4,
                },
                {
                    "SU 2": 72,
                    "SU Unknown": 240,
                },
            ],
        )
        answer_invoice = (
            "Invoice Month,Project - Allocation,Project - Allocation ID,Manager (PI),Cluster Name,Invoice Email,Invoice Address,Institution,Institution - Specific Code,SU Hours (GBhr or SUhr),SU Type,Rate,Cost\n"
            "2025-01,P1,P1,,bm,,,,,24,SU 1,1.5,36.0\n"
            "2025-01,P1,P1,,bm,,,,,4,SU 2,2.5,10.0\n"
            "2025-01,P2,P2,,bm,,,,,72,SU 2,2.5,180.0\n"
            "2025-01,P2,P2,,bm,,,,,240,SU Unknown,0,0\n"  # Precision is preserved
        )

        with tempfile.NamedTemporaryFile(mode="w+") as tmp:
            invoice_writer = billing.InvoiceWriter(
                test_invoice_month,
                test_project_invoice_list,
                self.TEST_SU_RATES,
                tmp.name,
            )
            invoice_writer.write_csv()
            self.assertEqual(tmp.read(), answer_invoice)


class TestProjectUsage(BillingTestBase):
    start_time = datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0)
    end_time = datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0)

    def _get_bm_usage_data(
        self,
        projects,
        start_times=None,
        expire_times=None,
        resource_classes=None,
    ):
        if not start_times:
            start_times = [datetime(2000, 1, 1, 0, 0, 0)] * len(projects)
        if not expire_times:
            expire_times = [datetime(2000, 1, 2, 0, 0, 0)] * len(projects)
        if not resource_classes:
            resource_classes = ["UKNOWN"] * len(projects)
        bm_usage_list = []
        for i in range(len(projects)):
            bm_usage_list.append(
                models.BMNodeUsage.model_validate(
                    {
                        "UUID": "uuid",
                        "Project": projects[i],
                        "Resource": "r",
                        "Resource Class": resource_classes[i],
                        "Start Time": start_times[i],
                        "Expire Time": expire_times[i],
                    }
                )
            )

        return models.BMUsageData.model_validate(bm_usage_list)

    def test_two_nodes_one_project(self):
        """One project has two leases using the same SU"""
        test_usage_data = self._get_bm_usage_data(
            ["P1", "P1"],
            resource_classes=["fc430", "fc430"],
            start_times=[datetime(1997, 1, 1, 0, 0, 0), datetime(1997, 1, 1, 0, 0, 0)],
            expire_times=[
                datetime(2000, 1, 1, 23, 59, 59),
                datetime(2000, 1, 2, 23, 0, 2),
            ],  # Lease duration of 1 and 2 days in billing period, 3 days total
        )
        answer_project_invoices = self._get_project_invoice_list(
            ["P1"], [{"BM FC430": HOURS_IN_DAY * 3}]
        )
        output_project_invoices = billing.get_project_invoices(
            test_usage_data, self.start_time, self.end_time
        )
        self.assertEqual(output_project_invoices, answer_project_invoices)

    def test_not_expired(self):
        """Nodes not expired are considered running for entire billing period"""
        test_usage_data = self._get_bm_usage_data(
            ["P1", "P1"],
            resource_classes=["fc430", "fc430"],
            start_times=[datetime(1997, 1, 1, 0, 0, 0), datetime(1997, 1, 1, 0, 0, 0)],
            expire_times=[
                datetime(2000, 1, 2, 0, 0, 0),
                None,
            ],  # Lease duration of 1 day and 1 month
        )
        answer_project_invoices = self._get_project_invoice_list(
            ["P1"], [{"BM FC430": HOURS_IN_DAY + (HOURS_IN_DAY * 31)}]
        )
        output_project_invoices = billing.get_project_invoices(
            test_usage_data, self.start_time, self.end_time
        )
        self.assertEqual(output_project_invoices, answer_project_invoices)

    def test_two_projects(self):
        """Two projects, a few leases each, of different SU types"""
        test_expire_times = [datetime(2000, 1, i, 0, 0, 0) for i in range(2, 7)]
        test_usage_data = self._get_bm_usage_data(
            ["P1", "P1", "P2", "P2", "P2"],
            resource_classes=["fc430", "fc830", "sd650nv2", "sd650nv2", "fc430"],
            start_times=[datetime(2000, 1, 1, 0, 0, 0)] * 5,
            expire_times=test_expire_times,  # Lease duration of 1 to 5 days
        )
        answer_project_invoices = self._get_project_invoice_list(
            ["P1", "P2"],
            [
                {
                    "BM FC430": HOURS_IN_DAY * 1,
                    "BM FC830": HOURS_IN_DAY * 2,
                },
                {
                    "BM GPUA100SXM4": HOURS_IN_DAY * 7,
                    "BM FC430": HOURS_IN_DAY * 5,
                },
            ],
        )
        output_project_invoices = billing.get_project_invoices(
            test_usage_data, self.start_time, self.end_time
        )
        self.assertEqual(output_project_invoices, answer_project_invoices)

    def test_unknown_su(self):
        test_usage_data = self._get_bm_usage_data(
            ["P1", "P1"],
            resource_classes=["ChickFilA", "Popeyes"],
            start_times=[datetime(2000, 1, 1, 0, 0, 0)] * 2,
            expire_times=[
                datetime(2000, 1, 2, 0, 0, 0),
                datetime(2000, 1, 4, 0, 0, 0),
            ],  # 1 and 3 days
        )
        answer_project_invoices = self._get_project_invoice_list(
            ["P1"], [{"ChickFilA": HOURS_IN_DAY * 1, "Popeyes": HOURS_IN_DAY * 3}]
        )

        with self.assertLogs(level="WARNING") as log:
            output_project_invoices = billing.get_project_invoices(
                test_usage_data, self.start_time, self.end_time
            )

        self.assertEqual(output_project_invoices, answer_project_invoices)
        self.assertIn(
            "WARNING:bare_metal_billing.billing:Unknown resource class ChickFilA (resource r) in lease uuid.",
            log.output,
        )

    def test_get_su_type(self):
        # Test known SUs and unknown
        test_bm_usage_data = self._get_bm_usage_data(
            ["P1", "P2", "P3", "P4", "P5"],
            resource_classes=[
                "lenovo-sd650nv2-a100",
                "sd650nv2",
                "fc430",
                "fc830",
                "dummy",
            ],
        )
        answer_su_types = (
            "BM GPUA100SXM4",
            "BM GPUA100SXM4",
            "BM FC430",
            "BM FC830",
            "dummy",
        )
        for i, project_invoice in enumerate(test_bm_usage_data.root):
            self.assertEqual(billing._get_su_type(project_invoice), answer_su_types[i])

    def test_get_su_hours(self):
        # SU hours always rounded up
        test_start_time = datetime(2000, 1, 1, 0, 15, 35)
        test_expire_time = datetime(2000, 1, 1, 4, 0, 0)
        test_bm_usage_data = self._get_bm_usage_data(
            ["P1"],
            start_times=[test_start_time],
            expire_times=[test_expire_time],
        )
        self.assertEqual(
            billing._get_running_time(
                test_bm_usage_data.root[0], self.start_time, self.end_time
            ),
            4,
        )
