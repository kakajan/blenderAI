# Manifest schema 1.0.0 (cheat sheet)

From [developer.blender.org schema 1.0.0](https://developer.blender.org/docs/features/extensions/schema/1.0.0/).

## Minimal add-on

```toml
schema_version = "1.0.0"
id = "my_example_extension"
version = "1.0.0"
name = "My Example Extension"
tagline = "This is another extension"
maintainer = "Developer Name"
type = "add-on"
blender_version_min = "4.2.0"
license = ["SPDX:GPL-3.0-or-later"]
```

## Common optionals

```toml
website = "https://github.com/org/repo"
tags = ["User Interface", "3D View"]
copyright = ["2024-2026 Developer Name"]

[permissions]
network = "Connect to local sidecar on localhost"
files = "Read install paths and write temp captures"

wheels = ["./wheels/some-1.0.0-py3-none-any.whl"]

[build]
paths_exclude_pattern = [
  "__pycache__/",
  "/.git/",
  "/*.zip",
]
```

## Rules

- Every declared field must be non-empty.
- Permission reasons: one short sentence, no trailing `.`
- `tagline`: no trailing punctuation.
- Valid add-on tags include: `3D View`, `User Interface`, `Development`, `Mesh`, `Modeling`, …
- Do not hand-author `[build.generated]`.
