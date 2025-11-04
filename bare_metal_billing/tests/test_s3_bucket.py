from unittest import TestCase, mock

from bare_metal_billing import s3_bucket


class TestS3Bucket(TestCase):
    def test_fetch_s3(self):
        mock_bucket = mock.MagicMock()
        mock_get_bucket = mock.MagicMock(return_value=mock_bucket)

        with mock.patch("bare_metal_billing.s3_bucket.get_bucket", mock_get_bucket):
            test_s3_filepath = "path/to/testfile.json"
            expected_local_name = "testfile.json"

            local_name = s3_bucket.fetch_s3("foo-bucket", test_s3_filepath)

            self.assertEqual(local_name, expected_local_name)
            mock_get_bucket.assert_called_once()
            mock_bucket.download_file.assert_called_once_with(
                test_s3_filepath, expected_local_name
            )
