import os
import time
import logging
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from db_utils import get_db_connection, save_check, init_db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_config() -> dict:
    urls_raw = os.getenv("URLS", "https://google.com,https://github.com")
    urls = [u.strip() for u in urls_raw.split(",") if u.strip()]

    return {
        "urls": urls,
        "check_interval": int(os.getenv("CHECK_INTERVAL_SECONDS", "60")),
        "request_timeout": int(os.getenv("REQUEST_TIMEOUT", "5")),
        "db_host":     os.getenv("DB_HOST", "localhost"),
        "db_port":     int(os.getenv("DB_PORT", "5432")),
        "db_name":     os.getenv("DB_NAME", "uptime_db"),
        "db_user":     os.getenv("DB_USER", "uptime_user"),
        "db_password": os.getenv("DB_PASSWORD", "secure_password"),
    }


def check_url(url: str, timeout: int) -> dict:
    result = {
        "url": url,
        "timestamp": datetime.now(timezone.utc),
        "response_time_ms": None,
        "status_code": None,
        "is_success": False,
        "error_message": None,
    }

    try:
        start = time.monotonic()
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        result["response_time_ms"] = elapsed_ms
        result["status_code"] = response.status_code
        result["is_success"] = response.status_code < 400

        logger.info("OK %s %d %d ms", url, response.status_code, elapsed_ms)

    except requests.exceptions.Timeout:
        result["error_message"] = "Request timed out"
        logger.warning("TIMEOUT %s", url)

    except requests.exceptions.ConnectionError as e:
        result["error_message"] = f"Connection error: {e}"
        logger.warning("CONNECTION ERROR %s %s", url, e)

    except requests.exceptions.RequestException as e:
        result["error_message"] = f"Request error: {e}"
        logger.warning("REQUEST ERROR %s %s", url, e)

    return result


def run_checks(urls: list[str], timeout: int, conn) -> None:
    for url in urls:
        result = check_url(url, timeout)
        try:
            save_check(conn, result)
        except Exception as e:
            logger.error("Failed to save record for %s: %s", url, e)
            conn.rollback()


def main():
    config = get_config()
    logger.info("Uptime Worker started")
    logger.info("URLs: %s", config["urls"])
    logger.info("Interval: %d sec | Timeout: %d sec",
                config["check_interval"], config["request_timeout"])

    db_params = {
        "host":     config["db_host"],
        "port":     config["db_port"],
        "dbname":   config["db_name"],
        "user":     config["db_user"],
        "password": config["db_password"],
    }

    conn = None

    while True:
        if conn is None or conn.closed:
            logger.info("Connecting to PostgreSQL (%s:%s/%s)...",
                        config["db_host"], config["db_port"], config["db_name"])
            conn = get_db_connection(db_params)
            if conn is None:
                logger.error("Could not connect to database. Retrying in %d sec...",
                             config["check_interval"])
                time.sleep(config["check_interval"])
                continue
            init_db(conn)

        try:
            run_checks(config["urls"], config["request_timeout"], conn)
        except Exception as e:
            logger.error("Error in check loop: %s", e)
            conn = None

        logger.info("Sleeping for %d sec...", config["check_interval"])
        time.sleep(config["check_interval"])


if __name__ == "__main__":
    main()
