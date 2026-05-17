import logging
import time

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


def get_db_connection(db_params: dict, retries: int = 5, delay: int = 5):
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(**db_params)
            conn.autocommit = False
            logger.info("Connected to PostgreSQL (attempt %d)", attempt)
            return conn
        except psycopg2.OperationalError as e:
            logger.warning("Attempt %d/%d: connection failed: %s", attempt, retries, e)
            if attempt < retries:
                time.sleep(delay)

    logger.error("All connection attempts exhausted.")
    return None


DDL = """
CREATE TABLE IF NOT EXISTS checks (
    id                SERIAL       PRIMARY KEY,
    url               TEXT         NOT NULL,
    timestamp         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    response_time_ms  INTEGER,
    status_code       INTEGER,
    is_success        BOOLEAN      NOT NULL DEFAULT FALSE,
    error_message     TEXT
);

CREATE INDEX IF NOT EXISTS idx_checks_url       ON checks (url);
CREATE INDEX IF NOT EXISTS idx_checks_timestamp ON checks (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_checks_url_ts    ON checks (url, timestamp DESC);
"""


def init_db(conn) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
        logger.info("Database schema initialized.")
    except Exception as e:
        conn.rollback()
        logger.error("Failed to initialize database schema: %s", e)
        raise


INSERT_CHECK_SQL = """
INSERT INTO checks (url, timestamp, response_time_ms, status_code, is_success, error_message)
VALUES (%(url)s, %(timestamp)s, %(response_time_ms)s, %(status_code)s, %(is_success)s, %(error_message)s);
"""


def save_check(conn, result: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(INSERT_CHECK_SQL, result)
    conn.commit()


def get_avg_response_time(conn, hours: int = 24) -> list[dict]:
    sql = """
        SELECT
            url,
            ROUND(AVG(response_time_ms)) AS avg_ms,
            COUNT(*)                     AS total_checks
        FROM checks
        WHERE timestamp >= NOW() - INTERVAL '%(hours)s hours'
          AND response_time_ms IS NOT NULL
        GROUP BY url
        ORDER BY avg_ms DESC;
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, {"hours": hours})
        return cur.fetchall()


def get_uptime_percent(conn, hours: int = 24) -> list[dict]:
    sql = """
        SELECT
            url,
            ROUND(
                100.0 * SUM(CASE WHEN is_success THEN 1 ELSE 0 END) / COUNT(*),
                2
            )                                            AS uptime_pct,
            SUM(CASE WHEN is_success THEN 1 ELSE 0 END) AS success,
            COUNT(*)                                     AS total
        FROM checks
        WHERE timestamp >= NOW() - INTERVAL '%(hours)s hours'
        GROUP BY url
        ORDER BY uptime_pct ASC;
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, {"hours": hours})
        return cur.fetchall()


def get_last_checks(conn, limit: int = 10) -> list[dict]:
    sql = """
        SELECT
            id, url, timestamp, response_time_ms,
            status_code, is_success, error_message
        FROM checks
        ORDER BY timestamp DESC
        LIMIT %(limit)s;
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, {"limit": limit})
        return cur.fetchall()


def get_last_check_per_url(conn) -> list[dict]:
    sql = """
        SELECT DISTINCT ON (url)
            url, timestamp, response_time_ms,
            status_code, is_success, error_message
        FROM checks
        ORDER BY url, timestamp DESC;
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        return cur.fetchall()
