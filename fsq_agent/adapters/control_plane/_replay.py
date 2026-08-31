# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import base64
import binascii
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

MAX_REPLAY_VIDEO_BYTES = 24 * 1024 * 1024
_EBML_HEADER = b"\x1a\x45\xdf\xa3"
_DOCTYPE_ID = b"\x42\x82"
_SEGMENT_ID = b"\x18\x53\x80\x67"


def replay_video_metadata(run_dir: Path, video_url: str) -> dict[str, object]:
    path = _video_path(run_dir)
    if not _valid_video_path(path):
        return {"available": False, "videoUrl": None}
    return {"available": True, "mimeType": "video/webm", "sizeBytes": path.stat().st_size, "videoUrl": video_url}


def store_replay_video(run_dir: Path, mime_type: object, encoded: object) -> dict[str, object]:
    if not isinstance(mime_type, str) or not re.fullmatch(r"video/webm(?:;codecs=[a-zA-Z0-9.,_-]+)?", mime_type.casefold()):
        raise ValueError("Only video/webm replay uploads are supported.")
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("videoBase64 is required.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Replay video is not valid base64.") from exc
    if not data:
        raise ValueError("Replay video is empty.")
    if len(data) > MAX_REPLAY_VIDEO_BYTES:
        raise OverflowError("Replay video exceeds the 24 MiB upload limit.")
    if not _is_webm_container(data):
        raise ValueError("Replay video is not a valid WebM container.")
    path = _video_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".webm.tmp")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"available": True, "mimeType": "video/webm", "sizeBytes": len(data)}


def read_replay_video(run_dir: Path, range_header: str | None) -> tuple[int, bytes, dict[str, str]]:
    path = _video_path(run_dir)
    if not _valid_video_path(path):
        raise FileNotFoundError("Replay video is unavailable.")
    total = path.stat().st_size
    headers = {"Content-Type": "video/webm", "Accept-Ranges": "bytes"}
    if not range_header:
        return 200, path.read_bytes(), headers
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
    if not match or (not match.group(1) and not match.group(2)):
        raise ValueError("Invalid replay video byte range.")
    if match.group(1):
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else total - 1
    else:
        length = int(match.group(2))
        start = max(0, total - length)
        end = total - 1
    if start < 0 or start >= total or end < start:
        raise ValueError("Replay video byte range is unsatisfiable.")
    end = min(end, total - 1)
    with path.open("rb") as handle:
        handle.seek(start)
        data = handle.read(end - start + 1)
    return 206, data, {**headers, "Content-Range": f"bytes {start}-{end}/{total}"}


def _video_path(run_dir: Path) -> Path:
    return run_dir.resolve() / "control-plane-replay" / "replay.webm"


def _valid_video_path(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size > MAX_REPLAY_VIDEO_BYTES:
            return False
        with path.open("rb") as handle:
            return _is_webm_container(handle.read(MAX_REPLAY_VIDEO_BYTES + 1))
    except OSError:
        return False


def _is_webm_container(data: bytes) -> bool:
    if not data.startswith(_EBML_HEADER):
        return False
    header_size = _read_vint_size(data, len(_EBML_HEADER))
    if header_size is None:
        return False
    payload_size, size_width = header_size
    payload_start = len(_EBML_HEADER) + size_width
    payload_end = payload_start + payload_size
    if payload_end > len(data) or data[payload_end : payload_end + len(_SEGMENT_ID)] != _SEGMENT_ID:
        return False
    offset = payload_start
    document_type: bytes | None = None
    while offset < payload_end:
        element_id = _read_vint_id(data, offset)
        if element_id is None:
            return False
        identifier, id_width = element_id
        element_size = _read_vint_size(data, offset + id_width)
        if element_size is None:
            return False
        length, length_width = element_size
        value_start = offset + id_width + length_width
        value_end = value_start + length
        if value_end > payload_end:
            return False
        if identifier == _DOCTYPE_ID:
            if document_type is not None:
                return False
            document_type = data[value_start:value_end].lower()
        offset = value_end
    segment_size_offset = payload_end + len(_SEGMENT_ID)
    segment_size = _read_vint_size(data, segment_size_offset)
    if segment_size is None:
        return False
    segment_length, segment_size_width = segment_size
    segment_start = segment_size_offset + segment_size_width
    segment_unknown = segment_length == _unknown_vint_value(segment_size_width)
    segment_end = len(data) if segment_unknown else segment_start + segment_length
    if segment_end > len(data) or (not segment_unknown and segment_end != len(data)):
        return False
    offset = segment_start
    while offset < segment_end:
        child_id = _read_vint_id(data, offset)
        if child_id is None:
            return False
        _, child_id_width = child_id
        child_size = _read_vint_size(data, offset + child_id_width)
        if child_size is None:
            return False
        child_length, child_size_width = child_size
        child_unknown = child_length == _unknown_vint_value(child_size_width)
        offset += child_id_width + child_size_width
        if child_unknown:
            return document_type == b"webm" and offset < segment_end
        offset += child_length
        if offset > segment_end:
            return False
    return offset == segment_end and document_type == b"webm"


def _read_vint_id(data: bytes, offset: int) -> tuple[bytes, int] | None:
    if offset >= len(data) or data[offset] == 0:
        return None
    first = data[offset]
    width = next((index for index in range(1, 5) if first & (1 << (8 - index))), None)
    if width is None or offset + width > len(data):
        return None
    return data[offset : offset + width], width


def _read_vint_size(data: bytes, offset: int) -> tuple[int, int] | None:
    if offset >= len(data) or data[offset] == 0:
        return None
    first = data[offset]
    width = next((index for index in range(1, 9) if first & (1 << (8 - index))), None)
    if width is None or offset + width > len(data):
        return None
    value = first & ((1 << (8 - width)) - 1)
    for byte in data[offset + 1 : offset + width]:
        value = (value << 8) | byte
    return value, width


def _unknown_vint_value(width: int) -> int:
    return (1 << (7 * width)) - 1


__all__ = ["MAX_REPLAY_VIDEO_BYTES", "read_replay_video", "replay_video_metadata", "store_replay_video"]
