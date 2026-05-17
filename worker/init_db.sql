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
