"""Execute multi-step workflow presets (skill + prompt per step)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator

from blender_ai_sidecar.chat.cancel import cancelled
from blender_ai_sidecar.providers.base import StreamEvent
from blender_ai_sidecar.skills.engine import SkillEngine


def _on_fail_continue(step: dict[str, Any]) -> bool:
    return str(step.get("on_fail") or "stop").strip().lower() in {"continue", "ignore", "skip"}


class WorkflowRunner:
    def __init__(self, agent: Any, skills: SkillEngine) -> None:
        self.agent = agent
        self.skills = skills

    def resolve_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Resolve by exact alias/id/name/stem, then path-style id, then fuzzy substring."""
        presets = self.skills.list_presets()
        wid = (workflow_id or "").strip()
        if not wid:
            return None

        candidates: list[dict[str, Any]] = []
        for preset in presets:
            steps = preset.get("steps")
            if not isinstance(steps, list) or not steps:
                continue
            candidates.append(preset)

        # 1) Exact match on alias / id / name / stem
        for preset in candidates:
            pid = str(preset.get("id") or "")
            alias = str(preset.get("alias") or "")
            name = str(preset.get("name") or "")
            if wid in {pid, alias, name, Path(pid).stem}:
                return preset

        # 2) Path-style: workflows/foo.yaml, foo.yaml, .../foo
        wid_norm = wid.replace("\\", "/")
        for preset in candidates:
            pid = str(preset.get("id") or "").replace("\\", "/")
            if (
                pid == wid_norm
                or pid.endswith(f"/{wid_norm}")
                or pid.endswith(f"/{wid_norm}.yaml")
                or pid.endswith(f"/{wid_norm}.yml")
                or Path(pid).name == wid_norm
                or Path(pid).name in {f"{wid_norm}.yaml", f"{wid_norm}.yml"}
            ):
                return preset

        # 3) Fuzzy substring (last resort) — prefer unique hit
        fuzzy: list[dict[str, Any]] = []
        for preset in candidates:
            pid = str(preset.get("id") or "")
            alias = str(preset.get("alias") or "")
            if wid in pid or (alias and wid in alias):
                fuzzy.append(preset)
        if len(fuzzy) == 1:
            return fuzzy[0]
        if fuzzy:
            return fuzzy[0]
        return None

    async def run_stream(
        self,
        *,
        workflow_id: str,
        user_message: str,
        provider_id: str,
        model: str | None = None,
        chat_id: str | None = None,
        scene_summary: dict[str, Any] | None = None,
        local_only: bool = False,
        image_base64: str | None = None,
        image_mime: str = "image/png",
        max_steps_per_stage: int | None = None,
        cancel: asyncio.Event | None = None,
    ) -> AsyncIterator[StreamEvent]:
        preset = self.resolve_workflow(workflow_id)
        if not preset:
            yield StreamEvent(type="error", content=f"Workflow not found or has no steps: {workflow_id}")
            yield StreamEvent(type="done")
            return

        steps = list(preset.get("steps") or [])
        total = len(steps)
        yield StreamEvent(
            type="status",
            content="workflow_started",
            data={
                "workflow_id": preset.get("id") or workflow_id,
                "name": preset.get("name"),
                "total_steps": total,
            },
        )

        current_chat = chat_id
        for idx, step in enumerate(steps):
            if cancelled(cancel):
                yield StreamEvent(type="status", content="stopped")
                yield StreamEvent(type="done", data={"chat_id": current_chat, "workflow_id": workflow_id, "stopped": True})
                return
            if not isinstance(step, dict):
                continue
            skill_id = step.get("skill") or None
            if skill_id and not self.skills.get(str(skill_id)):
                yield StreamEvent(
                    type="error",
                    content=f"Workflow step skill not found: {skill_id}",
                    data={"index": idx, "skill_id": skill_id},
                )
                yield StreamEvent(
                    type="done",
                    data={"chat_id": current_chat, "workflow_id": workflow_id, "failed": True},
                )
                return

            step_prompt = (step.get("prompt") or "").strip()
            combined = user_message.strip()
            if step_prompt:
                combined = f"{user_message.strip()}\n\n[Workflow step {idx + 1}/{total}]\n{step_prompt}".strip()
            allow_continue = _on_fail_continue(step)

            yield StreamEvent(
                type="status",
                content="workflow_step",
                data={
                    "index": idx,
                    "total": total,
                    "skill_id": skill_id,
                    "name": step.get("name") or skill_id or f"step_{idx + 1}",
                },
            )
            yield StreamEvent(
                type="token",
                content=f"\n\n— Step {idx + 1}/{total}"
                + (f" ({skill_id})" if skill_id else "")
                + " —\n",
            )

            # Only attach the user image on the first step.
            img = image_base64 if idx == 0 else None
            async for event in self.agent.run_stream(
                provider_id=provider_id,
                model=model,
                skill_id=skill_id,
                user_message=combined,
                chat_id=current_chat,
                scene_summary=scene_summary,
                local_only=local_only,
                max_steps=max_steps_per_stage,
                image_base64=img,
                image_mime=image_mime,
                critique_rounds=1 if skill_id and str(skill_id).startswith("review.") else 0,
                cancel=cancel,
            ):
                if cancelled(cancel):
                    yield StreamEvent(type="status", content="stopped")
                    yield StreamEvent(type="done", data={"chat_id": current_chat, "workflow_id": workflow_id, "stopped": True})
                    return
                if event.type == "status" and event.content == "chat_ready":
                    current_chat = (event.data or {}).get("chat_id") or current_chat
                    yield StreamEvent(
                        type="status",
                        content="chat_ready",
                        data={"chat_id": current_chat, "workflow_step": idx},
                    )
                    continue
                if event.type == "done":
                    # Suppress per-step done; emit one at the end.
                    continue

                # Fail-fast on agent error / tool failure unless step allows continue.
                if event.type == "error":
                    yield event
                    if not allow_continue:
                        yield StreamEvent(
                            type="status",
                            content="workflow_aborted",
                            data={"index": idx, "reason": "error", "skill_id": skill_id},
                        )
                        yield StreamEvent(
                            type="done",
                            data={"chat_id": current_chat, "workflow_id": workflow_id, "failed": True},
                        )
                        return
                    continue
                if event.type == "status" and event.content == "tool_result":
                    result = event.data or {}
                    if result.get("ok") is False:
                        yield event
                        if not allow_continue:
                            yield StreamEvent(
                                type="status",
                                content="workflow_aborted",
                                data={
                                    "index": idx,
                                    "reason": "tool_failure",
                                    "skill_id": skill_id,
                                    "error": result.get("error"),
                                },
                            )
                            yield StreamEvent(
                                type="done",
                                data={"chat_id": current_chat, "workflow_id": workflow_id, "failed": True},
                            )
                            return
                        continue

                yield event

        yield StreamEvent(
            type="status",
            content="workflow_finished",
            data={"workflow_id": preset.get("id") or workflow_id, "chat_id": current_chat},
        )
        yield StreamEvent(type="done", data={"chat_id": current_chat, "workflow_id": workflow_id})
