from destination_glide.glide import GlideBigTableRestStrategy, Column
import requests  # for mocking it
import unittest
from unittest import skip
from unittest.mock import patch
import uuid
from requests.exceptions import HTTPError
import json

class TestGlideBigTableRestStrategy(unittest.TestCase):
    api_host = "https://test-api-host.com"
    api_key = "test-api-key"
    api_path_root = "test/api/path/root"
    table_id = ""
    table_name = ""
    batch_size = 100

    test_columns = [
        Column("test-str", "string"),
        Column("test-num", "number")
    ]

    def setUp(self):
        self.table_id = f"test-table-id-{str(uuid.uuid4())}"
        self.table_name = f"test-table-name-{str(uuid.uuid4())}"
        self.gbt = GlideBigTableRestStrategy()
        self.gbt.init(self.api_key, self.table_name, self.test_columns, self.api_host, self.api_path_root, self.batch_size)

    def test_invalid_col_type(self):
        with self.assertRaises(ValueError):
            Column("test-num", "invalid-type")

    @patch.object(requests, "post")
    def test_add_rows(self, mock_post):
        test_rows = [
            {"test-str": "one", "test-num": 1},
            {"test-str": "two", "test-num": 2}
        ]
        self.gbt.add_rows(test_rows)
        mock_post.assert_not_called()

    @patch.object(requests, "post")
    def test_add_rows_batching(self, mock_post):
        # the batch size isn't currently strict, so the extra row will be sent in the same batch
        TEST_ROW_COUNT = self.batch_size + 1
        test_rows = list([
            {"test-str": f"one {i}", "test-num": i}
            for i in range(TEST_ROW_COUNT)
        ])

        self.gbt.add_rows(test_rows)

        self.assertEqual(1, mock_post.call_count)
        self.assertEqual(mock_post.call_args.kwargs["json"], test_rows)

    @patch.object(requests, "post")
    def test_add_rows_413(self, mock_post):
        self.gbt.batch_size = 1
        mock_post.return_value.status_code = 413
        mock_post.return_value.text = "Payload Too Large"
        mock_post.return_value.raise_for_status.side_effect = HTTPError("413 Client Error: Payload Too Large")

        with self.assertRaises(Exception) as context:
            self.gbt.add_rows([
                {"test-str": "one", "test-num": 1},
                {"test-str": "two", "test-num": 2},
                {"test-str": "three", "test-num": 3},
                {"test-str": "four", "test-num": 4}])

        self.assertIn("Failed to post rows batch", str(context.exception))

    @patch.object(requests, "post")
    def test_split_batches_on_413(self, mock_post):
        threshold_bytes = 200
        did_fail = False

        def side_effect(*args, **kwargs):
            payload = kwargs.get("json", [])
            payload_size = len(json.dumps(payload).encode("utf-8"))
            mock_response = requests.Response()
            if payload_size > threshold_bytes:
                mock_response.status_code = 413
                mock_response._content = b"Payload Too Large"
                nonlocal did_fail
                did_fail = True
            else:
                mock_response.status_code = 200
                mock_response._content = b"OK"
            return mock_response

        mock_post.side_effect = side_effect

        # Force small flushes to test smaller batches
        self.gbt.batch_size = 2

        # Attempt to add rows that will exceed threshold if posted all at once
        large_number_of_rows = [
            {"test-str": "foo " * 30, "test-num": i}  # repeated strings for size
            for i in range(10)
        ]
        self.gbt.add_rows(large_number_of_rows)

        self.assertTrue(did_fail)

    def test_commit_with_pre_existing_table(self):
        with patch.object(requests, "post") as mock_post:
            TEST_ROW_COUNT = self.batch_size
            test_rows = list([
                {"test-str": f"one {i}", "test-num": i}
                for i in range(TEST_ROW_COUNT)
            ])
            self.gbt.add_rows(test_rows)

            with patch.object(requests, "get") as mock_get:
                # mock the `GET /tables` response to include the table:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    "data": [
                        {
                            "name": self.table_name,
                            "id": self.table_id
                        }
                    ]
                }
                mock_post.reset_mock()
                with patch.object(requests, "put") as mock_put:
                    self.gbt.commit()
                    # it should have called put to overwrite a table and NOT called post
                    mock_put.assert_called_once()
                    # it should have NOT created a new table via post:
                    mock_post.assert_not_called()

    def test_commit_with_non_existing_table(self):
        # TODO: in a future version, we want to search for the table and if not found, create it. if found, update it (put).
        with patch.object(requests, "post") as mock_post:
            test_rows = [
                {"test-str": "one", "test-num": 1},
                {"test-str": "two", "test-num": 2}
            ]
            self.gbt.add_rows(test_rows)

            with patch.object(requests, "get") as mock_get:
                # mock the `GET /tables` response to include the table:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    "data": []
                }
                mock_post.reset_mock()
                with patch.object(requests, "put") as mock_put:
                    self.gbt.commit()
                    # it should not have tried to overwrite a table with put
                    mock_put.assert_not_called()
                    # it should have created a new table with post:
                    mock_put.assert_not_called()



if __name__ == '__main__':
    unittest.main()
