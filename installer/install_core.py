"""BlenderAI installer — core install logic (no UI)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ProgressCb = Callable[[str, float], None]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def appdata_blenderai() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "BlenderAI"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class BlenderInstall:
    version: str
    blender_exe: Path
    config_dir: Path  # .../Blender/<ver>

    @property
    def extensions_user_default(self) -> Path:
        return self.config_dir / "extensions" / "user_default"

    @property
    def label(self) -> str:
        return f"Blender {self.version} — {self.blender_exe}"


@dataclass
class InstallOptions:
    blender: BlenderInstall
    install_sidecar: bool = True
    build_webui: bool = True
    enable_extension: bool = True
    create_shortcuts: bool = True
    install_mcp: bool = True


@dataclass
class InstallResult:
    ok: bool
    messages: list[str] = field(default_factory=list)
    extension_path: Path | None = None
    sidecar_path: Path | None = None
    webui_url: str = "http://127.0.0.1:8765"


def discover_blenders() -> list[BlenderInstall]:
    found: dict[str, BlenderInstall] = {}

    def add(exe: Path, version_hint: str = "") -> None:
        if not exe.is_file():
            return
        version = version_hint or _probe_version(exe) or "unknown"
        key = f"{version}|{exe.resolve()}"
        config = _config_dir_for_version(version)
        found[key] = BlenderInstall(version=version, blender_exe=exe.resolve(), config_dir=config)

    # Windows common paths
    if os.name == "nt":
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        pf86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        for base in (pf / "Blender Foundation", pf86 / "Blender Foundation", local / "Programs"):
            if not base.exists():
                continue
            for child in base.rglob("blender.exe"):
                ver = ""
                for part in child.parts:
                    if part.startswith("Blender ") and any(c.isdigit() for c in part):
                        ver = part.replace("Blender ", "").strip()
                add(child, ver)
        # Steam
        steam = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam" / "steamapps" / "common"
        if steam.exists():
            for child in steam.rglob("blender.exe"):
                add(child)
        # Windows registry uninstall entries
        for exe, ver in _registry_blender_exes():
            add(exe, ver)

    # macOS
    if sys.platform == "darwin":
        mac_candidates = [
            Path("/Applications/Blender.app/Contents/MacOS/Blender"),
            Path.home() / "Applications" / "Blender.app" / "Contents" / "MacOS" / "Blender",
        ]
        # Multiple versioned apps: Blender 4.2.app, Blender 4.5.app
        for apps_root in (Path("/Applications"), Path.home() / "Applications"):
            if apps_root.exists():
                for app in apps_root.glob("Blender*.app"):
                    exe = app / "Contents" / "MacOS" / "Blender"
                    mac_candidates.append(exe)
        # Homebrew cask / intel & apple silicon
        for brew in (
            Path("/opt/homebrew/bin/blender"),
            Path("/usr/local/bin/blender"),
            Path("/opt/homebrew/Caskroom"),
        ):
            if brew.is_file():
                mac_candidates.append(brew)
            elif brew.is_dir():
                for exe in brew.rglob("Blender"):
                    if exe.is_file() and "MacOS" in exe.parts:
                        mac_candidates.append(exe)
        for exe in mac_candidates:
            ver = ""
            for part in exe.parts:
                if part.startswith("Blender") and any(c.isdigit() for c in part):
                    ver = part.replace("Blender", "").replace(".app", "").strip()
            add(exe, ver)

    # Linux
    if sys.platform.startswith("linux"):
        linux_candidates = [
            Path("/usr/bin/blender"),
            Path("/usr/local/bin/blender"),
            Path.home() / ".local" / "bin" / "blender",
            Path("/snap/bin/blender"),
            Path("/var/lib/flatpak/exports/bin/blender"),
            Path.home() / ".local" / "share" / "flatpak" / "exports" / "bin" / "blender",
        ]
        # Flatpak binary path
        flatpak = Path("/var/lib/flatpak/app/org.blender.Blender")
        if flatpak.exists():
            for exe in flatpak.rglob("blender"):
                if exe.is_file() and os.access(exe, os.X_OK) and "bin" in exe.parts:
                    linux_candidates.append(exe)
        # Extracted official tarballs in home
        for base in (Path.home(), Path.home() / "Applications", Path.home() / "apps", Path("/opt")):
            if not base.exists():
                continue
            try:
                for exe in base.glob("blender-*/blender"):
                    linux_candidates.append(exe)
                for exe in base.glob("Blender*/blender"):
                    linux_candidates.append(exe)
            except PermissionError:
                pass
        for exe in linux_candidates:
            add(exe)

    # PATH (all platforms)
    which = shutil.which("blender")
    if which:
        add(Path(which))

    items = list(found.values())
    items.sort(key=lambda b: _version_key(b.version), reverse=True)
    return [b for b in items if _version_ok(b.version)] or items


def _registry_blender_exes() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    if os.name != "nt":
        return out
    try:
        import winreg
    except ImportError:
        return out
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in roots:
        try:
            key = winreg.OpenKey(hive, path)
        except OSError:
            continue
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(key, i)
            except OSError:
                break
            i += 1
            try:
                sk = winreg.OpenKey(key, sub)
                name, _ = winreg.QueryValueEx(sk, "DisplayName")
                if not str(name).lower().startswith("blender"):
                    continue
                loc, _ = winreg.QueryValueEx(sk, "InstallLocation")
                ver = ""
                try:
                    ver, _ = winreg.QueryValueEx(sk, "DisplayVersion")
                except OSError:
                    pass
                exe = Path(str(loc)) / "blender.exe"
                if exe.exists():
                    out.append((exe, str(ver)))
            except OSError:
                continue
    return out


def _blender_config_root() -> Path:
    if os.name == "nt":
        return Path(os.environ["APPDATA"]) / "Blender Foundation" / "Blender"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Blender"
    return Path.home() / ".config" / "blender"


def _config_dir_for_version(version: str) -> Path:
    major_minor = ".".join(version.split(".")[:2]) if version and version[0].isdigit() else version
    if not major_minor or major_minor == "unknown":
        # default to newest config folder
        root = _blender_config_root()
        if root.exists():
            vers = sorted(
                [p for p in root.iterdir() if p.is_dir() and p.name[0].isdigit()],
                key=lambda p: _version_key(p.name),
                reverse=True,
            )
            if vers:
                return vers[0]
        major_minor = "4.2"
    return _blender_config_root() / major_minor


def _probe_version(exe: Path) -> str:
    try:
        out = subprocess.check_output([str(exe), "--version"], text=True, stderr=subprocess.STDOUT, timeout=8)
        # Blender 4.2.0
        for line in out.splitlines():
            if line.lower().startswith("blender"):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1].strip()
    except Exception:
        pass
    return ""


def _version_key(v: str) -> tuple:
    nums = []
    for part in v.replace("-", ".").split("."):
        if part.isdigit():
            nums.append(int(part))
        else:
            break
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def _version_ok(v: str) -> bool:
    if not v or v == "unknown":
        return True
    major, minor, *_ = _version_key(v)
    return (major, minor) >= (4, 2)


def _progress(cb: ProgressCb | None, msg: str, pct: float) -> None:
    if cb:
        cb(msg, pct)


def build_extension_zip(dest_zip: Path, progress: ProgressCb | None = None) -> Path:
    src = repo_root() / "extension"
    if not (src / "blender_manifest.toml").exists():
        raise FileNotFoundError("extension/blender_manifest.toml missing")
    if not (src / "__init__.py").exists():
        raise FileNotFoundError("extension/__init__.py missing (flat layout required)")
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    if dest_zip.exists():
        dest_zip.unlink()
    _progress(progress, "Packaging Blender extension…", 0.15)
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in src.rglob("*"):
            if path.is_file():
                if "__pycache__" in path.parts or path.suffix == ".pyc":
                    continue
                if path.name == "install_info.json":
                    continue
                zf.write(path, path.relative_to(src).as_posix())
    return dest_zip


def install_extension_copy(blender: BlenderInstall, progress: ProgressCb | None = None) -> Path:
    """Copy flat extension package into user_default/blender_ai.

    Blender requires ``blender_manifest.toml`` and ``__init__.py`` in the same
    directory (see developer.blender.org extensions handbook).
    """
    target_root = blender.extensions_user_default
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / "blender_ai"
    src = repo_root() / "extension"
    _progress(progress, f"Installing extension → {target}", 0.35)
    if not (src / "blender_manifest.toml").exists() or not (src / "__init__.py").exists():
        raise FileNotFoundError(
            "extension/ must contain blender_manifest.toml and __init__.py at the root"
        )
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.zip", ".git", "install_info.json")
    for item in src.iterdir():
        if item.name in ("__pycache__",) or item.suffix in (".pyc", ".zip"):
            continue
        if item.name == "install_info.json":
            continue
        dest = target / item.name
        if item.is_dir():
            shutil.copytree(item, dest, ignore=ignore)
        elif item.is_file():
            shutil.copy2(item, dest)

    marker = {
        "sidecar_dir": str(appdata_blenderai() / "sidecar"),
        "data_dir": str(appdata_blenderai()),
        "installed_by": "BlenderAI Installer",
    }
    marker_text = json.dumps(marker, indent=2)
    # Convenience copy next to package (optional) + canonical AppData copy
    (target / "install_info.json").write_text(marker_text, encoding="utf-8")
    (appdata_blenderai() / "install_info.json").write_text(marker_text, encoding="utf-8")
    return target


EXTENSION_MODULE_CANDIDATES = (
    "bl_ext.user_default.blender_ai",
    "blender_ai",
)

_ENABLE_PY = """\
import addon_utils
import bpy

candidates = __CANDIDATES__
ok = False
try:
    addon_utils.modules_refresh()
except Exception:
    pass

for mod in candidates:
    try:
        try:
            addon_utils.enable(mod, default_set=True, persistent=True)
        except TypeError:
            addon_utils.enable(mod, default_set=True)
    except Exception as exc:
        print("ENABLE_ERR", mod, exc)
        continue
    keys = list(bpy.context.preferences.addons.keys())
    if mod in keys or any(mod in k for k in keys):
        ok = True
        print("ENABLED", mod)
        break

if not ok:
    for mod in candidates:
        try:
            bpy.ops.preferences.addon_enable(module=mod)
            ok = True
            print("OPS_ENABLED", mod)
            break
        except Exception as exc:
            print("OPS_ERR", mod, exc)

try:
    bpy.ops.wm.save_userpref()
    print("SAVED_PREFS")
except Exception as exc:
    print("SAVE_PREFS_ERR", exc)

raise SystemExit(0 if ok else 1)
"""


def try_cli_install(blender: BlenderInstall, zip_path: Path, progress: ProgressCb | None = None) -> bool:
    """Install from zip into user_default and enable (official Blender CLI)."""
    _progress(progress, "Trying Blender CLI extension install + enable…", 0.3)
    cmd = [
        str(blender.blender_exe),
        "--command",
        "extension",
        "install-file",
        "-r",
        "user_default",
        "--enable",
        str(zip_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0:
            return True
        err = (proc.stderr or proc.stdout or "").strip()
        if err:
            _progress(progress, f"CLI install note: {err[:200]}", 0.32)
        return False
    except Exception as exc:
        _progress(progress, f"CLI install failed: {exc}", 0.32)
        return False


def try_enable_via_python(blender: BlenderInstall, progress: ProgressCb | None = None) -> bool:
    """Enable BlenderAI in user preferences via background Blender Python."""
    _progress(progress, "Enabling BlenderAI in Blender preferences…", 0.42)
    script = appdata_blenderai() / "cache" / "enable_blender_ai.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        _ENABLE_PY.replace("__CANDIDATES__", repr(list(EXTENSION_MODULE_CANDIDATES))),
        encoding="utf-8",
    )
    cmd = [
        str(blender.blender_exe),
        "--background",
        "--offline-mode",
        "--python",
        str(script),
        "--python-exit-code",
        "1",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if proc.returncode == 0 and ("ENABLED" in out or "OPS_ENABLED" in out):
            return True
        if out:
            # Keep log short for the installer UI
            tail = "\n".join(out.splitlines()[-8:])
            _progress(progress, f"Enable script: {tail[:300]}", 0.43)
        return False
    except Exception as exc:
        _progress(progress, f"Enable via Python failed: {exc}", 0.43)
        return False


def enable_extension(
    blender: BlenderInstall,
    zip_path: Path,
    progress: ProgressCb | None = None,
) -> bool:
    """Ensure BlenderAI is enabled after files are on disk (CLI, then Python fallback)."""
    if try_cli_install(blender, zip_path, progress):
        return True
    return try_enable_via_python(blender, progress)


def _pids_listening_on_port(port: int) -> set[int]:
    """Best-effort PIDs bound to TCP port (Windows / Unix)."""
    pids: set[int] = set()
    if os.name == "nt":
        # netstat is more reliable than Get-NetTCPConnection (no admin / module quirks)
        try:
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            needle = f":{port}"
            for line in out.splitlines():
                if "LISTENING" not in line.upper():
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                local = parts[1]
                if not local.endswith(needle):
                    continue
                pid_s = parts[-1]
                if pid_s.isdigit():
                    pids.add(int(pid_s))
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue)"
                    f".OwningProcess | Select-Object -Unique",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    pids.add(int(line))
        except Exception:
            pass
        return pids
    try:
        out = subprocess.check_output(
            ["lsof", "-ti", f"TCP:{port}", "-sTCP:LISTEN"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                pids.add(int(line))
    except Exception:
        pass
    return pids


def _pids_matching_sidecar() -> set[int]:
    """PIDs whose command line looks like the BlenderAI sidecar."""
    pids: set[int] = set()
    markers = ("blender_ai_sidecar", "blenderai\\sidecar", "blenderai/sidecar")
    if os.name == "nt":
        try:
            out = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_Process "
                    "-Filter \"Name='python.exe' OR Name='pythonw.exe' OR Name='uvicorn.exe'\" "
                    "| ForEach-Object { '{0}`t{1}' -f $_.ProcessId, $_.CommandLine }",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
            for line in out.splitlines():
                low = line.lower()
                if not any(m in low for m in markers):
                    continue
                pid_s = line.split("\t", 1)[0].strip()
                if pid_s.isdigit():
                    pids.add(int(pid_s))
        except Exception:
            pass
        return pids
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,command="], text=True, timeout=10)
        for line in out.splitlines():
            low = line.lower()
            if not any(m in low for m in markers):
                continue
            parts = line.strip().split(None, 1)
            if parts and parts[0].isdigit():
                pids.add(int(parts[0]))
    except Exception:
        pass
    return pids


def _kill_pids(pids: set[int]) -> None:
    me = os.getpid()
    for pid in sorted(pids):
        if pid <= 0 or pid == me:
            continue
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                )
            else:
                os.kill(pid, 15)
        except Exception:
            pass


def stop_running_sidecar(port: int = 8765, progress: ProgressCb | None = None) -> None:
    """Stop a live sidecar so AppData files can be replaced on reinstall."""
    pids = _pids_listening_on_port(port) | _pids_matching_sidecar()
    if not pids:
        return
    _progress(progress, "Stopping running sidecar…", 0.48)
    _kill_pids(pids)
    # Windows often needs a beat to release DLL / .pyd locks
    for _ in range(10):
        time.sleep(0.35)
        leftover = _pids_listening_on_port(port) | _pids_matching_sidecar()
        if not leftover:
            break
        _kill_pids(leftover)


def _rmtree_retry(path: Path, *, retries: int = 12, delay: float = 0.4) -> None:
    """Remove a directory tree; retry briefly for Windows file locks."""
    if not path.exists():
        return
    last: OSError | None = None
    for i in range(retries):
        try:
            shutil.rmtree(path)
            return
        except OSError as exc:
            last = exc
            if i in (2, 5, 8):
                stop_running_sidecar()
            time.sleep(delay * (1 + i * 0.35))
    if path.exists():
        raise RuntimeError(
            f"Cannot remove {path} (still in use). "
            "Close BlenderAI Chat UI / stop the sidecar (N-Panel → Stop), then retry."
        ) from last


def _clear_sidecar_contents(dest: Path) -> None:
    """Delete everything under dest except a preserved .venv (in-place update)."""
    if not dest.exists():
        return
    for child in list(dest.iterdir()):
        if child.name == ".venv":
            continue
        if child.is_dir():
            _rmtree_retry(child)
        else:
            for _ in range(8):
                try:
                    child.unlink()
                    break
                except OSError:
                    stop_running_sidecar()
                    time.sleep(0.35)


def _overlay_copytree(src: Path, dest: Path, *, ignore_dir_names: set[str] | None = None) -> None:
    """Copy src into dest (create or overlay). Used when rmtree of dest may fail."""
    if not src.exists():
        return
    skip = set(ignore_dir_names or ())
    if not dest.exists():
        patterns = list(skip | {"__pycache__"}) + ["*.egg-info", "*.pyc"]
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*patterns))
        return
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        dirs[:] = [
            d for d in dirs if d not in skip and d != "__pycache__" and not d.endswith(".egg-info")
        ]
        target_dir = dest / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            if name.endswith(".pyc"):
                continue
            shutil.copy2(Path(root) / name, target_dir / name)


def _copy_sidecar_sources(src: Path, dest: Path) -> None:
    ignore = shutil.ignore_patterns(".venv", "__pycache__", "*.egg-info", ".pytest_cache")
    if not dest.exists():
        shutil.copytree(src, dest, ignore=ignore)
        return
    # Overlay into existing tree (avoids deleting a locked root folder)
    _overlay_copytree(src, dest, ignore_dir_names={".venv", "__pycache__", ".pytest_cache"})


def install_sidecar(progress: ProgressCb | None = None) -> Path:
    dest = appdata_blenderai() / "sidecar"
    src = repo_root() / "sidecar"
    data = appdata_blenderai()
    tmp_venv = data / "_venv_backup"

    # Running sidecar locks files under dest → WinError 183 on copytree.
    stop_running_sidecar(progress=progress)
    _progress(progress, "Copying sidecar…", 0.5)

    if dest.exists():
        venv = dest / ".venv"
        if venv.exists():
            try:
                if tmp_venv.exists():
                    _rmtree_retry(tmp_venv)
                shutil.move(str(venv), str(tmp_venv))
            except OSError:
                # Keep .venv in place; update package files around it
                pass

        try:
            _rmtree_retry(dest)
        except RuntimeError:
            _progress(progress, "Sidecar folder locked — updating files in place…", 0.52)
            stop_running_sidecar(progress=progress)
            _clear_sidecar_contents(dest)

    if dest.exists():
        _clear_sidecar_contents(dest)

    _copy_sidecar_sources(src, dest)

    # Restore preserved venv (including leftover backup from a prior failed install)
    if tmp_venv.exists():
        target_venv = dest / ".venv"
        if target_venv.exists() and target_venv.resolve() != tmp_venv.resolve():
            try:
                _rmtree_retry(target_venv)
            except RuntimeError:
                pass
        if not (dest / ".venv").exists():
            try:
                shutil.move(str(tmp_venv), str(dest / ".venv"))
            except OSError:
                pass
        elif tmp_venv.exists():
            try:
                _rmtree_retry(tmp_venv)
            except RuntimeError:
                pass

    # copy skills & presets next to data (overlay if remove fails / dir locked)
    for name in ("skills", "presets"):
        s = repo_root() / name
        d = data / name
        if not s.exists():
            continue
        if d.exists():
            try:
                _rmtree_retry(d)
            except RuntimeError:
                pass
        _overlay_copytree(s, d)

    venv_py = _ensure_venv(dest, progress)
    _progress(progress, "Installing Python packages…", 0.65)
    subprocess.check_call([str(venv_py), "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"])
    subprocess.check_call([str(venv_py), "-m", "pip", "install", "-e", f"{dest}[mcp]"])

    # Write env pointer for skills paths
    cfg = {
        "skills_dir": str(data / "skills"),
        "presets_dir": str(data / "presets"),
        "webui_dist": str(data / "webui" / "dist"),
        "host": "127.0.0.1",
        "port": 8765,
    }
    (data / "install.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return dest


def _ensure_venv(sidecar_dir: Path, progress: ProgressCb | None = None) -> Path:
    venv = sidecar_dir / ".venv"
    if os.name == "nt":
        py = venv / "Scripts" / "python.exe"
    else:
        py = venv / "bin" / "python"
    if not py.exists():
        _progress(progress, "Creating virtualenv…", 0.55)
        subprocess.check_call([sys.executable, "-m", "venv", str(venv)])
    return py


def install_webui(build: bool, progress: ProgressCb | None = None) -> Path:
    dest = appdata_blenderai() / "webui" / "dist"
    src_dist = repo_root() / "webui" / "dist"
    webui = repo_root() / "webui"
    if build and (webui / "package.json").exists():
        _progress(progress, "Building WebUI…", 0.75)
        npm = shutil.which("npm")
        if npm:
            subprocess.check_call([npm, "install"], cwd=str(webui))
            subprocess.check_call([npm, "run", "build"], cwd=str(webui))
        elif not src_dist.exists():
            raise RuntimeError("npm not found and webui/dist missing — install Node.js or build WebUI first")
    if not src_dist.exists():
        raise FileNotFoundError("webui/dist not found — run npm run build in webui/")
    _progress(progress, "Copying WebUI…", 0.85)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_dist, dest)
    return dest


def create_shortcuts(sidecar_dir: Path, progress: ProgressCb | None = None) -> None:
    _progress(progress, "Creating shortcuts…", 0.92)
    data = appdata_blenderai()
    py = _venv_python(sidecar_dir)
    start_script = data / ("start-blenderai.bat" if os.name == "nt" else "start-blenderai.sh")

    if os.name == "nt":
        start_script.write_text(
            f'@echo off\n'
            f'title BlenderAI Sidecar\n'
            f'cd /d "{sidecar_dir}"\n'
            f'"{py}" -m blender_ai_sidecar.main serve\n'
            f'pause\n',
            encoding="utf-8",
        )
        # Also keep friendly name
        friendly = data / "Start BlenderAI.bat"
        friendly.write_text(start_script.read_text(encoding="utf-8"), encoding="utf-8")
        desktop = _desktop_dir()
        lnk = desktop / "BlenderAI.lnk"
        ps = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{lnk}')
$Shortcut.TargetPath = '{friendly}'
$Shortcut.WorkingDirectory = '{data}'
$Shortcut.Description = 'Start BlenderAI Sidecar'
$Shortcut.Save()
"""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            pass
        return

    # POSIX start script
    start_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"cd '{sidecar_dir}'\n"
        f"exec '{py}' -m blender_ai_sidecar.main serve\n",
        encoding="utf-8",
    )
    start_script.chmod(0o755)

    if sys.platform == "darwin":
        _create_macos_app(data, start_script, sidecar_dir)
    else:
        _create_linux_desktop(data, start_script)


def _venv_python(sidecar_dir: Path) -> Path:
    if os.name == "nt":
        return sidecar_dir / ".venv" / "Scripts" / "python.exe"
    return sidecar_dir / ".venv" / "bin" / "python"


def cursor_mcp_config_path() -> Path:
    return Path.home() / ".cursor" / "mcp.json"


def build_mcp_server_entry(sidecar_dir: Path) -> dict[str, str | list[str]]:
    py = _venv_python(sidecar_dir)
    return {
        "command": str(py.resolve()),
        "args": ["-m", "blender_ai_sidecar.main", "mcp", "--stdio"],
        "cwd": str(sidecar_dir.resolve()),
    }


def _read_json_object(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json_object(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def merge_mcp_servers(cfg_path: Path, entry: dict[str, str | list[str]], *, key: str = "mcpServers") -> Path:
    """Merge blender-ai into a standard mcpServers-style JSON config."""
    existing = _read_json_object(cfg_path)
    servers = dict(existing.get(key) or {})
    servers["blender-ai"] = entry
    merged = {**existing, key: servers}
    _write_json_object(cfg_path, merged)
    return cfg_path


def merge_vscode_mcp(cfg_path: Path, entry: dict[str, str | list[str]]) -> Path:
    """Merge blender-ai into VS Code Copilot MCP format ({ \"servers\": { ... } })."""
    existing = _read_json_object(cfg_path)
    servers = dict(existing.get("servers") or {})
    servers["blender-ai"] = {
        "type": "stdio",
        "command": entry["command"],
        "args": entry["args"],
        "cwd": entry["cwd"],
    }
    merged = {**existing, "servers": servers}
    _write_json_object(cfg_path, merged)
    return cfg_path


def claude_desktop_config_paths() -> list[Path]:
    """Possible Claude Desktop config locations (standard + Windows MSIX)."""
    home = Path.home()
    paths: list[Path] = []
    if os.name == "nt":
        appdata = Path(os.environ.get("APPDATA") or (home / "AppData" / "Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA") or (home / "AppData" / "Local"))
        paths.append(appdata / "Claude" / "claude_desktop_config.json")
        packages = local / "Packages"
        if packages.is_dir():
            for pkg in packages.glob("Claude_*"):
                candidate = pkg / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json"
                paths.append(candidate)
    elif sys.platform == "darwin":
        paths.append(home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
    else:
        paths.append(home / ".config" / "Claude" / "claude_desktop_config.json")
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p.resolve()) if p.parent.exists() else str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def windsurf_mcp_config_path() -> Path:
    return Path.home() / ".codeium" / "windsurf" / "mcp_config.json"


def claude_code_user_config_path() -> Path:
    return Path.home() / ".claude.json"


def cline_mcp_config_path() -> Path | None:
    """Cline / Roo-style MCP settings inside VS Code / Cursor extension storage."""
    home = Path.home()
    candidates: list[Path] = []
    if os.name == "nt":
        appdata = Path(os.environ.get("APPDATA") or (home / "AppData" / "Roaming"))
        candidates.extend(
            [
                appdata / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
                appdata / "Cursor" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
                appdata / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "mcp_settings.json",
            ]
        )
    elif sys.platform == "darwin":
        support = home / "Library" / "Application Support"
        candidates.extend(
            [
                support / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
                support / "Cursor" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
            ]
        )
    else:
        config = home / ".config"
        candidates.extend(
            [
                config / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
                config / "Cursor" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json",
            ]
        )
    for path in candidates:
        if path.parent.exists() or path.exists():
            return path
    return None


def install_cursor_mcp(sidecar_dir: Path, progress: ProgressCb | None = None) -> Path:
    """Register BlenderAI MCP server in Cursor (~/.cursor/mcp.json)."""
    entry = build_mcp_server_entry(sidecar_dir)
    cfg_path = merge_mcp_servers(cursor_mcp_config_path(), entry)
    if (repo_root() / "extension" / "blender_manifest.toml").exists():
        repo_mcp = repo_root() / ".cursor" / "mcp.json"
        _write_json_object(repo_mcp, {"mcpServers": {"blender-ai": entry}})
    return cfg_path


def install_mcp_clients(sidecar_dir: Path, progress: ProgressCb | None = None) -> list[tuple[str, Path]]:
    """Register blender-ai MCP in Cursor, Claude Desktop, Claude Code, Windsurf, Cline when possible."""
    _progress(progress, "Configuring MCP clients…", 0.88)
    entry = build_mcp_server_entry(sidecar_dir)
    configured: list[tuple[str, Path]] = []

    cursor_path = install_cursor_mcp(sidecar_dir, progress=None)
    configured.append(("Cursor", cursor_path))

    # Claude Desktop: write standard path always; also merge into any discovered MSIX path
    desktop_paths = claude_desktop_config_paths()
    written_desktop: set[str] = set()
    for i, path in enumerate(desktop_paths):
        # Always create the primary path; only touch extras if parent already exists
        if i == 0 or path.exists() or path.parent.exists():
            merge_mcp_servers(path, entry)
            key = str(path)
            if key not in written_desktop:
                written_desktop.add(key)
                configured.append(("Claude Desktop", path))

    claude_code_path = merge_mcp_servers(claude_code_user_config_path(), entry)
    configured.append(("Claude Code", claude_code_path))

    windsurf_dir = windsurf_mcp_config_path().parent
    if windsurf_dir.exists() or windsurf_mcp_config_path().exists():
        windsurf_path = merge_mcp_servers(windsurf_mcp_config_path(), entry)
        configured.append(("Windsurf", windsurf_path))

    cline_path = cline_mcp_config_path()
    if cline_path is not None:
        merge_mcp_servers(cline_path, entry)
        configured.append(("Cline", cline_path))

    return configured


def _desktop_dir() -> Path:
    if os.name == "nt":
        return Path.home() / "Desktop"
    if sys.platform == "darwin":
        return Path.home() / "Desktop"
    # XDG
    desktop = Path.home() / "Desktop"
    xdg = os.environ.get("XDG_DESKTOP_DIR")
    if xdg:
        return Path(xdg)
    return desktop if desktop.exists() else Path.home()


def _create_macos_app(data: Path, start_script: Path, sidecar_dir: Path) -> None:
    """Create a minimal .app bundle on Desktop + Applications Support."""
    app = data / "BlenderAI.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    launcher = macos / "BlenderAI"
    launcher.write_text(
        "#!/bin/bash\n"
        f"exec '{start_script}'\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    plist = app / "Contents" / "Info.plist"
    plist.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>BlenderAI</string>
  <key>CFBundleIdentifier</key><string>ai.blenderai.sidecar</string>
  <key>CFBundleName</key><string>BlenderAI</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0.1</string>
</dict>
</plist>
""",
        encoding="utf-8",
    )
    desktop_app = _desktop_dir() / "BlenderAI.app"
    if desktop_app.exists():
        shutil.rmtree(desktop_app, ignore_errors=True)
    try:
        shutil.copytree(app, desktop_app)
    except Exception:
        # Fallback symlink
        try:
            if desktop_app.exists() or desktop_app.is_symlink():
                desktop_app.unlink()
            desktop_app.symlink_to(app, target_is_directory=True)
        except Exception:
            pass


def _create_linux_desktop(data: Path, start_script: Path) -> None:
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=BlenderAI\n"
        "Comment=Start BlenderAI Sidecar\n"
        f"Exec={start_script}\n"
        "Terminal=true\n"
        "Categories=Graphics;3DGraphics;\n"
        "StartupNotify=false\n"
    )
    # User applications menu
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    desktop_file = apps / "blenderai.desktop"
    desktop_file.write_text(content, encoding="utf-8")
    desktop_file.chmod(0o755)
    # Desktop copy
    desk = _desktop_dir() / "BlenderAI.desktop"
    try:
        desk.write_text(content, encoding="utf-8")
        desk.chmod(0o755)
    except Exception:
        pass
    # Mark trusted on some DEs
    try:
        subprocess.run(["gio", "set", str(desk), "metadata::trusted", "true"], check=False, capture_output=True)
    except Exception:
        pass


def current_platform_label() -> str:
    if os.name == "nt":
        return "Windows"
    if sys.platform == "darwin":
        return "macOS"
    if sys.platform.startswith("linux"):
        return "Linux"
    return sys.platform


def blender_filetypes_for_dialog() -> list[tuple[str, str]]:
    if os.name == "nt":
        return [("Blender", "blender.exe"), ("Executable", "*.exe"), ("All", "*.*")]
    if sys.platform == "darwin":
        return [("Blender", "Blender"), ("All", "*")]
    return [("Blender", "blender"), ("All", "*")]


def run_install(opts: InstallOptions, progress: ProgressCb | None = None) -> InstallResult:
    result = InstallResult(ok=False)
    try:
        _progress(progress, "Starting installation…", 0.05)
        zip_path = appdata_blenderai() / "cache" / "blender_ai_extension.zip"
        build_extension_zip(zip_path, progress)

        # Deterministic file install first, then enable in Blender preferences
        ext_path = install_extension_copy(opts.blender, progress)
        result.extension_path = ext_path
        result.messages.append(f"Extension installed → {ext_path}")

        enabled = False
        if opts.enable_extension:
            enabled = enable_extension(opts.blender, zip_path, progress)
            if enabled:
                result.messages.append("BlenderAI enabled in Blender preferences.")
            else:
                result.messages.append(
                    "Auto-enable failed. In Blender: Preferences → Get Extensions → enable BlenderAI."
                )

        if opts.install_sidecar:
            side = install_sidecar(progress)
            result.sidecar_path = side
            result.messages.append(f"Sidecar ready at {side}")
            if opts.build_webui:
                install_webui(build=True, progress=progress)
                result.messages.append("WebUI installed")
            if opts.create_shortcuts:
                create_shortcuts(side, progress)
                result.messages.append("Shortcuts created")
            if opts.install_mcp:
                mcp_targets = install_mcp_clients(side, progress)
                for label, mcp_path in mcp_targets:
                    result.messages.append(f"{label} MCP configured → {mcp_path}")
                result.messages.append(
                    "Restart Cursor / Claude Desktop / Claude Code / Windsurf / Cline to load blender-ai."
                )

        # Patch config so sidecar finds skills in APPDATA
        _write_sidecar_launcher_env()
        _progress(progress, "Done", 1.0)
        result.ok = True
        if enabled:
            result.messages.append("Restart Blender, then open N-Panel (N) → BlenderAI.")
        else:
            result.messages.append("Restart Blender after enabling BlenderAI.")
        return result
    except Exception as e:
        result.messages.append(str(e))
        result.ok = False
        return result


def _write_sidecar_launcher_env() -> None:
    """Ensure installed sidecar reads APPDATA install.json paths via env file."""
    data = appdata_blenderai()
    env_path = data / "sidecar" / ".env"
    cfg = data / "install.json"
    if not cfg.exists():
        return
    info = json.loads(cfg.read_text(encoding="utf-8"))
    lines = [
        f"BLENDERAI_SKILLS_DIR={info.get('skills_dir','')}",
        f"BLENDERAI_PRESETS_DIR={info.get('presets_dir','')}",
        f"BLENDERAI_WEBUI_DIST={info.get('webui_dist','')}",
    ]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
