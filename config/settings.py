"""
config/settings.py — Centralised application configuration.

All tunable parameters, environment variables, and constants live here.
Import from this module everywhere else; never hardcode values in app.py.

Usage:
    from config.settings import settings, APP_VERSION

Environment variables (set in .env or platform secrets):
    MAX_UPLOAD_MB          Maximum upload size in MB  (default: 3072 = 3 GB)
    TMP_DIR                Temp file directory        (default: /tmp/mediaplan)
    CHUNK_ROWS             CSV chunk size in rows     (default: 300_000)
    LOG_LEVEL              Logging verbosity          (default: INFO)
    ENABLE_AUTH            Enable password gate       (default: false)
    APP_PASSWORD           Password if auth enabled   (default: "")
    DUCKDB_THREADS         DuckDB parallelism         (default: 4)
    DUCKDB_MEMORY_LIMIT    DuckDB memory cap          (default: 4GB)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Try to load .env (ignored gracefully if python-dotenv not installed)
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR   = Path(__file__).parent.parent.resolve()
TMP_DIR    = Path(os.getenv("TMP_DIR", "/tmp/mediaplan"))
TMP_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# App identity
# ---------------------------------------------------------------------------
APP_NAME    = "Amazon Media Plan Forecast Engine"
APP_VERSION = "2.0.0"
APP_AUTHOR  = "Sumeet Mangotra"
APP_ROLE    = "Brand Ecommerce Manager"
APP_ICON    = "📊"

# ---------------------------------------------------------------------------
# Colours (single source of truth — also used in components)
# ---------------------------------------------------------------------------
C_PRIMARY = "#4f46e5"
C_ACCENT  = "#f97316"
C_DARK    = "#1e1b4b"
C_BG      = "#f0f2ff"
C_WHITE   = "#ffffff"
C_MUTED   = "#6b7280"
C_GREEN   = "#10b981"
C_RED     = "#ef4444"

# ---------------------------------------------------------------------------
# Upload / file limits
# ---------------------------------------------------------------------------
MAX_UPLOAD_MB: int     = int(os.getenv("MAX_UPLOAD_MB", 3072))      # 3 GB
MAX_UPLOAD_BYTES: int  = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_EXTENSIONS     = {"csv", "xlsx", "xls"}
CHUNK_ROWS: int        = int(os.getenv("CHUNK_ROWS", 300_000))
CSV_ENCODINGS          = ("utf-8", "latin-1", "cp1252")

# ---------------------------------------------------------------------------
# DuckDB settings (used by processing_service)
# ---------------------------------------------------------------------------
DUCKDB_THREADS: int        = int(os.getenv("DUCKDB_THREADS", 4))
DUCKDB_MEMORY_LIMIT: str   = os.getenv("DUCKDB_MEMORY_LIMIT", "4GB")

# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------
LARGE_FILE_THRESHOLD_ROWS: int = 500_000    # show "large file" banner above this
LARGE_FILE_THRESHOLD_MB:   int = 100        # try DuckDB path above this size (MB)

# ---------------------------------------------------------------------------
# Auth (simple password gate — set ENABLE_AUTH=true + APP_PASSWORD in env)
# ---------------------------------------------------------------------------
ENABLE_AUTH: bool      = os.getenv("ENABLE_AUTH", "false").lower() == "true"
APP_PASSWORD: str      = os.getenv("APP_PASSWORD", "")

# ---------------------------------------------------------------------------
# Forecast defaults (never change these — they define business logic)
# ---------------------------------------------------------------------------
DEFAULT_CHANNEL_SPLIT = {
    "Sponsored Products": 0.65,
    "Sponsored Brands":   0.25,
    "Sponsored Display":  0.10,
}
ACOS_EFFICIENCY_DECAY = 0.04    # +4% relative ACOS per 10% spend increase

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# ---------------------------------------------------------------------------
# Convenience accessor (typed namespace)
# ---------------------------------------------------------------------------
class _Settings:
    """Typed namespace for IDE autocompletion."""
    app_name            = APP_NAME
    app_version         = APP_VERSION
    app_author          = APP_AUTHOR
    app_role            = APP_ROLE
    app_icon            = APP_ICON
    root_dir            = ROOT_DIR
    tmp_dir             = TMP_DIR
    max_upload_mb       = MAX_UPLOAD_MB
    max_upload_bytes    = MAX_UPLOAD_BYTES
    allowed_extensions  = ALLOWED_EXTENSIONS
    chunk_rows          = CHUNK_ROWS
    csv_encodings       = CSV_ENCODINGS
    duckdb_threads      = DUCKDB_THREADS
    duckdb_memory_limit = DUCKDB_MEMORY_LIMIT
    large_file_rows     = LARGE_FILE_THRESHOLD_ROWS
    large_file_mb       = LARGE_FILE_THRESHOLD_MB
    enable_auth         = ENABLE_AUTH
    app_password        = APP_PASSWORD
    default_channel_split = DEFAULT_CHANNEL_SPLIT
    acos_efficiency_decay = ACOS_EFFICIENCY_DECAY
    log_level           = LOG_LEVEL
    c_primary = C_PRIMARY
    c_accent  = C_ACCENT
    c_dark    = C_DARK
    c_bg      = C_BG
    c_white   = C_WHITE
    c_muted   = C_MUTED
    c_green   = C_GREEN
    c_red     = C_RED


settings = _Settings()
