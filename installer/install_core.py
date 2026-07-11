"""BlenderAI installer — core install logic (no UI)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    if dest_zip.exists():
        dest_zip.unlink()
    _progress(progress, "Packaging Blender extension…", 0.15)
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in src.rglob("*"):
            if path.is_file():
                if "__pycache__" in path.parts or path.suffix == ".pyc":
                    continue
                zf.write(path, path.relative_to(src).as_posix())
    return dest_zip


def install_extension_copy(blender: BlenderInstall, progress: ProgressCb | None = None) -> Path:
    """Copy extension into user_default/blender_ai (reliable fallback)."""
    target_root = blender.extensions_user_default
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / "blender_ai"
    src = repo_root() / "extension"
    _progress(progress, f"Installing extension → {target}", 0.35)
    if target.exists():
        shutil.rmtree(target)
    # Extension folder must contain manifest + package
    target.mkdir(parents=True)
    shutil.copy2(src / "blender_manifest.toml", target / "blender_manifest.toml")
    shutil.copytree(src / "blender_ai", target / "blender_ai")
    # Write install marker with sidecar path
    marker = {
        "sidecar_dir": str(appdata_blenderai() / "sidecar"),
        "data_dir": str(appdata_blenderai()),
        "installed_by": "BlenderAI Installer",
    }
    (target / "blender_ai" / "install_info.json").write_text(json.dumps(marker, indent=2), encoding="utf-8")
    return target


def try_cli_install(blender: BlenderInstall, zip_path: Path, progress: ProgressCb | None = None) -> bool:
    _progress(progress, "Trying Blender CLI extension install…", 0.3)
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
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        return True
    except Exception:
        return False


def install_sidecar(progress: ProgressCb | None = None) -> Path:
    dest = appdata_blenderai() / "sidecar"
    src = repo_root() / "sidecar"
    _progress(progress, "Copying sidecar…", 0.5)
    if dest.exists():
        # keep venv if present
        venv = dest / ".venv"
        tmp_venv = appdata_blenderai() / "_venv_backup"
        if venv.exists():
            if tmp_venv.exists():
                shutil.rmtree(tmp_venv, ignore_errors=True)
            shutil.move(str(venv), str(tmp_venv))
        shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", "*.egg-info", ".pytest_cache"),
    )
    # restore venv
    tmp_venv = appdata_blenderai() / "_venv_backup"
    if tmp_venv.exists():
        shutil.move(str(tmp_venv), str(dest / ".venv"))

    # copy skills & presets next to data
    for name in ("skills", "presets"):
        s = repo_root() / name
        d = appdata_blenderai() / name
        if d.exists():
            shutil.rmtree(d)
        if s.exists():
            shutil.copytree(s, d)

    venv_py = _ensure_venv(dest, progress)
    _progress(progress, "Installing Python packages…", 0.65)
    subprocess.check_call([str(venv_py), "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"])
    subprocess.check_call([str(venv_py), "-m", "pip", "install", "-e", str(dest)])

    # Write env pointer for skills paths
    cfg = {
        "skills_dir": str(appdata_blenderai() / "skills"),
        "presets_dir": str(appdata_blenderai() / "presets"),
        "webui_dist": str(appdata_blenderai() / "webui" / "dist"),
        "host": "127.0.0.1",
        "port": 8765,
    }
    (appdata_blenderai() / "install.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
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
  <key>CFBundleVersion</key><string>1.0.0</string>
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

        cli_ok = False
        if opts.enable_extension:
            cli_ok = try_cli_install(opts.blender, zip_path, progress)
        # Always ensure copy install (CLI may place differently; copy is deterministic)
        ext_path = install_extension_copy(opts.blender, progress)
        result.extension_path = ext_path
        result.messages.append(
            "Extension installed via Blender CLI" if cli_ok else "Extension copied to user_default"
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

        # Patch config so sidecar finds skills in APPDATA
        _write_sidecar_launcher_env()
        _progress(progress, "Done", 1.0)
        result.ok = True
        result.messages.append("Restart Blender, then enable BlenderAI if needed.")
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
