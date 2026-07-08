import os
import shutil
import sys
from pathlib import Path

ENV_EXECUTABLE = "AUTOREMESHER_PATH"


def _resolve_app_bundle(path):
    """
    If *path* is a macOS ``.app`` bundle, resolve it to the actual
    executable binary inside ``Contents/MacOS/``.
    Otherwise return *path* unchanged.
    """
    path = Path(path)
    if not (path.name.endswith(".app") and path.is_dir()):
        return path

    macos_dir = path / "Contents" / "MacOS"
    if not macos_dir.is_dir():
        return path

    app_stem = path.stem
    # Try same-stem, lowercased stem, then a generic "autoremesher" fallback
    for name in (app_stem, app_stem.lower(), "autoremesher"):
        candidate = macos_dir / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    return path


def resolve_executable_path(configured_path="", *, which=shutil.which):
    configured = str(configured_path).strip()
    if configured:
        return _resolve_app_bundle(Path(configured))

    env_path = os.environ.get(ENV_EXECUTABLE, "").strip()
    if env_path:
        return _resolve_app_bundle(Path(env_path))

    exe = which("autoremesher") or which("autoremesher.exe")
    if exe:
        return _resolve_app_bundle(Path(exe))

    if sys.platform == "darwin":
        default_app = Path("/Applications/autoremesher.app")
        if default_app.is_dir():
            resolved = _resolve_app_bundle(default_app)
            if resolved != default_app:
                return resolved

    return Path()


def validate_executable(executable_path):
    if not str(executable_path).strip() or str(Path(executable_path)) == ".":
        return (
            "AutoRemesher executable is not configured. Set it in add-on "
            f"preferences, {ENV_EXECUTABLE}, or PATH."
        )
    path = Path(executable_path)

    # Regular file
    if path.is_file():
        return ""

    # macOS .app bundle (directory)
    if sys.platform == "darwin" and path.name.endswith(".app") and path.is_dir():
        return ""

    return f"AutoRemesher executable not found: {path}"


def build_autoremesher_command(
    executable_path,
    input_path,
    output_path,
    report_path,
    *,
    target_quads,
    edge_scaling,
    sharp_edge,
    smooth_normal,
    adaptivity,
):
    return [
        str(executable_path),
        "-i",
        str(input_path),
        "-o",
        str(output_path),
        "--report",
        str(report_path),
        "--target-quads",
        str(target_quads),
        "--edge-scaling",
        str(edge_scaling),
        "--sharp-edge",
        str(sharp_edge),
        "--smooth-normal",
        str(smooth_normal),
        "--adaptivity",
        str(adaptivity),
    ]
