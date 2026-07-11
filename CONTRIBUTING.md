# Contributing to BlenderAI

Thank you for considering a contribution. You don’t need to be an expert — clear issues, small PRs, and kind reviews all move the project forward.

| | |
|--|--|
| **Repository** | [github.com/kakajan/blenderAI](https://github.com/kakajan/blenderAI) |
| **Author** | [AsherQelich SayyedMuhammadi](https://github.com/kakajan) (`@kakajan`) |
| **Issues / PRs** | [Issues](https://github.com/kakajan/blenderAI/issues) · [Pull requests](https://github.com/kakajan/blenderAI/pulls) |

## Ways to help

| Area | Examples |
|------|----------|
| Skills | New YAML skills + presets for sculpt, nodes, rigging, VFX |
| Providers | Adapters, retries, better error messages, tests |
| WebUI | Accessibility, RTL polish, performance, design |
| Extension | Safer tools, better scene context, Blender version quirks |
| Docs | Tutorials, GIFs, translations, clarifying “gotchas” |
| Security | Allowlist review, MCP hardening, key handling |

## Development setup

1. Fork and clone the repo.
2. Follow the **Manual setup** section in [README.md](README.md).
3. Run sidecar tests:

```bash
cd sidecar
pip install -e ".[dev]"
pytest -q
```

4. For WebUI:

```bash
cd webui
npm install
npm run build
```

## Pull request checklist

- [ ] Describe **why** the change helps users or maintainers
- [ ] Keep the diff focused (one concern per PR when possible)
- [ ] Add/update tests for sidecar logic when you touch providers or skills
- [ ] Don’t commit secrets, `.env`, or personal API keys
- [ ] Match existing code style; prefer clarity over cleverness
- [ ] Update docs if behavior or setup steps change

## Code of conduct (short version)

Be respectful. Assume good intent. No harassment, spam, or hostile gatekeeping. We’re building tools for artists and TDs — keep the tone supportive.

## Security

If you find a vulnerability (especially around tool execution or MCP write access), please open a private security advisory or email the maintainers rather than posting a public exploit PoC.

## License

By contributing, you agree your work is licensed under the project’s [MIT License](LICENSE).

---

Questions? [Open an issue](https://github.com/kakajan/blenderAI/issues) with the `question` label, or reach [@kakajan](https://github.com/kakajan). We’re glad you’re here.
