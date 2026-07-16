from __future__ import annotations

import re
from dataclasses import dataclass

# Surface/edit tools that break a primitive-only streak.
SURFACE_TOOLS = frozenset(
    {
        "mesh.ops",
        "mesh.extrude",
        "mesh.from_data",
        "mesh.profile_extrude",
        "mesh.edge_loop",
        "mesh.select",
        "mesh.loft_profiles",
        "curve.create",
        "python.run",
        "asset.import",
    }
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

_CHARACTER_RE = re.compile(
    r"\b(character|chibi|bird|animal|mascot|creature|stylized|کارتونی|پرنده|حیوان|کاراکتر)\b",
    re.IGNORECASE,
)
_DETAIL_RE = re.compile(
    r"\b(detailed|detail|realistic|accurate|جزئیات|دقیق|کامل)\b",
    re.IGNORECASE,
)
_HARDSURFACE_RE = re.compile(
    r"\b(hard[\s-]?surface|bevel|boolean|mechanical|صنعتی|مکانیک)\b",
    re.IGNORECASE,
)
_LOWPOLY_RE = re.compile(
    r"\b(low[\s-]?poly|game\s+asset|pixel|lowpoly|لو[\s-]?پلی)\b",
    re.IGNORECASE,
)
_BLOCKOUT_RE = re.compile(
    r"\b(blockout|block[\s-]?out|silhouette\s+only|massing|بلوک[\s-]?اوت)\b",
    re.IGNORECASE,
)
_PRIMITIVES_RE = re.compile(
    r"\b(primitives?\s+only|just\s+(a\s+)?(cube|sphere|cylinder)|فقط\s+پریمیتیو)\b",
    re.IGNORECASE,
)


@dataclass
class RouteDecision:
    skill_id: str | None
    strategy_id: str | None
    confidence: float
    reason: str


def infer_skill(user_message: str, skill_id: str | None = None) -> str | None:
    """Pick a modeling skill when none was explicitly selected."""
    if skill_id:
        return skill_id

    msg = (user_message or "").strip()
    if not msg:
        return None

    if _PRIMITIVES_RE.search(msg):
        return "modeling.primitives"
    if _BLOCKOUT_RE.search(msg):
        return "modeling.blockout"
    if _LOWPOLY_RE.search(msg):
        return "modeling.low_poly"
    if _COMPLEX_OBJECT_RE.search(msg):
        return "modeling.procedural"
    if _HARDSURFACE_RE.search(msg):
        return "modeling.hardsurface"
    if _CHARACTER_RE.search(msg) and (_DETAIL_RE.search(msg) or len(msg) > 40):
        return "modeling.surface_advanced"
    if _CHARACTER_RE.search(msg):
        return "modeling.character_stylized"
    if _DETAIL_RE.search(msg):
        return "modeling.surface_advanced"

    return None


def route(message: str, skill_id: str | None = None) -> RouteDecision:
    """Unified skill + strategy routing (keeps infer_skill for back-compat)."""
    from blender_ai_sidecar.chat.modeling_strategy import _SKILL_DEFAULT_STRATEGY

    explicit = bool((skill_id or "").strip())
    resolved = infer_skill(message, skill_id)
    strategy_id = _SKILL_DEFAULT_STRATEGY.get(resolved or "") if resolved else None

    if explicit:
        return RouteDecision(
            skill_id=resolved,
            strategy_id=strategy_id,
            confidence=1.0,
            reason="explicit skill_id",
        )
    if resolved:
        return RouteDecision(
            skill_id=resolved,
            strategy_id=strategy_id,
            confidence=0.75,
            reason=f"inferred from message → {resolved}",
        )
    return RouteDecision(
        skill_id=None,
        strategy_id=None,
        confidence=0.0,
        reason="no skill match",
    )


def is_surface_tool(tool: str) -> bool:
    return tool in SURFACE_TOOLS


def primitive_guardrail_message(streak: int) -> str:
    return (
        f"You placed {streak} primitives without surface edits. "
        "Use mesh.extrude / mesh.ops / mesh.profile_extrude / mesh.loft_profiles / "
        "curve.create / python.run next — do not add more loose primitives."
    )
