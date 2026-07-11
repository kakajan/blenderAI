# Skills

Skills live in `/skills/*.yaml` and reference system prompts under `/presets`.

فارسی: [skills.fa.md](skills.fa.md)

## Schema

```yaml
id: domain.action
version: 1
name: Human Name
domains: [modeling]
tools: [scene.create_object]
system_prompt: presets/path.md
risk: low|medium|high
requires_confirmation: false
viewport_capture: false|optional|required
description: Short description
```

## Adding a skill

1. Add YAML under `skills/`.
2. Add or reuse a preset markdown system prompt.
3. Restart the sidecar (or reload skills if exposed).
4. Ensure matching Blender tools are allowlisted in the extension.

## Sharing skills

Pack a small folder (YAML + preset) and open a PR — community skill packs are one of the best ways to grow BlenderAI.
