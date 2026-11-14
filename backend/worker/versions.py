"""Build-time inventory of the worker image (written to /opt/stellaris/versions.json)."""

import json
import platform
import sys
from importlib import metadata

packages = sorted(
    ({"name": dist.metadata["Name"], "version": dist.version} for dist in metadata.distributions()),
    key=lambda item: (item["name"] or "").lower(),
)
info = {
    "python": sys.version.split()[0],
    "implementation": platform.python_implementation(),
    "machine": platform.machine(),
    "packages": packages,
}
try:
    import av
    import cv2
    import numpy

    info["libraries"] = {"numpy": numpy.__version__, "opencv": cv2.__version__, "pyav": av.__version__,
                         "ffmpeg_libraries": {k: ".".join(map(str, v)) for k, v in av.library_versions.items()}}
except Exception as exc:  # Recorded rather than hidden.
    info["libraries_error"] = repr(exc)
json.dump(info, sys.stdout, indent=1, sort_keys=True)
