from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from blender_ai_sidecar.bridge import protocol as bridge
from blender_ai_sidecar.bridge.tool_args import normalize_tool_args
from blender_ai_sidecar.chat.cancel import cancelled
from blender_ai_sidecar.chat.modeling_strategy import format_strategy_for_prompt, plan_modeling_strategy
from blender_ai_sidecar.chat.skill_router import (
    infer_skill,
    is_surface_tool,
    primitive_guardrail_message,
)
from blender_ai_sidecar.context import (
    apply_capability_gate,
    build_context_bundle,
    image_refs_from_capture,
    read_image_b64,
)
from blender_ai_sidecar.contracts import ImageRef, ProviderCapabilities
from blender_ai_sidecar.learning.engine import LearningEngine
from blender_ai_sidecar.modeling.session_metrics import (
    count_modeling_methods,
    critique_refactor_hint,
)
from blender_ai_sidecar.orchestration import get_run_registry
from blender_ai_sidecar.orchestration.tool_protocol import parse_first_tool_call, parse_native_tool_calls
from blender_ai_sidecar.policy import get_policy_engine, resolve_skill_tools
from blender_ai_sidecar.providers.base import ChatMessage, ChatRequest, StreamEvent
from blender_ai_sidecar.providers.router import ProviderRouter
from blender_ai_sidecar.skills.engine import SkillEngine
from blender_ai_sidecar.store.db import Database
from blender_ai_sidecar.tools import get_registry

# Back-compat for tests / docs that still import TOOL_RE.
TOOL_RE = re.compile(
    r"```(?:json)?\s*(?:tool\s*)?(\{.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)

DEFAULT_MAX_STEPS = 32
HARD_MAX_STEPS = 96
MODELING_DOMAINS = {"modeling"}
HISTORY_LIMIT = 24


class ChatAgent:
    def __init__(self, db: Database, router: ProviderRouter, skills: SkillEngine) -> None:
        self.db = db
        self.router = router
        self.skills = skills
        self.learning = LearningEngine(db)

    def _resolve_max_steps(self, skill: dict[str, Any] | None, max_steps: int | None) -> int:
        if max_steps is not None and max_steps > 0:
            return min(int(max_steps), HARD_MAX_STEPS)
        if skill and skill.get("max_steps"):
            try:
                return min(int(skill["max_steps"]), HARD_MAX_STEPS)
            except (TypeError, ValueError):
                pass
        if skill:
            domains = set(skill.get("domains") or [])
            if domains & MODELING_DOMAINS or str(skill.get("id") or "").startswith("modeling."):
                return DEFAULT_MAX_STEPS
        return DEFAULT_MAX_STEPS

    async def run_stream(
        self,
        *,
        provider_id: str,
        model: str | None,
        skill_id: str | None,
        user_message: str,
        chat_id: str | None = None,
        scene_summary: dict[str, Any] | None = None,
        local_only: bool = False,
        max_steps: int | None = None,
        image_base64: str | None = None,
        image_mime: str = "image/png",
        critique_rounds: int | None = None,
        cancel: asyncio.Event | None = None,
        run_id: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        inferred = infer_skill(user_message, skill_id)
        if inferred and inferred != skill_id:
            skill_id = inferred

        skill = self.skills.get(skill_id) if skill_id else None
        # Inferred skill_id with missing definition → read/low-safe tools only (None path).
        connected = bool(bridge.get_scene_cache().get("connected"))
        allowed = resolve_skill_tools(skill)
        steps_budget = self._resolve_max_steps(skill, max_steps)

        try:
            autonomy = await self.db.get_setting("autonomy", "ask")
        except Exception:
            autonomy = "ask"

        modeling_strategy = plan_modeling_strategy(
            user_message,
            skill_id=skill_id,
            scene_summary=scene_summary,
            has_reference_image=bool(image_base64),
        )
        strategy_text = format_strategy_for_prompt(modeling_strategy)

        system_parts = [
            (skill or {}).get("system_prompt_text")
            or self.skills._load_prompt("presets/general/blender_assistant.md")
            or "You are BlenderAI."
        ]
        if scene_summary:
            system_parts.append("Scene summary:\n" + json.dumps(scene_summary, ensure_ascii=False)[:6000])
        else:
            system_parts.append("Scene summary: unavailable (no live Blender scene cache).")

        try:
            learnings = await self.learning.find_relevant(
                user_goal=user_message,
                skill_id=skill_id,
                limit=3,
            )
            learning_text = self.learning.format_learnings_for_prompt(learnings)
            if learning_text:
                system_parts.append(learning_text)
        except Exception:
            pass

        try:
            from blender_ai_sidecar.knowledge import format_for_prompt, retrieve

            chunks = retrieve(user_message, limit=3)
            knowledge_text = format_for_prompt(chunks)
            if knowledge_text:
                system_parts.append(knowledge_text)
        except Exception:
            pass

        system_parts.append(
            "Adaptive rules: prefer composing allowlisted tools "
            "(mesh.loft_profiles, curve.create, python.run, mesh.ops, modifiers); "
            "use blender.introspect (read-only) when unsure about Blender version/API; "
            "sandboxed python.run is allowed for complex procedural geometry "
            "(imports: bpy/bmesh/math/mathutils/random only — no os/files/network). "
            "Never invent freeform Python outside python.run. "
            "If a needed primitive is missing, say so and record a capability gap "
            "instead of claiming success."
        )

        if strategy_text:
            system_parts.append(strategy_text)

        if skill:
            system_parts.append(
                f"Active skill: {skill.get('id')}. Allowed tools ONLY: {', '.join(allowed)}. "
                "Do not call any other tool — the request will be rejected."
            )
        elif skill_id:
            system_parts.append(
                f"Auto-selected skill: {skill_id}. Use its modeling workflow (extrude/inset/bevel, not primitive stacking). "
                f"Allowed tools (safe fallback): {', '.join(allowed)}."
            )
        else:
            system_parts.append(f"Allowed tools: {', '.join(allowed)}.")

        system_parts.append(_tool_docs(allowed))
        if connected:
            system_parts.append("Bridge status: Blender is connected. Tools can run.")
        else:
            system_parts.append(
                "Bridge status: Blender is NOT connected. Tools will fail. Tell the user the N-Panel "
                "must show Bridge: connected (not only Sidecar: online). Enable the BlenderAI add-on, "
                "then wait a few seconds or click Start in the N-Panel. "
                "Do not pretend objects were added."
            )

        messages: list[ChatMessage] = [
            ChatMessage(role="system", content="\n\n".join(system_parts)),
        ]

        # Load prior chat turns for iterative art direction.
        if chat_id:
            try:
                prior = await self.db.list_messages(chat_id)
                for row in prior[-HISTORY_LIMIT:]:
                    role = row.get("role") or "user"
                    if role not in {"user", "assistant"}:
                        continue
                    content = (row.get("content") or "").strip()
                    if not content:
                        continue
                    messages.append(ChatMessage(role=role, content=content[:4000]))
            except Exception:
                pass

        # Auto viewport capture when skill requires it and no image provided.
        image_refs: list[ImageRef] = []
        mime = image_mime or "image/png"
        if image_base64:
            image_refs = [
                ImageRef(
                    id=str(uuid.uuid4()),
                    source="user",
                    mime=mime,
                    data_base64=image_base64,
                )
            ]
        elif skill and str(skill.get("viewport_capture") or "").lower() == "required" and connected:
            if cancelled(cancel):
                yield StreamEvent(type="status", content="stopped")
                yield StreamEvent(type="done", data={"chat_id": chat_id, "stopped": True})
                return
            cap = await bridge.request_tool("viewport.capture", {})
            if cap.get("ok"):
                image_refs = image_refs_from_capture(cap, chat_id=chat_id)
                if image_refs:
                    mime = image_refs[0].mime or "image/png"
                    yield StreamEvent(
                        type="status",
                        content="viewport_auto_captured",
                        data={"path": cap.get("path"), "views": [r.view for r in image_refs]},
                    )

        # Capability gate — strip/truncate images the model cannot use.
        caps = await self._resolve_capabilities(provider_id, model)
        bundle = build_context_bundle(
            scene_summary=scene_summary,
            images=image_refs,
            skill_id=skill_id,
            connected=connected,
            strategy=modeling_strategy.to_status_data() if modeling_strategy else None,
        )
        bundle, cap_warn = apply_capability_gate(bundle, caps)
        images: list[str] | None = [r.data_base64 for r in bundle.images if r.data_base64] or None
        if cap_warn:
            system_parts.append(cap_warn)
            messages[0] = ChatMessage(role="system", content="\n\n".join(system_parts))

        user_content = user_message
        if images:
            user_content = (
                (user_message or "").rstrip()
                + "\n\n[Viewport image attached — use it for visual critique and next modeling steps.]"
            )
        elif cap_warn:
            digest = "\n".join(bundle.text_enrichments).strip()
            if digest:
                user_content = (user_message or "").rstrip() + "\n\n" + digest
            else:
                user_content = (user_message or "").rstrip() + f"\n\n[{cap_warn}]"
        messages.append(
            ChatMessage(role="user", content=user_content, images=images, image_mime=mime)
        )

        now = datetime.now(timezone.utc).isoformat()
        if not chat_id:
            chat_id = str(uuid.uuid4())
            await self.db.create_chat(
                {
                    "id": chat_id,
                    "title": user_message[:60] or "Chat",
                    "provider_id": provider_id,
                    "model": model,
                    "skill_id": skill_id,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        await self.db.add_message(
            {
                "id": str(uuid.uuid4()),
                "chat_id": chat_id,
                "role": "user",
                "content": user_message,
                "created_at": now,
                "meta": {"has_image": bool(images)},
            }
        )
        yield StreamEvent(
            type="status",
            content="chat_ready",
            data={
                "chat_id": chat_id,
                "max_steps": steps_budget,
                "modeling_strategy": modeling_strategy.to_status_data() if modeling_strategy else None,
            },
        )

        assistant_text = ""
        last_tool_ok: dict[str, Any] | None = None
        tools_ok_count = 0
        primitive_streak = 0
        session_tools: list[dict[str, Any]] = []
        critique_done = 0
        if critique_rounds is None:
            sid = str((skill or {}).get("id") or "")
            if sid == "modeling.procedural":
                critique_rounds = 2
            elif sid.startswith("modeling.") or sid.startswith("review.iterate"):
                critique_rounds = 1
            else:
                critique_rounds = 0
        max_critique = max(0, int(critique_rounds))

        for step in range(steps_budget):
            if cancelled(cancel):
                break
            req = ChatRequest(messages=messages, model=model)
            chunk_text = ""
            stream_failed = False
            empty_model = False
            native_calls: list[dict[str, Any]] = []
            async for event in self.router.chat_stream(provider_id, req, local_only=local_only):
                if cancelled(cancel):
                    break
                if event.type == "token":
                    chunk_text += event.content
                    assistant_text += event.content
                    yield event
                elif event.type == "tool_call":
                    data = event.data if isinstance(event.data, dict) else {}
                    parsed = parse_native_tool_calls(data)
                    if not parsed:
                        # Single-call shape: content=name, data={args:…}
                        name = event.content or data.get("name") or data.get("tool")
                        if name:
                            parsed = parse_native_tool_calls(
                                {
                                    "tool_calls": [
                                        {
                                            "name": name,
                                            "args": data.get("args") or data.get("input") or {},
                                        }
                                    ]
                                }
                            )
                    native_calls.extend(parsed)
                    yield event
                elif event.type == "error":
                    err = (event.content or "Provider error").strip()
                    if err:
                        assistant_text = f"{assistant_text}\n{err}".strip() if assistant_text else err
                    yield event
                    stream_failed = True
                    break
                elif event.type == "status" and (event.content or "").startswith("empty_model_response"):
                    empty_model = True
                    yield event
                elif event.type == "done":
                    break
                else:
                    yield event

            if cancelled(cancel):
                break

            if stream_failed:
                if last_tool_ok is not None and not (chunk_text or "").strip():
                    summary = _summarize_tool_success(last_tool_ok)
                    if summary:
                        assistant_text = _strip_trailing_error(assistant_text, keep_tools=True)
                        assistant_text = (
                            f"{assistant_text}\n{summary}".strip() if assistant_text else summary
                        )
                        yield StreamEvent(type="token", content=summary)
                break

            if empty_model and not (chunk_text or "").strip():
                if last_tool_ok is not None:
                    summary = _summarize_tool_success(last_tool_ok)
                    if summary:
                        assistant_text = (
                            f"{assistant_text}\n{summary}".strip() if assistant_text else summary
                        )
                        yield StreamEvent(type="token", content=summary)
                    break
                err = "Model returned empty content. Retry or pick another model."
                assistant_text = err
                yield StreamEvent(type="error", content=err)
                break

            # Prefer native tool_calls from the stream; fall back to text fence parse.
            call = native_calls[0] if native_calls else parse_first_tool_call(chunk_text)
            if not call:
                # Optional mid-run critique after several successful modeling tools.
                if (
                    max_critique > 0
                    and critique_done < max_critique
                    and tools_ok_count >= 3
                    and connected
                    and skill
                    and str(skill.get("id") or "").startswith("modeling.")
                ):
                    critique_done += 1
                    cap_args: dict[str, Any] = {
                        "views": ["front", "side", "back"],
                        "shading": "MATERIAL",
                    }
                    if last_tool_ok and last_tool_ok.get("result", {}).get("name"):
                        cap_args["target"] = last_tool_ok["result"]["name"]
                    cap = await bridge.request_tool("viewport.capture", cap_args)
                    refs = image_refs_from_capture(cap, chat_id=chat_id) if cap.get("ok") else []
                    critique_images = [r.data_base64 for r in refs if r.data_base64]
                    if critique_images:
                        metrics = count_modeling_methods(session_tools)
                        refactor_hint = critique_refactor_hint(metrics)
                        view_labels = [r.view or "view" for r in refs]
                        critique_content = (
                            "Critique this model from the captured turnaround view(s) against the user's request. "
                            f"Attached views: {', '.join(view_labels)}. "
                            "Check FRONT (face, eyes, belly), SIDE (silhouette, wing, tail placement), "
                            "BACK (crest, tail tufts). Score each view 1-5. "
                        )
                        if refactor_hint:
                            critique_content += refactor_hint + " "
                        critique_content += (
                            "Then emit the NEXT tool block to fix the weakest issue, "
                            "or a short final summary if done."
                        )
                        yield StreamEvent(
                            type="status",
                            content="critique_round",
                            data={"round": critique_done, "views": cap.get("views") or view_labels},
                        )
                        messages.append(ChatMessage(role="assistant", content=chunk_text or "(no tool)"))
                        messages.append(
                            ChatMessage(
                                role="user",
                                content=critique_content,
                                images=critique_images,
                                image_mime="image/png",
                            )
                        )
                        continue
                break
            tool = call.get("tool")
            args = call.get("args") or {}
            if not tool:
                break
            if cancelled(cancel):
                break
            try:
                args = normalize_tool_args(tool, args)
            except ValueError as exc:
                result = {"ok": False, "error": str(exc)}
                yield StreamEvent(type="status", content="tool_result", data=result)
                messages.append(ChatMessage(role="assistant", content=chunk_text))
                follow = (
                    f"Tool result:\n{json.dumps(result, ensure_ascii=False)}\n\n"
                    "The tool args were invalid. Fix the coordinates/indices and retry, "
                    "or explain the validation error to the user. "
                    "Do NOT claim the scene change succeeded."
                )
                messages.append(ChatMessage(role="user", content=follow))
                assistant_text += f"\n[tool:{tool}]"
                continue

            decision = get_policy_engine().decide(
                tool=tool,
                skill=skill,
                autonomy=autonomy,
                path="chat",
                confirmed=False,
                blender_connected=connected,
            )
            if decision.action == "deny":
                err = decision.reason or f"Tool denied: {tool}"
                result = {"ok": False, "error": err}
                yield StreamEvent(type="error", content=err)
                yield StreamEvent(type="status", content="tool_result", data=result)
                messages.append(ChatMessage(role="assistant", content=chunk_text or f"[tool:{tool}]"))
                messages.append(
                    ChatMessage(
                        role="user",
                        content=(
                            f"Tool result:\n{json.dumps(result, ensure_ascii=False)}\n\n"
                            "Pick an allowed tool for this skill/autonomy, or explain the denial to the user. "
                            "Do NOT claim the scene change succeeded."
                        ),
                    )
                )
                assistant_text += f"\n[tool:{tool}]"
                continue
            if decision.action == "confirm":
                registry = get_run_registry()
                handle = await registry.get(run_id) if run_id else None
                if handle is None and run_id:
                    handle = await registry.create(chat_id=chat_id, meta={"kind": "confirm"})
                    run_id = handle.run_id
                if handle is not None:
                    handle.pending_confirm = {
                        "tool": tool,
                        "args": args,
                        "reason": decision.reason,
                        "risk": decision.risk,
                    }
                    handle.confirm_event = asyncio.Event()
                    handle.confirm_approved = False
                    handle.set_state("confirm_wait")
                    yield StreamEvent(
                        type="status",
                        content="confirm_request",
                        data={
                            "run_id": handle.run_id,
                            "tool": tool,
                            "args": args,
                            "reason": decision.reason,
                            "risk": decision.risk,
                        },
                    )
                    # Wait until user confirms/denies or cancel/timeout.
                    try:
                        await asyncio.wait_for(handle.confirm_event.wait(), timeout=300.0)
                    except asyncio.TimeoutError:
                        result = {"ok": False, "error": "Confirmation timed out", "error_code": "confirm_timeout"}
                        yield StreamEvent(type="status", content="tool_result", data=result)
                        messages.append(ChatMessage(role="assistant", content=chunk_text or f"[tool:{tool}]"))
                        messages.append(
                            ChatMessage(
                                role="user",
                                content=(
                                    f"Tool result:\n{json.dumps(result, ensure_ascii=False)}\n\n"
                                    "Confirmation timed out. Continue without that tool or ask the user again."
                                ),
                            )
                        )
                        assistant_text += f"\n[tool:{tool}:timeout]"
                        continue
                    if cancelled(cancel) or not handle.confirm_approved:
                        result = {
                            "ok": False,
                            "error": "User denied confirmation",
                            "error_code": "confirm_denied",
                        }
                        yield StreamEvent(type="status", content="tool_result", data=result)
                        messages.append(ChatMessage(role="assistant", content=chunk_text or f"[tool:{tool}]"))
                        messages.append(
                            ChatMessage(
                                role="user",
                                content=(
                                    f"Tool result:\n{json.dumps(result, ensure_ascii=False)}\n\n"
                                    "User denied the risky tool. Pick a safer approach or stop."
                                ),
                            )
                        )
                        assistant_text += f"\n[tool:{tool}:denied]"
                        continue
                    # Approved — fall through to execute.
                else:
                    # No run handle available: keep previous non-blocking behavior.
                    yield StreamEvent(
                        type="status",
                        content="confirm_request",
                        data={
                            "tool": tool,
                            "args": args,
                            "reason": decision.reason,
                            "risk": decision.risk,
                        },
                    )
                    messages.append(ChatMessage(role="assistant", content=chunk_text or f"[tool:{tool}]"))
                    messages.append(
                        ChatMessage(
                            role="user",
                            content=(
                                f"Tool `{tool}` requires user confirmation before it can run "
                                f"(reason: {decision.reason}; risk: {decision.risk}). "
                                "It was NOT executed. Ask the user to confirm, or pick a safer allowed tool."
                            ),
                        )
                    )
                    assistant_text += f"\n[tool:{tool}:confirm]"
                    continue

            yield StreamEvent(type="tool_call", content=tool, data={"args": args, "run_id": run_id})
            result = await bridge.request_tool(tool, args)
            yield StreamEvent(type="status", content="tool_result", data=result)
            messages.append(ChatMessage(role="assistant", content=chunk_text))
            try:
                await self.learning.record_tool_run(
                    chat_id=chat_id,
                    skill_id=skill_id,
                    tool=str(tool),
                    args=args,
                    result=result,
                    step=step,
                    user_goal=user_message,
                )
            except Exception:
                pass
            result_json = json.dumps(result, ensure_ascii=False)[:3000]
            follow = f"Tool result:\n{result_json}"
            if result.get("ok"):
                last_tool_ok = {"tool": tool, "args": args, "result": result}
                tools_ok_count += 1
                session_tools.append({"tool": tool, "args": args})
                if tool == "scene.create_object":
                    primitive_streak += 1
                elif is_surface_tool(tool):
                    primitive_streak = 0
                remaining = steps_budget - step - 1
                follow += (
                    "\n\nIf the user's request is not fully complete yet, emit the NEXT tool block now "
                    "(mesh edits, modifiers, more parts, materials, lights, camera). "
                    "Only reply with a short final summary (no tool block) when the object is done. "
                    f"Steps remaining this turn: {remaining}."
                )
                if primitive_streak >= 3:
                    follow += "\n\n" + primitive_guardrail_message(primitive_streak)
                    primitive_streak = 0
            else:
                last_tool_ok = None
                follow += (
                    "\n\nThe tool failed. Tell the user what went wrong. "
                    "You may retry with a different tool/args, or explain the failure. "
                    "Do NOT claim the scene change succeeded."
                )
            messages.append(ChatMessage(role="user", content=follow))
            assistant_text += f"\n[tool:{tool}]"

        if last_tool_ok is not None and not _visible_reply(assistant_text):
            summary = _summarize_tool_success(last_tool_ok)
            if summary:
                assistant_text = summary
                yield StreamEvent(type="token", content=summary)

        stopped = cancelled(cancel)
        if stopped and not (assistant_text or "").strip():
            assistant_text = "[Stopped]"

        if not stopped and not (assistant_text or "").strip():
            assistant_text = (
                "No response from the model. If this keeps happening, make sure only one "
                "BlenderAI sidecar is running on port 8765, then retry."
            )
            yield StreamEvent(type="error", content=assistant_text)
        elif stopped:
            yield StreamEvent(type="status", content="stopped")

        await self.db.add_message(
            {
                "id": str(uuid.uuid4()),
                "chat_id": chat_id,
                "role": "assistant",
                "content": assistant_text,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta": {
                    "tools_used": session_tools[-24:],
                    "tools_ok_count": tools_ok_count,
                    "skill_id": skill_id,
                },
            }
        )

        # Never auto-write positive session_learnings; feedback is user-driven only.
        yield StreamEvent(type="done", data={"chat_id": chat_id, "stopped": stopped})

    async def _resolve_capabilities(self, provider_id: str, model: str | None) -> ProviderCapabilities:
        caps_fn = getattr(self.router, "capabilities", None)
        if callable(caps_fn):
            try:
                maybe = caps_fn(provider_id, model)
                if asyncio.iscoroutine(maybe):
                    maybe = await maybe
                if isinstance(maybe, ProviderCapabilities):
                    return maybe
            except Exception:
                pass
        return _caps_for(provider_id, model)


def _caps_for(provider_id: str, model: str | None) -> ProviderCapabilities:
    """Local fallback when ProviderRouter.capabilities is not available yet."""
    pid = (provider_id or "").lower()
    mid = (model or "").lower()
    vision_names = (
        "llava",
        "vision",
        "bakllava",
        "moondream",
        "minicpm",
        "qwen2-vl",
        "qwen2.5-vl",
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-4.1",
        "gpt-5",
        "claude",
        "gemini",
    )
    if pid in {"anthropic"} or "claude" in mid:
        return ProviderCapabilities(vision=True, max_images=8, tool_calling="regex")
    if pid in {"openai", "openai_compatible", "openrouter"} or mid.startswith("gpt-"):
        return ProviderCapabilities(vision=True, max_images=8, tool_calling="regex")
    if pid in {"ollama"} or "ollama" in pid:
        vision = any(x in mid for x in vision_names)
        return ProviderCapabilities(
            vision=vision,
            max_images=4 if vision else 0,
            tool_calling="regex",
        )
    vision = any(x in mid for x in vision_names)
    return ProviderCapabilities(vision=vision, max_images=4 if vision else 0, tool_calling="regex")


def _tool_docs(allowed: list[str] | None = None) -> str:
    return get_registry().docs_for(allowed)


def _read_image_b64(path: str) -> str | None:
    """Thin wrapper — prefer context.read_image_b64; kept for tests."""
    return read_image_b64(path)


def _visible_reply(text: str) -> bool:
    cleaned = TOOL_RE.sub("", text or "")
    cleaned = re.sub(r"\[tool:[^\]]+\]", "", cleaned)
    return bool(cleaned.strip())


def _strip_trailing_error(text: str, *, keep_tools: bool = True) -> str:
    lines = (text or "").splitlines()
    while lines and lines[-1].strip().lower().startswith(
        ("model returned", "provider error", "all providers failed", '{"error"')
    ):
        lines.pop()
    out = "\n".join(lines).strip()
    if keep_tools:
        return out
    return re.sub(r"\[tool:[^\]]+\]", "", out).strip()


def _summarize_tool_success(info: dict[str, Any]) -> str:
    tool = str(info.get("tool") or "")
    args = info.get("args") or {}
    result = info.get("result") or {}
    name = (
        args.get("object")
        or args.get("name")
        or result.get("name")
        or (result.get("data") or {}).get("name")
        or ""
    )
    obj_type = args.get("type") or (result.get("data") or {}).get("type") or ""
    if tool == "scene.create_object":
        label = name or obj_type or "object"
        kind = obj_type.replace("_", " ") if obj_type else "object"
        if name and obj_type:
            return f"Created {name} ({kind})."
        return f"Created {label}."
    if tool == "mesh.from_data":
        parts = result.get("parts") or []
        part_count = len(parts)
        total_verts = result.get("total_verts") or sum(p.get("verts", 0) for p in parts)
        root = result.get("name") or name or "mesh"
        return f"Built low-poly {root} ({part_count} parts, {total_verts} verts)."
    if tool == "mesh.ops":
        op = args.get("op") or result.get("op") or "edit"
        return f"Applied {op} on {name or 'mesh'}."
    if tool == "mesh.select":
        return f"Selected {result.get('selected', '')} on {name or 'mesh'}."
    if tool == "modifier.add":
        mod = result.get("modifier") or args.get("type") or "modifier"
        return f"Added {mod} to {name or 'object'}."
    if tool == "object.transform":
        return f"Transformed {name or 'object'}."
    if tool == "object.join":
        return f"Joined into {result.get('name') or name or 'object'}."
    if tool == "viewport.capture":
        return "Captured viewport."
    if name:
        return f"Done — {tool} on {name}."
    return f"Done — {tool} succeeded."
