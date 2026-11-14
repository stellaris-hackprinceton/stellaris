"""Server-side content validation and metadata extraction for artifact bytes.

Client MIME types and timing claims are not trusted:
  * video/image: ffprobe is forced to the demuxer implied by the declared MIME type, must
    find a video stream, and must decode at least one frame. Dimensions, duration, frame
    count, and nominal frame rate come from ffprobe.
  * text: the whole file must be strict UTF-8 without NUL bytes (streamed, bounded memory).
  * application/json (generated artifacts only): strict JSON with finite numbers.

ffprobe parses untrusted media inside the trusted API container, so it runs as uid/gid
65534 with address-space and CPU rlimits, a wall-clock timeout, an empty environment, and
the file protocol only. A separate throwaway container would be stronger isolation.
"""

import codecs
import json
import math
import subprocess
import sys

from .errors import ApiError
from .http import strict_loads

ARTIFACT_KINDS = ("document", "dataset", "image", "video", "audio", "code", "chart", "report", "log", "environment")

# mime -> (validator, forced ffprobe demuxer, kinds allowed for uploads, kinds allowed for generated artifacts)
TYPES = {
    "video/mp4": ("av", "mov", {"video"}, {"video"}),
    "video/quicktime": ("av", "mov", {"video"}, {"video"}),
    "video/webm": ("av", "matroska", {"video"}, {"video"}),
    "image/png": ("image", "png_pipe", {"image"}, {"image", "chart"}),
    "image/jpeg": ("image", "jpeg_pipe", {"image"}, {"image", "chart"}),
    "text/plain": ("text", None, {"document", "dataset", "code"}, {"document", "dataset", "code", "log", "environment"}),
    "text/markdown": ("text", None, {"document"}, {"document", "report"}),
    "text/csv": ("text", None, {"dataset"}, {"dataset"}),
    "text/x-python": ("text", None, {"code"}, {"code"}),
    "application/json": ("json", None, set(), {"dataset", "environment", "document", "log"}),
    "application/pdf": ("pdf", None, {"document"}, {"document"}),
    "application/gzip": ("gzip", None, set(), {"document"}),
    "application/x-tar": ("tar", None, set(), {"document"}),
}
UPLOAD_MIME_TYPES = sorted(m for m, spec in TYPES.items() if spec[2])
INLINE_MIME_TYPES = {"image/png", "image/jpeg", "video/mp4", "video/webm", "video/quicktime",
                     "text/plain", "text/markdown", "text/csv"}
MAX_JSON_BYTES = 16 * 1024 * 1024
PROBE_MEMORY_BYTES = 1024 * 1024 * 1024
PROBE_UID = 65534
_CHUNK = 1024 * 1024

# Fixed launcher: applies rlimits, then execs the fixed ffprobe argv. No shell involved.
_LIMITED_EXEC = (
    "import os,resource,sys;"
    "m,c=int(sys.argv[1]),int(sys.argv[2]);"
    "resource.setrlimit(resource.RLIMIT_AS,(m,m));"
    "resource.setrlimit(resource.RLIMIT_CPU,(c,c));"
    "os.execv(sys.argv[3],sys.argv[3:])"
)


def content_type_header(mime_type: str) -> str:
    return f"{mime_type}; charset=utf-8" if mime_type.startswith("text/") or mime_type == "application/json" else mime_type


def decode_failed(message: str) -> ApiError:
    return ApiError(422, "MEDIA_DECODE_FAILED", message)


def inspect_file(path: str, mime_type: str, config) -> dict:
    """Validate the bytes at `path` against `mime_type`; return Artifact metadata fields."""
    validator, demuxer = TYPES[mime_type][0], TYPES[mime_type][1]
    if validator == "text":
        _check_utf8(path)
        return {}
    if validator == "json":
        _check_json(path)
        return {}
    if validator in SIGNATURES:
        _check_signature(path, validator)
        return {}
    probe = _ffprobe(path, demuxer, config, [
        "-select_streams", "v:0", "-count_frames", "-read_intervals", "%+#5", "-show_format", "-show_streams",
    ])
    streams = probe.get("streams") or []
    stream = streams[0] if streams else {}
    if stream.get("codec_type") != "video":
        raise decode_failed("No decodable video or image stream was found.")
    if _int(stream.get("nb_read_frames")) is None or _int(stream.get("nb_read_frames")) < 1:
        raise decode_failed("No frame could be decoded.")
    width, height = _int(stream.get("width")), _int(stream.get("height"))
    if not width or not height or width < 1 or height < 1:
        raise decode_failed("Frame dimensions could not be determined.")
    if _rotation(stream) % 180 == 90:  # Report dimensions of the displayed (rotated) frame.
        width, height = height, width
    metadata = {"width_px": width, "height_px": height}
    if validator == "image":
        return metadata

    duration = _float((probe.get("format") or {}).get("duration"))
    if duration is None:
        # Browser MediaRecorder WebM files often omit the container duration; derive it
        # from the video packets' timestamps instead.
        duration = _packet_duration(_ffprobe(path, demuxer, config, [
            "-select_streams", "v:0", "-show_entries", "packet=pts_time,duration_time",
        ]))
    if duration is None or duration <= 0:
        raise decode_failed("Video duration could not be determined.")
    duration_ms = int(round(duration * 1000))
    if duration_ms > config.max_video_duration_ms:
        raise ApiError(422, "VALIDATION_FAILED", "Video is longer than the maximum allowed duration.",
                       details={"field_errors": [{"path": "", "message":
                                                  f"Duration {duration_ms} ms exceeds {config.max_video_duration_ms} ms."}]})
    metadata["duration_ms"] = duration_ms
    frame_count = _int(stream.get("nb_frames"))
    if frame_count and frame_count > 0:
        metadata["frame_count"] = frame_count
    fps = _rate(stream.get("avg_frame_rate")) or _rate(stream.get("r_frame_rate"))
    if fps:
        metadata["nominal_frame_rate_fps"] = round(fps, 6)
    return metadata


def _packet_duration(probe: dict):
    starts, ends = [], []
    for packet in probe.get("packets") or []:
        pts = _float(packet.get("pts_time"))
        if pts is not None:
            starts.append(pts)
            ends.append(pts + (_float(packet.get("duration_time")) or 0.0))
    if not starts:
        return None
    return max(ends) - min(starts)


def _ffprobe(path: str, demuxer: str, config, probe_args) -> dict:
    """Run ffprobe with a fixed argv: forced demuxer, file protocol only, one decoder thread."""
    timeout = config.media_probe_timeout_s
    argv = [
        sys.executable, "-I", "-c", _LIMITED_EXEC, str(PROBE_MEMORY_BYTES), str(max(1, int(timeout))),
        "/usr/bin/ffprobe", "-v", "error", "-hide_banner", "-protocol_whitelist", "file", "-threads", "1",
        "-f", demuxer, *probe_args, "-of", "json", f"file:{path}",
    ]
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL,
                              env={"MALLOC_ARENA_MAX": "2"}, user=PROBE_UID, group=PROBE_UID, extra_groups=[])
    except FileNotFoundError:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "Media inspection is unavailable.", retryable=True)
    except subprocess.TimeoutExpired:
        raise decode_failed("Media inspection timed out.")
    if proc.returncode != 0:
        raise decode_failed("The file could not be decoded as the declared media type.")
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        raise decode_failed("Media inspection returned unreadable output.")
    return data if isinstance(data, dict) else {}


SIGNATURES = {"pdf": "PDF", "gzip": "gzip", "tar": "tar"}


def _check_signature(path: str, validator: str) -> None:
    """Magic-byte check only; document parsing happens in the isolated worker."""
    with open(path, "rb") as fh:
        head = fh.read(1024)
    ok = {"pdf": b"%PDF-" in head, "gzip": head[:2] == b"\x1f\x8b",
          "tar": len(head) > 262 and head[257:262] == b"ustar"}[validator]
    if not ok:
        raise decode_failed(f"The content is not a {SIGNATURES[validator]} file.")


def _check_utf8(path: str) -> None:
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    try:
        with open(path, "rb") as fh:
            while chunk := fh.read(_CHUNK):
                if b"\x00" in chunk:
                    raise decode_failed("Text content must not contain NUL bytes.")
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        raise decode_failed("Text content must be valid UTF-8.")


def _check_json(path: str) -> None:
    with open(path, "rb") as fh:
        raw = fh.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise decode_failed("JSON artifacts are limited to 16 MiB.")
    try:
        strict_loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise decode_failed("Content is not valid UTF-8 JSON with finite numbers.")


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _rate(value):
    try:
        num, den = (int(part) for part in str(value).split("/"))
    except (TypeError, ValueError):
        return None
    return num / den if num > 0 and den > 0 else None


def _rotation(stream) -> int:
    rotation = 0.0
    for side_data in stream.get("side_data_list") or []:
        if isinstance(side_data, dict) and _float(side_data.get("rotation")) is not None:
            rotation = _float(side_data.get("rotation"))
    tag = _float((stream.get("tags") or {}).get("rotate"))
    if tag is not None:
        rotation = tag
    return int(round(rotation)) % 360
