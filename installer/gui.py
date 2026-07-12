"""BlenderAI beautiful graphical installer."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

# Allow running as script
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import customtkinter as ctk
except ImportError:
    print("Installing customtkinter…")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

from install_core import (
    InstallOptions,
    blender_filetypes_for_dialog,
    current_platform_label,
    discover_blenders,
    run_install,
)


# Brand palette — studio graphite + amber/copper
COLORS = {
    "bg0": "#12141a",
    "bg1": "#1a1d26",
    "bg2": "#232833",
    "text": "#e8e4dc",
    "muted": "#9a9488",
    "accent": "#d4a574",
    "accent2": "#b87333",
    "ok": "#6fbf8a",
    "err": "#e07a6a",
}


class InstallerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("BlenderAI Installer")
        self.geometry("760x640")
        self.minsize(680, 560)
        self.configure(fg_color=COLORS["bg0"])

        self.blenders = discover_blenders()
        self._busy = False

        self._build()

    def _build(self) -> None:
        # Footer FIRST (side=bottom) so actions are always visible
        foot = ctk.CTkFrame(self, fg_color=COLORS["bg1"], corner_radius=16, height=72)
        foot.pack(side="bottom", fill="x", padx=20, pady=(0, 16))
        foot.pack_propagate(False)

        foot_inner = ctk.CTkFrame(foot, fg_color="transparent")
        foot_inner.pack(fill="both", expand=True, padx=16, pady=8)

        self.install_btn = ctk.CTkButton(
            foot_inner,
            text="Install BlenderAI",
            command=self._start_install,
            fg_color=COLORS["accent2"],
            hover_color=COLORS["accent"],
            text_color="#1a120c",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=40,
            width=200,
        )
        self.install_btn.pack(side="right")

        self._installed = False

        # Hero
        hero = ctk.CTkFrame(self, fg_color=COLORS["bg1"], corner_radius=16)
        hero.pack(side="top", fill="x", padx=20, pady=(16, 10))

        top = ctk.CTkFrame(hero, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=14)

        mark = ctk.CTkFrame(top, width=44, height=44, corner_radius=12, fg_color=COLORS["accent"])
        mark.pack(side="left", padx=(0, 12))
        mark.pack_propagate(False)

        titles = ctk.CTkFrame(top, fg_color="transparent")
        titles.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            titles,
            text="BlenderAI",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=26),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            titles,
            text=f"Cross-platform installer · {current_platform_label()} · Blender 4.2+",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
            anchor="w",
        ).pack(anchor="w")

        # Scrollable middle content
        body = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg1"], corner_radius=16)
        body.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 12))

        ctk.CTkLabel(
            body,
            text="Blender version",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["accent"],
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 6))

        values = [b.label for b in self.blenders] or ["No Blender found — browse to select the executable"]
        self.blender_var = ctk.StringVar(value=values[0])
        self.blender_menu = ctk.CTkOptionMenu(
            body,
            values=values,
            variable=self.blender_var,
            fg_color=COLORS["bg2"],
            button_color=COLORS["accent2"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg2"],
            text_color=COLORS["text"],
            height=36,
        )
        self.blender_menu.pack(fill="x", padx=14, pady=(0, 8))

        browse_row = ctk.CTkFrame(body, fg_color="transparent")
        browse_row.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkButton(
            browse_row,
            text="Browse Blender…",
            command=self._browse_blender,
            fg_color=COLORS["bg2"],
            hover_color="#2c3240",
            text_color=COLORS["text"],
            width=150,
            height=34,
        ).pack(side="left")
        ctk.CTkButton(
            browse_row,
            text="Rescan",
            command=self._rescan,
            fg_color=COLORS["bg2"],
            hover_color="#2c3240",
            text_color=COLORS["text"],
            width=90,
            height=34,
        ).pack(side="left", padx=8)

        self.opt_sidecar = ctk.CTkCheckBox(
            body,
            text="Install Sidecar + Python dependencies",
            text_color=COLORS["text"],
            fg_color=COLORS["accent2"],
            hover_color=COLORS["accent"],
        )
        self.opt_sidecar.select()
        self.opt_sidecar.pack(anchor="w", padx=14, pady=3)

        self.opt_webui = ctk.CTkCheckBox(
            body,
            text="Build / copy WebUI",
            text_color=COLORS["text"],
            fg_color=COLORS["accent2"],
            hover_color=COLORS["accent"],
        )
        self.opt_webui.select()
        self.opt_webui.pack(anchor="w", padx=14, pady=3)

        self.opt_shortcuts = ctk.CTkCheckBox(
            body,
            text="Create desktop / app menu shortcut",
            text_color=COLORS["text"],
            fg_color=COLORS["accent2"],
            hover_color=COLORS["accent"],
        )
        self.opt_shortcuts.select()
        self.opt_shortcuts.pack(anchor="w", padx=14, pady=3)

        self.opt_mcp = ctk.CTkCheckBox(
            body,
            text="Configure Cursor MCP (blender-ai tools)",
            text_color=COLORS["text"],
            fg_color=COLORS["accent2"],
            hover_color=COLORS["accent"],
        )
        self.opt_mcp.select()
        self.opt_mcp.pack(anchor="w", padx=14, pady=3)

        self.opt_enable = ctk.CTkCheckBox(
            body,
            text="Enable BlenderAI in Blender (recommended)",
            text_color=COLORS["text"],
            fg_color=COLORS["accent2"],
            hover_color=COLORS["accent"],
        )
        self.opt_enable.select()
        self.opt_enable.pack(anchor="w", padx=14, pady=3)

        self.progress = ctk.CTkProgressBar(body, progress_color=COLORS["accent"], fg_color=COLORS["bg2"], height=8)
        self.progress.pack(fill="x", padx=14, pady=(14, 6))
        self.progress.set(0)

        self.status = ctk.CTkLabel(body, text="Ready to install", text_color=COLORS["muted"], anchor="w")
        self.status.pack(fill="x", padx=14, pady=(0, 6))

        self.log = ctk.CTkTextbox(body, height=90, fg_color=COLORS["bg0"], text_color=COLORS["text"])
        self.log.pack(fill="x", padx=14, pady=(0, 12))

    def _log(self, msg: str) -> None:
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def _set_install_button_idle(self) -> None:
        if self._installed:
            self.install_btn.configure(
                text="Close",
                command=self._close_installer,
                state="normal",
            )
        else:
            self.install_btn.configure(
                text="Install BlenderAI",
                command=self._start_install,
                state="normal",
            )

    def _close_installer(self) -> None:
        self.destroy()

    def _rescan(self) -> None:
        self.blenders = discover_blenders()
        values = [b.label for b in self.blenders] or ["No Blender found"]
        self.blender_menu.configure(values=values)
        self.blender_var.set(values[0])
        self._log(f"Found {len(self.blenders)} Blender install(s).")

    def _browse_blender(self) -> None:
        from tkinter import filedialog
        from install_core import BlenderInstall, _config_dir_for_version, _probe_version

        kwargs = {
            "title": "Select Blender executable",
            "filetypes": blender_filetypes_for_dialog(),
        }
        if sys.platform == "darwin":
            path = filedialog.askopenfilename(**kwargs)
            if path and path.endswith(".app"):
                path = str(Path(path) / "Contents" / "MacOS" / "Blender")
        else:
            path = filedialog.askopenfilename(**kwargs)
        if not path:
            return
        exe = Path(path)
        ver = _probe_version(exe) or "4.2"
        b = BlenderInstall(version=ver, blender_exe=exe, config_dir=_config_dir_for_version(ver))
        self.blenders = [b] + [x for x in self.blenders if x.blender_exe != exe]
        values = [x.label for x in self.blenders]
        self.blender_menu.configure(values=values)
        self.blender_var.set(values[0])

    def _selected_blender(self):
        label = self.blender_var.get()
        for b in self.blenders:
            if b.label == label:
                return b
        return self.blenders[0] if self.blenders else None

    def _on_progress(self, msg: str, pct: float) -> None:
        def ui():
            self.progress.set(max(0.0, min(1.0, pct)))
            self.status.configure(text=msg)
            self._log(msg)

        self.after(0, ui)

    def _start_install(self) -> None:
        if self._busy:
            return
        blender = self._selected_blender()
        if not blender:
            self.status.configure(text="Select a Blender install first", text_color=COLORS["err"])
            return
        self._busy = True
        self.install_btn.configure(state="disabled", text="Installing…")
        self.status.configure(text_color=COLORS["muted"])
        opts = InstallOptions(
            blender=blender,
            install_sidecar=bool(self.opt_sidecar.get()),
            build_webui=bool(self.opt_webui.get()),
            enable_extension=bool(self.opt_enable.get()),
            create_shortcuts=bool(self.opt_shortcuts.get()),
            install_mcp=bool(self.opt_mcp.get()),
        )

        def worker():
            result = run_install(opts, progress=self._on_progress)

            def done():
                self._busy = False
                for m in result.messages:
                    self._log(m)
                if result.ok:
                    self._installed = True
                    enabled = any("enabled in Blender preferences" in m for m in result.messages)
                    self.status.configure(
                        text=(
                            "Installed & enabled. Restart Blender → N-Panel → BlenderAI."
                            if enabled
                            else "Installed. Enable BlenderAI in Get Extensions, then restart."
                        ),
                        text_color=COLORS["ok"],
                    )
                    self.progress.set(1.0)
                else:
                    self.status.configure(text="Installation failed", text_color=COLORS["err"])
                self._set_install_button_idle()

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    app = InstallerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
