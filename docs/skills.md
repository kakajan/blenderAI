# Skills

Skills live in `/skills/*.yaml` (built-in) and can also be **user-defined**.

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

## Add a skill in the WebUI (recommended)

1. Open Chat UI → **Skills**.
2. Click **Add skill**.
3. Set name, tools, and system prompt.
4. Save — the skill appears under **Your skills** and in the Chat skill picker.

Custom skills are stored under your OS data folder:

| OS | Path |
|----|------|
| Windows | `%APPDATA%\BlenderAI\user_skills\` |
| macOS | `~/Library/Application Support/BlenderAI/user_skills/` |
| Linux | `~/.local/share/BlenderAI/user_skills/` |

Each skill is a YAML file plus `prompts/<id>.md`.

## Add a skill by dropping files

1. Create `user.my_skill.yaml` in the `user_skills` folder (schema above).
2. Put the system prompt in `user_skills/prompts/user.my_skill.md` (or set `system_prompt` / inline `prompt`).
3. In WebUI Skills, click **Reload** (or restart the Sidecar).

User skills may override a built-in skill with the same `id` when loaded from `user_skills`.

## Built-in skills (repo)

1. Add YAML under repo `skills/`.
2. Add or reuse a preset markdown system prompt under `presets/`.
3. Restart the sidecar.
4. Ensure matching Blender tools are allowlisted in the extension.

## Sharing skills

Pack a small folder (YAML + prompt) and open a PR — community skill packs are one of the best ways to grow BlenderAI.
