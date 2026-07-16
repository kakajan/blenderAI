from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Reuse signal patterns from skill_router where useful.
from blender_ai_sidecar.chat.skill_router import (
    _BLOCKOUT_RE,
    _CHARACTER_RE,
    _DETAIL_RE,
    _HARDSURFACE_RE,
    _LOWPOLY_RE,
    _PRIMITIVES_RE,
)

_SCULPT_RE = re.compile(
    r"\b(sculpt|sculpting|organic|نرم|اسکالپت|ارگانیک)\b",
    re.IGNORECASE,
)
_BRIDGE_RE = re.compile(
    r"\b(bridge|loft|spin|revolve|لوله|پل|\bspin\b)\b",
    re.IGNORECASE,
)
_REFERENCE_RE = re.compile(
    r"\b(reference|turnaround|ref\s*sheet|multi[\s-]?view|مرجع|نما|از\s*روی\s*عکس)\b",
    re.IGNORECASE,
)
_PROP_RE = re.compile(
    r"\b(prop|furniture|chair|table|vehicle|weapon|tool|وسیله|مبل|صندلی)\b",
    re.IGNORECASE,
)
_COMPLEX_OBJECT_RE = re.compile(
    r"\b("
    r"boat|ship|yacht|canoe|kayak|rowboat|sailboat|"
    r"car|truck|vehicle|airplane|aircraft|helicopter|"
    r"spaceship|spacecraft|starship|rocket|ufo|mecha|mech|"
    r"robot|android|cyborg|drone|"
    r"house|building|castle|palace|bridge|furniture|"
    r"mountain|hill|cliff|rockscape|terrain|"
    r"tree|forest|pine|oak|palm|willow|"
    r"guitar|violin|piano|weapon|sword|"
    r"قایق|کشتی|قایقرانی|قایق\s*پارویی|بادبانی|"
    r"ماشین|خودرو|کامیون|هواپیما|هلیکوپتر|"
    r"سفینه|فضاپیما|موشک|یو\s*اف\s*او|"
    r"ربات|روبوت|آندروید|پهپاد|مکا|"
    r"خانه|ساختمان|قلعه|قصر|پل|مبلمان|"
    r"کوه|تپه|صخره|"
    r"درخت|جنگل|کاج|نخل|"
    r"گیتار|ویولن|پیانو|شمشیر|سلاح"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class StrategyPhase:
    name: str
    goal: str
    tools: list[str]
    hints: list[str] = field(default_factory=list)


@dataclass
class ModelingStrategy:
    id: str
    title: str
    rationale: str
    phases: list[StrategyPhase]
    transitions: list[str]
    anti_patterns: list[str]

    def to_prompt_block(self) -> str:
        lines = [
            "## Modeling Strategy (execute this plan — combine methods as listed)",
            "",
            f"**Approach:** {self.title}",
            f"**Why:** {self.rationale}",
            "",
        ]
        for i, phase in enumerate(self.phases, 1):
            lines.append(f"### Phase {i} — {phase.name}")
            lines.append(f"- **Goal:** {phase.goal}")
            lines.append(f"- **Tools:** {', '.join(phase.tools)}")
            for hint in phase.hints:
                lines.append(f"- {hint}")
            lines.append("")
        if self.transitions:
            lines.append("### Phase transitions")
            for rule in self.transitions:
                lines.append(f"- {rule}")
            lines.append("")
        if self.anti_patterns:
            lines.append("### Avoid")
            for item in self.anti_patterns:
                lines.append(f"- {item}")
        return "\n".join(lines).strip()

    def to_status_data(self) -> dict[str, Any]:
        return {
            "strategy_id": self.id,
            "title": self.title,
            "phases": [p.name for p in self.phases],
            "rationale": self.rationale,
        }


def _strategy_hybrid_blockout_surface() -> ModelingStrategy:
    return ModelingStrategy(
        id="hybrid_blockout_surface",
        title="Hybrid: Blockout primitives → Surface edit → Modifiers → Features",
        rationale="Detailed object — start with 1–3 primitives for massing, then extrude/inset/bevel for real form.",
        phases=[
            StrategyPhase(
                name="Blockout",
                goal="Establish scale and silhouette with 1–3 named primitives.",
                tools=["scene.create_object", "object.transform", "collection.organize"],
                hints=["Max 2–3 primitives total for the main form.", "Use dimensions for non-uniform shapes."],
            ),
            StrategyPhase(
                name="Surface edit",
                goal="Shape the base with extrude, inset, bevel, edge loops.",
                tools=["mesh.extrude", "mesh.ops", "mesh.select", "mesh.edge_loop"],
                hints=[
                    "Required before adding more primitives.",
                    "Use top_cap/by_normal selectors for head, belly, rim.",
                ],
            ),
            StrategyPhase(
                name="Modifiers",
                goal="Non-destructive smoothing and symmetry.",
                tools=["modifier.add", "modifier.apply"],
                hints=["SUBSURF for organic; BEVEL for edges; MIRROR for symmetric characters."],
            ),
            StrategyPhase(
                name="Feature meshes",
                goal="Flush details — beak, eyes, patches, small appendages.",
                tools=["mesh.from_data", "mesh.profile_extrude", "object.parent"],
                hints=["Features sit ON the surface — not floating spheres."],
            ),
            StrategyPhase(
                name="Finish",
                goal="Materials, lighting, multi-view verify.",
                tools=["material.create", "material.assign", "viewport.capture", "viewport.set_shading"],
                hints=["Capture front + side + back before claiming done."],
            ),
        ],
        transitions=[
            "After blockout: next tool MUST be mesh.extrude or mesh.ops — no more base primitives.",
            "After surface edit: add modifiers before scattering more loose parts.",
            "Join or parent parts before materials when they form one character.",
        ],
        anti_patterns=[
            "10+ loose primitives without extrude/inset",
            "Stopping after blockout when user asked for detail",
        ],
    )


def _strategy_hybrid_sculpt_surface() -> ModelingStrategy:
    return ModelingStrategy(
        id="hybrid_sculpt_surface",
        title="Hybrid: Box modeling → SUBSURF → Sculpt pass → Mesh polish",
        rationale="Soft organic character — box form first, smooth with SUBSURF, optional sculpt remesh, then hard-edge polish.",
        phases=[
            StrategyPhase(
                name="Box base",
                goal="Single integrated body/head volume from cube + extrude.",
                tools=["scene.create_object", "mesh.extrude", "mesh.ops"],
                hints=["One pear-shaped body — do not stack equal spheres."],
            ),
            StrategyPhase(
                name="Smooth",
                goal="SUBSURF for readable organic silhouette.",
                tools=["modifier.add"],
                hints=["levels 2 for stylized; keep base topology simple."],
            ),
            StrategyPhase(
                name="Sculpt pass",
                goal="Optional voxel remesh / inflate for organic variation.",
                tools=["sculpt.remesh", "sculpt.set_brush"],
                hints=["Use only if silhouette still too boxy; then return to mesh edit for features."],
            ),
            StrategyPhase(
                name="Mesh polish",
                goal="Hard features after sculpt — beak, eyes, inset patches.",
                tools=["mesh.ops", "mesh.from_data", "mesh.profile_extrude"],
                hints=["Sculpt shapes volume; mesh edit places flush eyes/beak/patches."],
            ),
            StrategyPhase(
                name="Character finish",
                goal="Fur, glossy eyes, materials, 3-view verify.",
                tools=["particle.fur_set", "material.create", "viewport.capture"],
                hints=["particle.fur_set preset soft — not long spikes."],
            ),
        ],
        transitions=[
            "Do sculpt only after SUBSURF base exists.",
            "After sculpt.remesh, use mesh.ops/mesh.from_data for small features — not more primitives.",
        ],
        anti_patterns=[
            "Sculpting from 20 separate spheres",
            "Skipping mesh polish after sculpt",
        ],
    )


def _strategy_hardsurface_boolean() -> ModelingStrategy:
    return ModelingStrategy(
        id="hardsurface_boolean",
        title="Hard-surface: Blockout → Edge flow → Boolean → Bevel",
        rationale="Mechanical or prop with sharp edges — support loops, booleans, bevel modifiers.",
        phases=[
            StrategyPhase(
                name="Blockout",
                goal="Named primitive massing at real scale.",
                tools=["scene.create_object", "object.transform"],
                hints=["Readable from front/side/top."],
            ),
            StrategyPhase(
                name="Edge flow",
                goal="Extrude, inset, loop_cut, crease, bevel_weight.",
                tools=["mesh.ops", "mesh.extrude", "mesh.edge_loop", "mesh.select"],
                hints=["Support loops before SUBSURF on curved hard-surface."],
            ),
            StrategyPhase(
                name="Boolean cuts",
                goal="Holes, panels, vents via cutter objects.",
                tools=["scene.create_object", "modifier.add"],
                hints=["BOOLEAN DIFFERENCE/UNION; name cutters clearly."],
            ),
            StrategyPhase(
                name="Bevel & UV",
                goal="Edge highlights and unwrap.",
                tools=["modifier.add", "uv.unwrap", "material.create"],
                hints=["BEVEL modifier non-destructive until stable."],
            ),
        ],
        transitions=[
            "Complete edge flow on main body before boolean cutters.",
            "Apply or keep booleans before final bevel pass.",
        ],
        anti_patterns=["SUBSURF without support loops on sharp props"],
    )


def _strategy_low_poly_direct() -> ModelingStrategy:
    return ModelingStrategy(
        id="low_poly_direct",
        title="Low-poly: mesh.from_data one-shot → flat materials",
        rationale="Game/stylized asset — explicit coordinates, no primitive chains.",
        phases=[
            StrategyPhase(
                name="Coordinate mesh",
                goal="All parts in one mesh.from_data call.",
                tools=["mesh.from_data"],
                hints=["20–80 verts per part; flat_shade true."],
            ),
            StrategyPhase(
                name="Materials",
                goal="2–3 bold flat colors.",
                tools=["material.create", "material.assign", "object.parent"],
                hints=["Do not fall back to scene.create_object."],
            ),
        ],
        transitions=["Do not use mesh.ops or primitives unless user changes request."],
        anti_patterns=["Primitive-by-primitive chains for low-poly"],
    )


def _strategy_reference_turnaround() -> ModelingStrategy:
    return ModelingStrategy(
        id="reference_turnaround",
        title="Reference match: Surface build → 3-view critique → Fix → Finish",
        rationale="Reference image or turnaround — build with surface methods, verify each view.",
        phases=[
            StrategyPhase(
                name="Surface build",
                goal="Box/profile modeling matching reference proportions.",
                tools=["scene.create_object", "mesh.extrude", "mesh.profile_extrude", "mesh.from_data", "modifier.add"],
                hints=["Check FRONT proportions first, then SIDE silhouette, then BACK."],
            ),
            StrategyPhase(
                name="Turnaround capture",
                goal="viewport.capture front/side/back.",
                tools=["viewport.capture"],
                hints=["Score each view 1–5 vs reference before finishing."],
            ),
            StrategyPhase(
                name="Iterative fix",
                goal="Fix weakest view with mesh edit or transform.",
                tools=["mesh.ops", "mesh.extrude", "object.transform"],
                hints=["Re-capture after each major fix."],
            ),
            StrategyPhase(
                name="Stylized finish",
                goal="Materials, fur, eyes, shading.",
                tools=["material.create", "particle.fur_set", "viewport.set_shading"],
                hints=[],
            ),
        ],
        transitions=[
            "Never claim reference match without 3-view capture.",
            "Fix silhouette before surface materials.",
        ],
        anti_patterns=["Building without comparing to reference views"],
    )


def _strategy_bridge_loft() -> ModelingStrategy:
    return ModelingStrategy(
        id="bridge_loft",
        title="Profile/loft: Base profile → Spin/bridge → Thicken → Bevel",
        rationale="Revolved or lofted forms — vases, horns, pipes, curved blades.",
        phases=[
            StrategyPhase(
                name="Profile base",
                goal="Plane or circle as profile source.",
                tools=["scene.create_object", "mesh.select"],
                hints=["Select boundary or cap faces for spin/bridge."],
            ),
            StrategyPhase(
                name="Loft/spin",
                goal="mesh.ops spin or bridge between edge loops.",
                tools=["mesh.ops"],
                hints=["spin for radial; bridge for between two loops."],
            ),
            StrategyPhase(
                name="Thickness",
                goal="solidify or modifier SOLIDIFY.",
                tools=["mesh.ops", "modifier.add"],
                hints=["solidify op or SOLIDIFY modifier."],
            ),
            StrategyPhase(
                name="Edge finish",
                goal="bevel + shade smooth.",
                tools=["mesh.ops", "material.create"],
                hints=[],
            ),
        ],
        transitions=["Complete spin/bridge before solidify."],
        anti_patterns=["Stacking cylinders when one spin suffices"],
    )


def _strategy_procedural_construction() -> ModelingStrategy:
    return ModelingStrategy(
        id="procedural_construction",
        title="Procedural: Part plan → Skeleton → Loft/Script form → Details → Materials → Verify",
        rationale=(
            "Complex real-world object — build part-by-part with loft, curves, "
            "and sandboxed python.run; never a single deformed box."
        ),
        phases=[
            StrategyPhase(
                name="Part plan",
                goal="Brief real-world part list before any geometry.",
                tools=["scene.summary", "asset.list"],
                hints=[
                    "Name every planned part (keel, ribs, planks, gunwale…).",
                    "Check asset.list for reusable hardware before reinventing.",
                ],
            ),
            StrategyPhase(
                name="Skeleton",
                goal="Primary guides — keel/stem curves or guide empties at real scale.",
                tools=["curve.create", "scene.create_object", "object.transform", "collection.organize"],
                hints=["Establish length/beam/height early with named objects."],
            ),
            StrategyPhase(
                name="Primary form",
                goal="Hull/body via mesh.loft_profiles or python.run plank/rib arrays.",
                tools=["mesh.loft_profiles", "python.run", "mesh.profile_extrude", "modifier.add"],
                hints=[
                    "Prefer loft for continuous shells; python.run for many curved planks.",
                    "Do not fake the whole object with one cube.",
                ],
            ),
            StrategyPhase(
                name="Details & joinery",
                goal="Secondary structure, hardware, imported assets, parenting.",
                tools=["python.run", "curve.create", "asset.import", "object.parent", "mesh.from_data", "mesh.ops"],
                hints=["Parent parts under a root Empty; keep names consistent."],
            ),
            StrategyPhase(
                name="Materials & verify",
                goal="Believable materials + front/side/back capture and fixes.",
                tools=["material.create", "material.assign", "viewport.capture", "viewport.set_shading"],
                hints=["Score each view; fix weakest silhouette before finishing."],
            ),
        ],
        transitions=[
            "Emit a short part list before the first create/loft/python tool.",
            "Primary form must use loft or python.run — not only primitives.",
            "Never claim done without multi-view viewport.capture.",
        ],
        anti_patterns=[
            "One cube → bevel → claim boat/vehicle/building",
            "Hollowed box as a complete hull",
            "10+ loose primitives without loft/script",
        ],
    )


def _strategy_primitives_only() -> ModelingStrategy:
    return ModelingStrategy(
        id="primitives_only",
        title="Primitives only",
        rationale="User asked for simple placement only.",
        phases=[
            StrategyPhase(
                name="Place primitives",
                goal="scene.create_object only.",
                tools=["scene.create_object"],
                hints=["One tool per primitive; no mesh edits."],
            ),
        ],
        transitions=[],
        anti_patterns=["Adding mesh.ops when user said primitives only"],
    )


def _strategy_blockout_only() -> ModelingStrategy:
    return ModelingStrategy(
        id="blockout_only",
        title="Blockout only — silhouette massing",
        rationale="Silhouette/massing pass — refinement comes in a later skill step.",
        phases=[
            StrategyPhase(
                name="Massing",
                goal="Named primitives + transforms; readable silhouette.",
                tools=["scene.create_object", "object.transform", "collection.organize"],
                hints=["Stop when silhouette reads; no bevels or materials."],
            ),
        ],
        transitions=["Hand off to surface/hardsurface skill for refinement."],
        anti_patterns=["Adding fine detail in blockout phase"],
    )


_STRATEGIES: dict[str, ModelingStrategy] = {
    "hybrid_blockout_surface": _strategy_hybrid_blockout_surface(),
    "hybrid_sculpt_surface": _strategy_hybrid_sculpt_surface(),
    "hardsurface_boolean": _strategy_hardsurface_boolean(),
    "low_poly_direct": _strategy_low_poly_direct(),
    "reference_turnaround": _strategy_reference_turnaround(),
    "bridge_loft": _strategy_bridge_loft(),
    "procedural_construction": _strategy_procedural_construction(),
    "primitives_only": _strategy_primitives_only(),
    "blockout_only": _strategy_blockout_only(),
}

_SKILL_DEFAULT_STRATEGY: dict[str, str] = {
    "modeling.primitives": "primitives_only",
    "modeling.blockout": "blockout_only",
    "modeling.low_poly": "low_poly_direct",
    "modeling.hardsurface": "hardsurface_boolean",
    "modeling.surface_advanced": "hybrid_blockout_surface",
    "modeling.character_stylized": "hybrid_sculpt_surface",
    "modeling.turnaround_character": "reference_turnaround",
    "modeling.create_mesh": "hybrid_blockout_surface",
    "modeling.modify_mesh": "hybrid_blockout_surface",
    "modeling.procedural": "procedural_construction",
}


def plan_modeling_strategy(
    user_message: str,
    *,
    skill_id: str | None = None,
    scene_summary: dict[str, Any] | None = None,
    has_reference_image: bool = False,
) -> ModelingStrategy | None:
    """Pick the best multi-method modeling plan for this session."""
    msg = (user_message or "").strip()
    if not msg and not skill_id:
        return None

    sid = (skill_id or "").strip()

    # Explicit skill overrides when unambiguous.
    if sid in _SKILL_DEFAULT_STRATEGY:
        key = _SKILL_DEFAULT_STRATEGY[sid]
        # Refine defaults using message signals.
        if sid == "modeling.procedural":
            return _STRATEGIES["procedural_construction"]
        if sid == "modeling.surface_advanced" and (_REFERENCE_RE.search(msg) or has_reference_image):
            return _STRATEGIES["reference_turnaround"]
        if sid == "modeling.surface_advanced" and _COMPLEX_OBJECT_RE.search(msg):
            return _STRATEGIES["procedural_construction"]
        if sid == "modeling.character_stylized" and (_SCULPT_RE.search(msg) or _DETAIL_RE.search(msg)):
            return _STRATEGIES["hybrid_sculpt_surface"]
        if sid == "modeling.create_mesh" and _COMPLEX_OBJECT_RE.search(msg):
            return _STRATEGIES["procedural_construction"]
        if sid == "modeling.create_mesh" and _HARDSURFACE_RE.search(msg):
            return _STRATEGIES["hardsurface_boolean"]
        return _STRATEGIES[key]

    # Message-driven selection when no skill.
    if _PRIMITIVES_RE.search(msg):
        return _STRATEGIES["primitives_only"]
    if _BLOCKOUT_RE.search(msg):
        return _STRATEGIES["blockout_only"]
    if _LOWPOLY_RE.search(msg):
        return _STRATEGIES["low_poly_direct"]
    if _COMPLEX_OBJECT_RE.search(msg):
        return _STRATEGIES["procedural_construction"]
    if _BRIDGE_RE.search(msg):
        return _STRATEGIES["bridge_loft"]
    if _HARDSURFACE_RE.search(msg) or (_PROP_RE.search(msg) and not _CHARACTER_RE.search(msg)):
        return _STRATEGIES["hardsurface_boolean"]
    if (_REFERENCE_RE.search(msg) or has_reference_image) and _CHARACTER_RE.search(msg):
        return _STRATEGIES["reference_turnaround"]

    # Scene hint: existing meshes → refine rather than fresh blockout.
    if scene_summary and _DETAIL_RE.search(msg):
        objects = scene_summary.get("objects") or []
        mesh_count = sum(1 for o in objects if str(o.get("type") or "").upper() == "MESH")
        if mesh_count > 0:
            strat = _strategy_hybrid_blockout_surface()
            return ModelingStrategy(
                id="hybrid_edit_existing",
                title="Hybrid: Edit existing mesh → Modifiers → Features",
                rationale="Scene already has mesh objects — refine with mesh.ops/extrude rather than new primitive stacks.",
                phases=[
                    StrategyPhase(
                        name="Assess & select",
                        goal="Use scene summary; selection.set or mesh.select on existing objects.",
                        tools=["selection.set", "mesh.select", "scene.summary"],
                        hints=["Delete or hide broken parts before rebuilding."],
                    ),
                    *strat.phases[1:],
                ],
                transitions=strat.transitions,
                anti_patterns=strat.anti_patterns + ["Ignoring existing scene objects"],
            )

    if _CHARACTER_RE.search(msg) and (_SCULPT_RE.search(msg) or _DETAIL_RE.search(msg)):
        return _STRATEGIES["hybrid_sculpt_surface"]
    if _CHARACTER_RE.search(msg) or _DETAIL_RE.search(msg):
        return _STRATEGIES["hybrid_blockout_surface"]

    return None


def format_strategy_for_prompt(strategy: ModelingStrategy | None) -> str:
    if not strategy:
        return ""
    return strategy.to_prompt_block()
