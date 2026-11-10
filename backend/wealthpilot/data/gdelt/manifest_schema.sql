-- gdelt_manifest_v1.1. B2-I's gdelt_manifest_v1 plus the B2-K additions documented in the B2-K report:
--   * existence 'available'   : the server confirmed the file (header 200) but it is not downloaded yet
--   * availability_* columns  : the fail-closed availability rule (verified / unverified + reason + flags)
--   * validation 'availability_unverified', 'body_incomplete'
--   * parse_status            : 'parsed_validated' separates "parsed and validated" from "committed"
--   * selection, sample_round, sample_block : which pre-registered list a slot came from
--   * list_status 'not_consulted' : sample runs verify by header checks, not the master list
--   * schema_meta             : schema version
-- Applied with journal_mode=WAL and foreign_keys=ON.

CREATE TABLE schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE run (
    run_id                       TEXT PRIMARY KEY,
    started_at_utc               TEXT NOT NULL,
    ended_at_utc                 TEXT,
    mode                         TEXT NOT NULL CHECK (mode IN ('dry_run', 'dev_sample', 'confirmation_sample', 'full_acquisition')),
    outcome                      TEXT NOT NULL DEFAULT 'running' CHECK (outcome IN (
                                     'running', 'completed', 'stopped_by_user', 'stopped_byte_budget',
                                     'stopped_request_budget', 'stopped_disk_space', 'stopped_error', 'interrupted')),
    window_first_ts              TEXT,
    window_last_ts               TEXT,
    code_git_commit              TEXT,
    code_dirty                   INTEGER CHECK (code_dirty IN (0, 1)),
    code_sha256                  TEXT NOT NULL,
    parser_version               TEXT NOT NULL,
    filter_version               TEXT NOT NULL,
    filter_spec_sha256           TEXT NOT NULL,
    audited_list_sha256          TEXT NOT NULL,
    selection_sha256             TEXT,
    masterlist_url               TEXT,
    masterlist_fetched_at_utc    TEXT,
    masterlist_bytes             INTEGER,
    masterlist_md5               TEXT,
    masterlist_sha256            TEXT,
    masterlist_last_modified_utc TEXT,
    masterlist_diff_json         TEXT,
    params_json                  TEXT NOT NULL,
    python_version               TEXT NOT NULL,
    tzdata_version               TEXT,
    free_bytes_at_start          INTEGER,
    bytes_downloaded             INTEGER NOT NULL DEFAULT 0,
    requests_made                INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE slot (
    batch_ts               TEXT PRIMARY KEY CHECK (length(batch_ts) = 14 AND batch_ts NOT GLOB '*[^0-9]*'),
    utc_day                TEXT NOT NULL,
    nominal_utc            TEXT NOT NULL,
    url                    TEXT NOT NULL,
    selection              TEXT NOT NULL DEFAULT 'window' CHECK (selection IN ('window', 'stage_D', 'stage_C')),
    sample_round           INTEGER,
    sample_block           INTEGER,
    list_status            TEXT NOT NULL CHECK (list_status IN ('listed', 'unlisted', 'not_consulted')),
    expected_bytes         INTEGER,
    expected_md5           TEXT,
    md5_source             TEXT CHECK (md5_source IN ('master_list', 'etag')),
    existence              TEXT NOT NULL DEFAULT 'unverified' CHECK (existence IN (
                               'unverified', 'available', 'present_verified', 'present_invalid',
                               'absent_confirmed', 'absent_inconclusive', 'absent_accepted',
                               'request_failed', 'inaccessible')),
    existence_evidence     TEXT,
    fetch_status           TEXT NOT NULL DEFAULT 'pending' CHECK (fetch_status IN (
                               'pending', 'in_progress', 'fetched', 'retry_wait', 'failed_permanent', 'not_applicable')),
    attempts               INTEGER NOT NULL DEFAULT 0,
    next_attempt_after_utc TEXT,
    http_status_last       INTEGER,
    http_etag              TEXT,
    http_last_modified_utc TEXT,
    actual_bytes           INTEGER,
    actual_md5             TEXT,
    actual_sha256          TEXT,
    checksum_basis         TEXT CHECK (checksum_basis IN ('md5_master_list', 'md5_etag', 'crc_and_size_only')),
    zip_member_name        TEXT,
    zip_member_bytes       INTEGER,
    zip_crc32              TEXT,
    validation_status      TEXT NOT NULL DEFAULT 'pending' CHECK (validation_status IN (
                               'pending', 'passed', 'size_mismatch', 'md5_mismatch', 'zip_invalid', 'crc_failed',
                               'member_unexpected', 'size_guard_exceeded', 'body_incomplete',
                               'availability_unverified', 'not_applicable')),
    availability_status    TEXT NOT NULL DEFAULT 'pending' CHECK (availability_status IN (
                               'pending', 'verified', 'unverified', 'not_applicable')),
    availability_reason    TEXT,
    availability_flags     TEXT,
    available_at_utc       TEXT,
    late_flag              INTEGER CHECK (late_flag IN (0, 1)),
    rows_physical          INTEGER,
    rows_malformed         INTEGER,
    rows_date_mismatch     INTEGER,
    rows_translated        INTEGER,
    rows_non_web           INTEGER,
    rows_english_valid     INTEGER,
    rows_captured          INTEGER,
    rows_company_item      INTEGER,
    rows_dup_same_batch    INTEGER,
    rows_audit_sample      INTEGER,
    near_empty_flag        INTEGER CHECK (near_empty_flag IN (0, 1)),
    near_empty_baseline    REAL,
    backlog_flag           INTEGER CHECK (backlog_flag IN (0, 1)),
    shard_relpath          TEXT,
    shard_sha256           TEXT,
    parse_status           TEXT NOT NULL DEFAULT 'pending' CHECK (parse_status IN ('pending', 'parsed_validated', 'not_applicable')),
    parser_version         TEXT,
    filter_version         TEXT,
    processed_at_utc       TEXT,
    run_id                 TEXT REFERENCES run (run_id),
    commit_status          TEXT NOT NULL DEFAULT 'pending' CHECK (commit_status IN ('pending', 'committed', 'not_applicable')),
    cleanup_status         TEXT NOT NULL DEFAULT 'nothing_written' CHECK (cleanup_status IN (
                               'nothing_written', 'temp_present', 'temp_deleted', 'delete_failed')),
    CHECK (existence <> 'present_verified'
           OR (validation_status = 'passed' AND fetch_status = 'fetched' AND availability_status = 'verified')),
    CHECK (existence <> 'present_invalid'
           OR (fetch_status = 'failed_permanent' AND validation_status NOT IN ('pending', 'passed', 'not_applicable'))),
    CHECK (existence NOT IN ('absent_confirmed', 'absent_inconclusive', 'absent_accepted', 'inaccessible', 'request_failed')
           OR (fetch_status IN ('not_applicable', 'failed_permanent') AND commit_status = 'not_applicable'
               AND parse_status = 'not_applicable')),
    CHECK (availability_status <> 'verified' OR available_at_utc IS NOT NULL),
    CHECK (availability_status <> 'unverified' OR (available_at_utc IS NULL AND availability_reason IS NOT NULL)),
    CHECK (parse_status <> 'parsed_validated'
           OR (existence = 'present_verified' AND rows_english_valid IS NOT NULL AND shard_sha256 IS NOT NULL)),
    CHECK (commit_status <> 'committed'
           OR (parse_status = 'parsed_validated' AND cleanup_status IN ('nothing_written', 'temp_deleted'))),
    CHECK (md5_source IS NULL OR expected_md5 IS NOT NULL)
);
CREATE INDEX slot_by_day ON slot (utc_day);
CREATE INDEX slot_open ON slot (fetch_status, existence) WHERE commit_status = 'pending';

CREATE TABLE attempt (
    attempt_id        INTEGER PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES run (run_id),
    batch_ts          TEXT REFERENCES slot (batch_ts),
    kind              TEXT NOT NULL CHECK (kind IN ('head', 'get', 'masterlist_get')),
    attempt_no        INTEGER NOT NULL CHECK (attempt_no >= 1),
    url               TEXT NOT NULL,
    started_at_utc    TEXT NOT NULL,
    elapsed_ms        INTEGER,
    outcome           TEXT NOT NULL CHECK (outcome IN (
                          'response', 'timeout', 'connection_error', 'tls_error', 'redirect_rejected',
                          'body_incomplete', 'aborted_by_budget', 'aborted_by_user')),
    http_status       INTEGER,
    location          TEXT,
    content_length    INTEGER,
    etag              TEXT,
    last_modified_utc TEXT,
    server_date_utc   TEXT,
    age_seconds       INTEGER,
    cache_control     TEXT,
    bytes_received    INTEGER NOT NULL DEFAULT 0,
    error_class       TEXT,
    backoff_before_s  REAL,
    CHECK (outcome <> 'response' OR http_status IS NOT NULL)
);
CREATE INDEX attempt_by_slot ON attempt (batch_ts, kind, attempt_no);
CREATE INDEX attempt_by_time ON attempt (started_at_utc);

CREATE TABLE slot_series_count (
    batch_ts         TEXT NOT NULL REFERENCES slot (batch_ts),
    filter_version   TEXT NOT NULL,
    series           TEXT NOT NULL CHECK (series IN ('EQUITY_US', 'RATES_US', 'GOLD')),
    rows             INTEGER NOT NULL CHECK (rows >= 0),
    rows_us_relevant INTEGER NOT NULL CHECK (rows_us_relevant >= 0),
    new_stories      INTEGER CHECK (new_stories >= 0),
    PRIMARY KEY (batch_ts, filter_version, series)
) WITHOUT ROWID;

CREATE TABLE day_commit (
    utc_day          TEXT NOT NULL,
    filter_version   TEXT NOT NULL,
    parser_version   TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('committed', 'superseded')),
    slots_expected   INTEGER NOT NULL,
    slots_present    INTEGER NOT NULL,
    slots_absent     INTEGER NOT NULL,
    slots_failed     INTEGER NOT NULL,
    rows_kept        INTEGER NOT NULL,
    file_relpath     TEXT NOT NULL,
    file_bytes       INTEGER NOT NULL,
    file_sha256      TEXT NOT NULL,
    audit_relpath    TEXT,
    audit_sha256     TEXT,
    committed_at_utc TEXT NOT NULL,
    run_id           TEXT NOT NULL REFERENCES run (run_id),
    PRIMARY KEY (utc_day, filter_version, parser_version),
    CHECK (slots_present + slots_absent + slots_failed = slots_expected)
);
