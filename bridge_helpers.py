import os
from pathlib import Path
import shutil


ENV_EXECUTABLE = "AUTOREMESHER_PATH"


def resolve_executable_path(configured_path="", *, which=shutil.which):
    configured = str(configured_path).strip()
    if configured:
        return Path(configured)

    env_path = os.environ.get(ENV_EXECUTABLE, "").strip()
    if env_path:
        return Path(env_path)

    path_match = which("autoremesher")
    if path_match:
        return Path(path_match)

    path_match = which("autoremesher.exe")
    if path_match:
        return Path(path_match)

    return Path()


def validate_executable(executable_path):
    if not str(executable_path).strip():
        return (
            "AutoRemesher executable is not configured. Set it in add-on "
            f"preferences, {ENV_EXECUTABLE}, or PATH."
        )
    path = Path(executable_path)
    if str(path) == ".":
        return (
            "AutoRemesher executable is not configured. Set it in add-on "
            f"preferences, {ENV_EXECUTABLE}, or PATH."
        )
    if not path.is_file():
        return f"AutoRemesher executable not found: {path}"
    return ""


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
