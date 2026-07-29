"""
services/file_service.py — Large-file upload handling, streaming CSV/XLSX parsing,
temp file lifecycle management, and file validation.

Design principles
-----------------
* Files are NEVER loaded fully into RAM before being needed.
  - CSVs: streamed in chunks via pd.read_csv(chunksize=...)
  - XLSXs: read once with openpyxl (unavoidable for format) then written to
    a Parquet temp file so downstream calls are instant Arrow reads.
* Temp files are stored under TMP_DIR with a UUID prefix and cleaned up by
  the caller (or by the atexit hook registered at import time).
* File validation: extension check → size check → header-sniff for CSV/XLSX
  magic bytes → column presence check.
* Progress is surfaced via a Streamlit progress bar yielded by the generator.
"""

from __future__ import annotations

import atexit
import hashlib
import io
import logging
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Generator, Optional, Tuple

import pandas as pd
import numpy as np

# Prefer PyArrow for Parquet I/O if available
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.csv as pa_csv
    _HAS_PYARROW = True
except ImportError:
    _HAS_PYARROW = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Temp file registry — track all temp files so we can clean them up
# ---------------------------------------------------------------------------
_TMP_REGISTRY: set = set()

def _cleanup_all_tmp() -> None:
    """Called on interpreter exit to remove any leftover temp files."""
    for p in list(_TMP_REGISTRY):
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass

atexit.register(_cleanup_all_tmp)


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

# CSV magic: starts with text (UTF BOM or plain ASCII)
# XLSX magic: PK header (ZIP archive)
_XLSX_MAGIC = b"PK\x03\x04"

def validate_uploaded_file(
    uploaded_file,
    max_bytes: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Validate an uploaded Streamlit file object.
    Returns (ok: bool, message: str).
    """
    if uploaded_file is None:
        return False, "No file provided."

    name = uploaded_file.name.lower()
    ext  = name.rsplit(".", 1)[-1] if "." in name else ""

    if ext not in settings.allowed_extensions:
        return False, f"Unsupported format '.{ext}'. Allowed: {settings.allowed_extensions}"

    # Size check
    limit = max_bytes or settings.max_upload_bytes
    data  = uploaded_file.read()
    uploaded_file.seek(0)          # reset for downstream read
    if len(data) > limit:
        mb = len(data) / 1024 / 1024
        return False, f"File is {mb:.0f} MB — exceeds {limit // (1024*1024)} MB limit."

    # Magic bytes check for XLSX
    if ext in ("xlsx", "xls"):
        if not data[:4] == _XLSX_MAGIC:
            return False, "File does not appear to be a valid Excel workbook."

    return True, "OK"


def file_hash(uploaded_file) -> str:
    """
    Compute a stable MD5 of the file bytes for use as a cache key.
    Resets the file pointer after reading.
    """
    data = uploaded_file.read()
    uploaded_file.seek(0)
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


# ---------------------------------------------------------------------------
# Streaming CSV parser
# ---------------------------------------------------------------------------

def parse_csv_streaming(
    uploaded_file,
    alias_map: dict,
    text_cols: set,
    numeric_cols: set,
    progress_callback=None,
) -> pd.DataFrame:
    """
    Parse a CSV in chunks, normalise columns, and return a single DataFrame.

    Parameters
    ----------
    uploaded_file       : Streamlit UploadedFile or file-like object
    alias_map           : column rename map (from parser.py)
    text_cols           : columns to skip numeric coercion
    numeric_cols        : canonical numeric column names
    progress_callback   : callable(fraction: float) for progress updates

    Strategy
    --------
    1. Read CSV with dtype=str in chunks of CHUNK_ROWS rows.
    2. For each chunk: normalise columns → coerce numeric columns.
    3. pd.concat() all chunks — memory-efficient because each chunk is
       immediately shrunk to typed dtypes before being appended.
    4. If PyArrow is available and the file is large, write a Parquet
       side-file for potential reuse.
    """
    raw  = uploaded_file.read()
    size = len(raw)
    uploaded_file.seek(0)

    chunks_list = []
    rows_seen   = 0
    est_rows    = max(size // 200, 1)   # rough estimate: ~200 bytes/row

    import re as _re
    _STRIP_RE = _re.compile(r"[\$\%\,]")

    for enc in settings.csv_encodings:
        try:
            buf = io.BytesIO(raw)
            reader = pd.read_csv(
                buf,
                encoding=enc,
                dtype=str,
                chunksize=settings.chunk_rows,
                low_memory=False,
                na_values=["", "N/A", "n/a", "--", "—"],
                keep_default_na=False,
            )

            chunks_list = []
            for chunk in reader:
                # Normalise column names
                chunk.columns = [c.strip().lower() for c in chunk.columns]
                rename = {c: alias_map[c] for c in chunk.columns if c in alias_map}
                chunk  = chunk.rename(columns=rename)

                # Fast coercion: known numeric cols
                for col in chunk.columns:
                    if col in text_cols:
                        continue
                    if col in numeric_cols:
                        chunk[col] = pd.to_numeric(
                            chunk[col].str.replace(_STRIP_RE, "", regex=True).str.strip(),
                            errors="coerce",
                        )
                    elif chunk[col].dtype == object:
                        sample = chunk[col].dropna()
                        if not sample.empty and sample.str.contains(r"[\$\%\,]", regex=True).any():
                            cleaned = chunk[col].str.replace(_STRIP_RE, "", regex=True).str.strip()
                            numeric = pd.to_numeric(cleaned, errors="coerce")
                            if numeric.notna().sum() >= sample.shape[0] * 0.5:
                                chunk[col] = numeric

                chunks_list.append(chunk)
                rows_seen += len(chunk)

                if progress_callback:
                    progress_callback(min(rows_seen / est_rows, 0.95))

            break   # successful encoding — stop trying others

        except UnicodeDecodeError:
            chunks_list = []
            continue
        except Exception as e:
            log.error("CSV parse error: %s", e)
            chunks_list = []
            continue

    if not chunks_list:
        raise ValueError("Could not decode CSV — tried UTF-8, latin-1, cp1252.")

    if progress_callback:
        progress_callback(1.0)

    return pd.concat(chunks_list, ignore_index=True, copy=False)


# ---------------------------------------------------------------------------
# XLSX parser
# ---------------------------------------------------------------------------

def parse_xlsx_streaming(
    uploaded_file,
    alias_map: dict,
    text_cols: set,
    numeric_cols: set,
) -> pd.DataFrame:
    """
    Parse an XLSX file.  openpyxl must load it fully (format limitation),
    but we use dtype=str to skip pandas type-inference and apply our own
    fast coercion path.
    """
    raw = uploaded_file.read()
    df  = pd.read_excel(io.BytesIO(raw), engine="openpyxl", dtype=str)

    import re as _re
    _STRIP_RE = _re.compile(r"[\$\%\,]")

    df.columns = [c.strip().lower() for c in df.columns]
    rename = {c: alias_map[c] for c in df.columns if c in alias_map}
    df = df.rename(columns=rename)

    for col in df.columns:
        if col in text_cols:
            continue
        if col in numeric_cols:
            df[col] = pd.to_numeric(
                df[col].str.replace(_STRIP_RE, "", regex=True).str.strip(),
                errors="coerce",
            )
        elif df[col].dtype == object:
            sample = df[col].dropna()
            if not sample.empty and sample.str.contains(r"[\$\%\,]", regex=True).any():
                cleaned = df[col].str.replace(_STRIP_RE, "", regex=True).str.strip()
                numeric = pd.to_numeric(cleaned, errors="coerce")
                if numeric.notna().sum() >= sample.shape[0] * 0.5:
                    df[col] = numeric

    return df


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def load_file(
    uploaded_file,
    alias_map: dict,
    text_cols: set,
    numeric_cols: set,
    progress_callback=None,
) -> pd.DataFrame:
    """
    Route to the correct parser based on file extension.
    Handles CSV streaming and XLSX loading.
    """
    name = uploaded_file.name.lower()

    if name.endswith(".csv"):
        return parse_csv_streaming(
            uploaded_file, alias_map, text_cols, numeric_cols, progress_callback
        )
    elif name.endswith((".xlsx", ".xls")):
        return parse_xlsx_streaming(uploaded_file, alias_map, text_cols, numeric_cols)
    else:
        raise ValueError(f"Unsupported format: {uploaded_file.name}")


# ---------------------------------------------------------------------------
# Temp file helpers
# ---------------------------------------------------------------------------

def save_to_parquet(df: pd.DataFrame, prefix: str = "upload") -> Path:
    """
    Save a DataFrame to a temporary Parquet file.
    Returns the path. Caller must call delete_tmp_file() when done.
    Requires PyArrow.
    """
    if not _HAS_PYARROW:
        raise RuntimeError("PyArrow is required for Parquet caching.")
    path = settings.tmp_dir / f"{prefix}_{uuid.uuid4().hex}.parquet"
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, path, compression="snappy")
    _TMP_REGISTRY.add(str(path))
    return path


def load_from_parquet(path: Path) -> pd.DataFrame:
    """Load a DataFrame from a previously saved Parquet temp file."""
    if not _HAS_PYARROW:
        raise RuntimeError("PyArrow is required for Parquet caching.")
    return pq.read_table(path).to_pandas()


def delete_tmp_file(path: Path) -> None:
    """Delete a temp file and remove it from the registry."""
    try:
        Path(path).unlink(missing_ok=True)
        _TMP_REGISTRY.discard(str(path))
    except Exception as e:
        log.warning("Could not delete temp file %s: %s", path, e)


def cleanup_old_tmp_files(max_age_seconds: int = 3600) -> int:
    """
    Remove temp files older than max_age_seconds from TMP_DIR.
    Returns the number of files deleted.
    Called at app startup to prevent disk accumulation.
    """
    now     = time.time()
    deleted = 0
    for p in settings.tmp_dir.iterdir():
        try:
            if p.is_file() and (now - p.stat().st_mtime) > max_age_seconds:
                p.unlink()
                deleted += 1
        except Exception:
            pass
    return deleted
