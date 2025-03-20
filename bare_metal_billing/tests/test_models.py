from unittest import TestCase
from datetime import datetime

import pydantic

from bare_metal_billing.models import BMUsageData, ProjectUsage


class TestBMUsageData(TestCase):
    def test_valid_two_nodes(self):
        test_usage_data = [
            {
                "UUID": "uuid1",
                "Resource": "r1",
                "Resource Class": "rc1",
                "Resource Properties": {
                    "vendor": "kfc",
                    "local_gb": "100",
                    "cpus": "10",
                    "cpu_arch": "x1024",
                    "memory_mb": "100000",
                    "cpu_model_name": "Fried Chicken",
                    "cpu_frequency": "1000.000",
                },
                "Project": "P1",
                "Start Time": "2025-01-01T16:43:56.312801",
                "End Time": "9999-12-31T23:59:59.999999",
                "Expire Time": "2025-02-01T18:57:51.573792",
                "Fulfill Time": "2025-09-09T16:44:02.995040",
                "Offer UUID": None,
                "Owner": "O1",
                "Parent Lease UUID": None,
                "Status": "deleted",
                "Purpose": None,
            },
            {
                "UUID": "uuid2",
                "Resource": "r2",
                "Resource Class": "rc2",
                "Resource Properties": {
                    "vendor": "Popeyes",
                    "local_gb": "2000",
                    "cpus": "20",
                    "cpu_arch": "x86_64",
                    "memory_mb": "200000",
                    "accelerators": [
                        {
                            "vendor_id": "10de",
                            "device_id": "20b0",
                            "type": "GPU",
                            "device_info": "NVIDIA Corporation GA100",
                            "pci_address": "0000:31:00.0",
                        },
                        {
                            "vendor_id": "10de",
                            "device_id": "20b0",
                            "type": "GPU",
                            "device_info": "NVIDIA Corporation GA100",
                            "pci_address": "0000:4b:00.0",
                        },
                        {
                            "vendor_id": "10de",
                            "device_id": "20b0",
                            "type": "GPU",
                            "device_info": "NVIDIA Corporation GA100",
                            "pci_address": "0000:ca:00.0",
                        },
                        {
                            "vendor_id": "10de",
                            "device_id": "20b0",
                            "type": "GPU",
                            "device_info": "NVIDIA Corporation GA100",
                            "pci_address": "0000:e3:00.0",
                        },
                    ],
                    "cpu_model_name": "Curly Fries",
                    "cpu_frequency": "9001.0000",
                },
                "Project": "P2",
                "Start Time": "2024-05-31T07:17:50.306338",
                "End Time": "9999-12-31T00:00:00",  # Testing missing Expire Time
                "Fulfill Time": "2024-05-31T07:20:33.768000",
                "Offer UUID": None,
                "Owner": "O2",
                "Parent Lease UUID": None,
                "Status": "deleted",
                "Purpose": None,
            },
        ]

        data_model = BMUsageData.model_validate(test_usage_data)
        node_1_info = data_model.root[0]
        properties_to_check = [
            (node_1_info.resource_class, "rc1"),
            (node_1_info.project, "P1"),
            (
                node_1_info.start_time,
                datetime.fromisoformat("2025-01-01T16:43:56.312801"),
            ),
            (
                node_1_info.expire_time,
                datetime.fromisoformat("2025-02-01T18:57:51.573792"),
            ),
        ]

        for node_attr, answer in properties_to_check:
            self.assertEqual(node_attr, answer)

        node_2_info = data_model.root[1]
        properties_to_check = [
            (node_2_info.resource_class, "rc2"),
            (node_2_info.project, "P2"),
            (
                node_2_info.start_time,
                datetime.fromisoformat("2024-05-31T07:17:50.306338"),
            ),
            (node_2_info.expire_time, None),
        ]

        for node_attr, answer in properties_to_check:
            self.assertEqual(node_attr, answer)

    def test_invalid_usage_data(self):
        test_usage_data = [
            {
                "UUID": "uuid2",
                "Resource": "r2",
                "resource class": "rc2",  # Test bad capitalization
                "Project": "P2",
                "Start Time": "2024-01-01T01:01:01.306338",
            }
        ]

        with self.assertRaises(pydantic.ValidationError):
            BMUsageData.model_validate(test_usage_data)

    def test_invalid_expiry_date(self):
        test_usage_data = [
            {
                "UUID": "uuid1",
                "Resource": "r1",
                "Resource Class": "rc1",
                "Project": "P1",
                "Start Time": "2024-01-01T01:01:01",
                "Expire Time": "2024-01-04T01:01:01",
            },
            {
                "UUID": "uuid2",
                "Resource": "r2",
                "Resource Class": "rc2",
                "Project": "P2",
                "Start Time": "2024-01-01T01:01:01.306338",
                "Expire Time": "2023-01-01T01:01:01.306338",  # Expire time before start time
            },
        ]

        with self.assertLogs(level="WARNING") as log:
            data_model = BMUsageData.model_validate(test_usage_data)

        self.assertEqual(len(data_model.root), 1)
        self.assertIn(
            "WARNING:bare_metal_billing.models:Ignoring node lease with Expire Time before Start Time: UUID uuid2",
            log.output,
        )
        node_info = data_model.root[0]
        properties_to_check = [
            (node_info.resource_class, "rc1"),
            (node_info.project, "P1"),
            (
                node_info.start_time,
                datetime.fromisoformat("2024-01-01T01:01:01"),
            ),
            (
                node_info.expire_time,
                datetime.fromisoformat("2024-01-04T01:01:01"),
            ),
        ]

        for node_attr, answer in properties_to_check:
            self.assertEqual(node_attr, answer)


class TestProjectUsage(TestCase):
    def test_valid_project_usage(self):
        test_project_data = {"project_name": "P1", "su_hours": {"GPU1": 16, "GPU2": 32}}
        data_model = ProjectUsage.model_validate(test_project_data)
        properties_to_check = [
            (data_model.project_name, "P1"),
            (data_model.su_hours, {"GPU1": 16, "GPU2": 32}),
        ]

        for node_attr, answer in properties_to_check:
            self.assertEqual(node_attr, answer)

    def test_invalid_project_usage(self):
        test_project_data = {
            "project_name": 1,  # Field must be str
            "su_hours": {"GPU1": 16, "GPU2": 32},
        }

        with self.assertRaises(pydantic.ValidationError):
            ProjectUsage.model_validate(test_project_data)

        test_project_data = {
            "project_name": "PI1",
            "su_hours": {
                "GPU1": -1,  # SU hour must be more than -1
                "GPU2": 32,
            },
        }

        with self.assertRaises(pydantic.ValidationError):
            ProjectUsage.model_validate(test_project_data)

    def test_invalid_reassignemnt(self):
        """Assignments to properties of ProjectUsage should also be validated"""
        test_project_data = {
            "project_name": "P1",
            "su_hours": {"GPU1": 16, "GPU2": 32},
        }
        data_model = ProjectUsage.model_validate(test_project_data)
        with self.assertRaises(pydantic.ValidationError):
            data_model.su_type = 1
