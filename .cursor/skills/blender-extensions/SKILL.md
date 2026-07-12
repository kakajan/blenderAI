---
name: blender-extensions
description: >-
  Build, package, install, and enable Blender 4.2+ extensions (manifest, flat
  zip layout, CLI, Get Extensions / Add-ons). Use when editing blender_manifest.toml,
  packaging add-ons, Install from Disk, enable/disable failures, extension repos,
  or anything under extension/ that must load in Blender Preferences.
---

# Blender Extensions (4.2+)

Source of truth: [developer.blender.org/docs](https://developer.blender.org/docs/) · [Creating Extensions](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html) · [Add-on Dev Setup](https://developer.blender.org/docs/handbook/extensions/addon_dev_setup/)

## Hard rules

1. **Flat package root** — the installed folder / zip root MUST contain both:
   - `blender_manifest.toml`
   - `__init__.py`
2. **Do not nest** `addon_id/addon_id/__init__.py`. Nested packages show in Get Extensions but often **never appear in Add-ons** (no Enable checkbox).
3. Manifest is authoritative — remove or stop relying on legacy `bl_info`.
4. Prefer **Install from Disk** (or `blender --command extension install-file … --enable`) over raw folder copy when testing enable.

## Correct layout

```text
my_extension.zip
├─ blender_manifest.toml
├─ __init__.py
├─ preferences.py
└─ … (subpackages OK)
```

Optional: all files inside one folder inside the zip (VCS zip quirk) — still must have manifest + `__init__.py` as siblings.

## Manifest checklist

Required: `schema_version`, `id`, `version`, `name`, `tagline`, `maintainer`, `type` (`add-on`), `blender_version_min` (≥ `4.2.0`), `license` (SPDX, e.g. `SPDX:MIT`).

- `tagline`: ≤64 chars, **no trailing punctuation**
- Optional `[permissions]`: `network`, `files`, … — short reason, **no period**
- Optional `wheels = ["./wheels/…"]` for deps
- Omit empty optional fields entirely
- Never commit `[build.generated]`

See [manifest-schema.md](manifest-schema.md).

## Install / enable

| Goal | Where |
|------|--------|
| Install / update package | Preferences → **Get Extensions** → Install from Disk |
| Enable / disable | Preferences → **Add-ons** (checkbox) — not the Get Extensions ⋮ menu |
| N-Panel UI | 3D Viewport → `N` → category from `bl_category` |

CLI:

```bash
blender --command extension install-file -r user_default --enable path/to/addon.zip
blender --command extension validate path/to/addon.zip
blender --command extension build   # run from directory with blender_manifest.toml
```

Module key after install: `bl_ext.<repo>.<id>` (e.g. `bl_ext.user_default.blender_ai`).

## Dev workflow

1. Keep source outside Blender’s config tree.
2. Symlink into a **local** extensions repo (not inside Blender version folders if avoidable):
   - Windows: `mklink /d "…/repo/addon_id" "…/project/extension"`
   - Unix: `ln -s "…/project/extension" "…/repo/addon_id"`
3. Support **Reload Scripts** via `importlib.reload` pattern in `__init__.py` (see blender-addon-api skill).
4. Uninstall from Preferences can delete symlink targets on Windows — back up first.

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Listed in Get Extensions, missing in Add-ons | Nested layout / no root `__init__.py` |
| Enable does nothing | Check Blender System Console for register errors |
| Tools / network fail | Missing `[permissions]`, or `bpy.app.online_access` is False |
| Prefs not found | `bl_idname` not `__package__` |

## Docs

- Schema: https://developer.blender.org/docs/features/extensions/schema/1.0.0/
- Guidelines: https://developer.blender.org/docs/handbook/addons/guidelines/
- Manual add-ons: https://docs.blender.org/manual/en/latest/advanced/extensions/addons.html
