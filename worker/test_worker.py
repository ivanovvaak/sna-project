import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from uptime_worker import check_url, get_config
import requests

class TestCheckUrl(unittest.TestCase):

    @patch("uptime_worker.requests.get")
    def test_successful_request(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = check_url("https://example.com", timeout=5)

        self.assertTrue(result["is_success"])
        self.assertEqual(result["status_code"], 200)
        self.assertIsNone(result["error_message"])
        self.assertIsNotNone(result["response_time_ms"])
        self.assertGreaterEqual(result["response_time_ms"], 0)
        self.assertEqual(result["url"], "https://example.com")

    @patch("uptime_worker.requests.get")
    def test_server_error_404(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = check_url("https://example.com/notfound", timeout=5)

        self.assertFalse(result["is_success"])
        self.assertEqual(result["status_code"], 404)

    @patch("uptime_worker.requests.get")
    def test_server_error_500(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = check_url("https://example.com", timeout=5)

        self.assertFalse(result["is_success"])
        self.assertEqual(result["status_code"], 500)

    @patch("uptime_worker.requests.get", side_effect=requests.exceptions.Timeout)
    def test_timeout(self, mock_get):
        result = check_url("https://slow-site.com", timeout=1)

        self.assertFalse(result["is_success"])
        self.assertIsNone(result["status_code"])
        self.assertIsNotNone(result["error_message"])
        self.assertIn("timed out", result["error_message"])

    @patch(
        "uptime_worker.requests.get",
        side_effect=requests.exceptions.ConnectionError("Connection refused"),
    )
    def test_connection_error(self, mock_get):
        result = check_url("http://localhost:9999", timeout=5)

        self.assertFalse(result["is_success"])
        self.assertIsNone(result["response_time_ms"])
        self.assertIsNotNone(result["error_message"])

    @patch("uptime_worker.requests.get")
    def test_result_has_timestamp(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = check_url("https://example.com", timeout=5)

        self.assertIn("timestamp", result)
        self.assertIsInstance(result["timestamp"], datetime)

class TestGetConfig(unittest.TestCase):

    @patch.dict(os.environ, {
        "URLS": "https://a.com,https://b.com",
        "CHECK_INTERVAL_SECONDS": "30",
        "REQUEST_TIMEOUT": "10",
        "DB_HOST": "myhost",
        "DB_PORT": "5433",
        "DB_NAME": "mydb",
        "DB_USER": "myuser",
        "DB_PASSWORD": "mypass",
    })
    def test_config_from_env(self):
        config = get_config()

        self.assertEqual(config["urls"], ["https://a.com", "https://b.com"])
        self.assertEqual(config["check_interval"], 30)
        self.assertEqual(config["request_timeout"], 10)
        self.assertEqual(config["db_host"], "myhost")
        self.assertEqual(config["db_port"], 5433)
        self.assertEqual(config["db_name"], "mydb")

    @patch.dict(os.environ, {}, clear=True)
    def test_config_defaults(self):
        config = get_config()

        # Дефолтные URL
        self.assertIn("https://google.com", config["urls"])
        self.assertEqual(config["check_interval"], 60)
        self.assertEqual(config["request_timeout"], 5)

    @patch.dict(os.environ, {"URLS": "  https://a.com , https://b.com  "})
    def test_url_whitespace_trimmed(self):
        config = get_config()
        self.assertEqual(config["urls"], ["https://a.com", "https://b.com"])

class TestDbUtils(unittest.TestCase):

    def _make_mock_conn(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_save_check_calls_execute(self):
        from db_utils import save_check

        mock_conn, mock_cursor = self._make_mock_conn()
        result = {
            "url": "https://example.com",
            "timestamp": datetime.now(timezone.utc),
            "response_time_ms": 123,
            "status_code": 200,
            "is_success": True,
            "error_message": None,
        }

        save_check(mock_conn, result)

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_init_db_calls_execute_and_commit(self):
        from db_utils import init_db

        mock_conn, mock_cursor = self._make_mock_conn()
        init_db(mock_conn)

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
