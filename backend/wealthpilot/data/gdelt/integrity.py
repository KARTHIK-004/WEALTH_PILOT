"""Body, checksum and zip-structure checks. The CRC-32 is verified by reading the member to its end
(``parser.iter_rows``), so no row from a batch is kept until the whole member has been read."""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass

from wealthpilot.data.gdelt.errors import IntegrityError

_MD5_RE = re.compile(r"^[0-9a-f]{32}$")


def md5_from_etag(etag: str | None) -> str | None:
    """The ETag is the file's MD5 when it is a plain 32-hex value (B2-G, B2-H); otherwise None."""
    if not etag:
        return None
    value = etag.strip()
    if value.startswith("W/"):
        return None  # weak validators are not checksums
    value = value.strip('"').lower()
    return value if _MD5_RE.match(value) else None


@dataclass(frozen=True)
class BodyCheck:
    size: int
    md5: str
    sha256: str
    checksum_basis: str   # "md5_master_list", "md5_etag" or "crc_and_size_only"


def check_body(body: bytes, *, content_length: int | None, expected_bytes: int | None,
               expected_md5: str | None, md5_source: str | None) -> BodyCheck:
    size = len(body)
    if content_length is not None and size < content_length:
        raise IntegrityError(f"truncated body: {size} of {content_length} B", status="body_incomplete")
    if content_length is not None and size != content_length:
        raise IntegrityError(f"body {size} B differs from Content-Length {content_length} B", status="size_mismatch")
    if expected_bytes is not None and size != expected_bytes:
        raise IntegrityError(f"body {size} B differs from expected {expected_bytes} B", status="size_mismatch")
    md5 = hashlib.md5(body).hexdigest()  # noqa: S324 - integrity check against GDELT's published MD5
    sha256 = hashlib.sha256(body).hexdigest()
    if expected_md5 is not None:
        if md5 != expected_md5.lower():
            raise IntegrityError(f"MD5 {md5} differs from expected {expected_md5}", status="md5_mismatch")
        basis = "md5_master_list" if md5_source == "master_list" else "md5_etag"
    else:
        basis = "crc_and_size_only"
    return BodyCheck(size, md5, sha256, basis)


def open_member(body: bytes, stamp: str, *, max_uncompressed: int, max_ratio: float) -> tuple[zipfile.ZipFile, zipfile.ZipInfo]:
    """Validate the archive's structure and return it with its single member. Extracts nothing."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(body))
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        raise IntegrityError(f"not a valid zip archive: {exc}", status="zip_invalid") from exc
    infos = archive.infolist()
    expected = f"{stamp}.gkg.csv"
    if len(infos) != 1:
        raise IntegrityError(f"expected exactly one member, found {len(infos)}", status="member_unexpected")
    info = infos[0]
    name = info.filename
    if name != expected or "/" in name or "\\" in name or ".." in name or name.startswith(("/", "\\")):
        raise IntegrityError(f"unexpected member name {name!r}; expected {expected!r}", status="member_unexpected")
    if info.flag_bits & 0x1:
        raise IntegrityError("member is encrypted", status="zip_invalid")
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise IntegrityError(f"unsupported compression method {info.compress_type}", status="zip_invalid")
    if info.file_size > max_uncompressed:
        raise IntegrityError(f"declared size {info.file_size} B above {max_uncompressed} B", status="size_guard_exceeded")
    if info.file_size > max_ratio * max(info.compress_size, 1):
        raise IntegrityError(f"expansion ratio above {max_ratio}x", status="size_guard_exceeded")
    return archive, info
