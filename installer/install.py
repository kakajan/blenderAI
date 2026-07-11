#!/usr/bin/env python3
"""Universal BlenderAI installer entry point (Windows / macOS / Linux)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    here = Path(__file__).resolve().parent
    req = here / "requirements.txt"
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print("Installing installer dependencies…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])

    # Prefer GUI; fall back to CLI if display unavailable
    if "--cli" in sys.argv:
        return _cli()
    try:
        from gui import main as gui_main

        gui_main()
        return 0
    except Exception as e:
        print(f"GUI unavailable ({e}); falling back to CLI.\n")
        return _cli()


def _cli() -> int:
    from install_core import InstallOptions, current_platform_label, discover_blenders, run_install

    print(f"BlenderAI Installer — {current_platform_label()}")
    blenders = discover_blenders()
    if not blenders:
        path = input("Blender executable path: ").strip().strip('"')
        if not path:
            print("No Blender selected.")
            return 1
        from pathlib import Path as P
        from install_core import BlenderInstall, _config_dir_for_version, _probe_version

        exe = P(path)
        ver = _probe_version(exe) or "4.2"
        blenders = [BlenderInstall(version=ver, blender_exe=exe, config_dir=_config_dir_for_version(ver))]

    print("Found:")
    for i, b in enumerate(blenders):
        print(f"  [{i}] {b.label}")
    idx = 0
    if len(blenders) > 1:
        raw = input(f"Select [0-{len(blenders)-1}] (default 0): ").strip() or "0"
        idx = int(raw)
    opts = InstallOptions(blender=blenders[idx])

    def progress(msg: str, pct: float) -> None:
        print(f"[{int(pct*100):3d}%] {msg}")

    result = run_install(opts, progress=progress)
    for m in result.messages:
        print(m)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
