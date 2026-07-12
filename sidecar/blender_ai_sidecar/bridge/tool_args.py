from __future__ import annotations

from typing import Any

MAX_MESH_PARTS = 20
MAX_VERTS_PER_PART = 500
MAX_FACES_PER_PART = 1000
MAX_TOTAL_VERTS = 2000


def _flatten_scalar(value: Any) -> Any:
    """Unwrap single-element list nesting from model output, e.g. [[0.5]] -> 0.5."""
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    return value


def _as_float(value: Any, default: float) -> float:
    value = _flatten_scalar(value)
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    if isinstance(value, (list, tuple)) and value:
        return _as_float(value[0], default)
    return default


def _coerce_vec3(value: Any, default: tuple[float, float, float]) -> list[float]:
    value = _flatten_scalar(value)
    if value is None:
        return [float(default[0]), float(default[1]), float(default[2])]
    if isinstance(value, (int, float)):
        v = float(value)
        return [v, v, v]
    if isinstance(value, (list, tuple)):
        if len(value) == 1 and isinstance(value[0], (list, tuple)):
            return _coerce_vec3(value[0], default)
        if len(value) >= 3:
            return [_as_float(value[0], default[0]), _as_float(value[1], default[1]), _as_float(value[2], default[2])]
        if len(value) == 2:
            return [_as_float(value[0], default[0]), _as_float(value[1], default[1]), float(default[2])]
        if len(value) == 1:
            v = _as_float(value[0], default[0])
            return [v, v, v]
    return [float(default[0]), float(default[1]), float(default[2])]


def normalize_tool_args(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool == "mesh.from_data":
        return _normalize_mesh_from_data(args)
    if tool == "mesh.extrude":
        return _normalize_mesh_extrude(args)
    if tool == "mesh.profile_extrude":
        return _normalize_mesh_profile_extrude(args)
    if tool == "mesh.edge_loop":
        return _normalize_mesh_edge_loop(args)
    if tool != "scene.create_object":
        return args
    out = dict(args)
    raw_size = out.get("size")
    raw_size = _flatten_scalar(raw_size)
    if isinstance(raw_size, (list, tuple)) and len(raw_size) == 3 and "dimensions" not in out:
        out["dimensions"] = _coerce_vec3(raw_size, (1.0, 1.0, 1.0))
        out.pop("size", None)
    elif isinstance(raw_size, (list, tuple)) and raw_size:
        out["size"] = _as_float(raw_size[0], 2.0)
    elif raw_size is not None and not isinstance(raw_size, (list, tuple)):
        out["size"] = _as_float(raw_size, 2.0)
    for key in ("radius", "depth", "height", "major_radius", "minor_radius", "radius2"):
        val = out.get(key)
        if val is not None:
            out[key] = _as_float(val, 1.0)
    for key, default in (("location", 0.0), ("rotation", 0.0), ("scale", 1.0)):
        val = out.get(key)
        if val is not None:
            out[key] = _coerce_vec3(val, (default, default, default))
    dims = out.get("dimensions")
    if dims is not None:
        out["dimensions"] = _coerce_vec3(dims, (1.0, 1.0, 1.0))
    return out


def _normalize_mesh_from_data(args: dict[str, Any]) -> dict[str, Any]:
    out = dict(args)
    parts = out.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("mesh.from_data requires a non-empty parts array")

    if len(parts) > MAX_MESH_PARTS:
        raise ValueError(f"mesh.from_data supports at most {MAX_MESH_PARTS} parts")

    normalized_parts: list[dict[str, Any]] = []
    total_verts = 0

    for i, part in enumerate(parts):
        if not isinstance(part, dict):
            raise ValueError(f"Part {i}: must be an object")

        part_name = str(part.get("name") or f"Part_{i + 1}")
        raw_vertices = part.get("vertices")
        raw_faces = part.get("faces")

        if not isinstance(raw_vertices, list) or not raw_vertices:
            raise ValueError(f"Part {part_name}: vertices required")
        if not isinstance(raw_faces, list) or not raw_faces:
            raise ValueError(f"Part {part_name}: faces required")

        if len(raw_vertices) > MAX_VERTS_PER_PART:
            raise ValueError(
                f"Part {part_name}: {len(raw_vertices)} vertices exceeds limit of {MAX_VERTS_PER_PART}"
            )

        vertices: list[list[float]] = []
        for vi, vert in enumerate(raw_vertices):
            if not isinstance(vert, (list, tuple)) or len(vert) < 3:
                raise ValueError(f"Part {part_name}: vertex {vi} must be [x, y, z]")
            vertices.append([float(vert[0]), float(vert[1]), float(vert[2])])

        total_verts += len(vertices)
        if total_verts > MAX_TOTAL_VERTS:
            raise ValueError(f"mesh.from_data exceeds total vertex limit of {MAX_TOTAL_VERTS}")

        if len(raw_faces) > MAX_FACES_PER_PART:
            raise ValueError(
                f"Part {part_name}: {len(raw_faces)} faces exceeds limit of {MAX_FACES_PER_PART}"
            )

        faces: list[list[int]] = []
        vert_count = len(vertices)
        for fi, face in enumerate(raw_faces):
            if not isinstance(face, (list, tuple)) or len(face) < 3 or len(face) > 4:
                raise ValueError(
                    f"Part {part_name}: face {fi} must be a triangle [i,j,k] or quad [i,j,k,l]"
                )
            indices = [int(idx) for idx in face]
            for idx in indices:
                if idx < 0 or idx >= vert_count:
                    raise ValueError(
                        f"Part {part_name}: face index {idx} out of range (0..{vert_count - 1})"
                    )
            faces.append(indices)

        normalized_parts.append(
            {
                "name": part_name,
                "vertices": vertices,
                "faces": faces,
                "location": _coerce_vec3(part.get("location"), (0.0, 0.0, 0.0)),
                "rotation": _coerce_vec3(part.get("rotation"), (0.0, 0.0, 0.0)),
                "scale": _coerce_vec3(part.get("scale"), (1.0, 1.0, 1.0)),
            }
        )

    out["parts"] = normalized_parts
    if "flat_shade" not in out:
        out["flat_shade"] = True
    if "remove_doubles" not in out:
        out["remove_doubles"] = True
    return out


def _normalize_mesh_extrude(args: dict[str, Any]) -> dict[str, Any]:
    out = dict(args)
    if out.get("distance") is not None:
        out["distance"] = _as_float(out["distance"], 0.2)
    if out.get("offset") is not None and out.get("distance") is None:
        out["distance"] = _as_float(out["offset"], 0.2)
    if out.get("inset_after") is not None:
        out["inset_after"] = _as_float(out["inset_after"], 0.02)
    if out.get("direction") is not None:
        out["direction"] = _coerce_vec3(out["direction"], (0.0, -1.0, 0.0))
    return out


def _normalize_mesh_edge_loop(args: dict[str, Any]) -> dict[str, Any]:
    out = dict(args)
    out["count"] = max(1, int(_as_float(out.get("count"), 1)))
    return out


def _normalize_mesh_profile_extrude(args: dict[str, Any]) -> dict[str, Any]:
    out = dict(args)
    out["depth"] = _as_float(out.get("depth"), 0.1)
    profile = out.get("profile") or []
    normalized: list[list[float]] = []
    for point in profile:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            normalized.append([_as_float(point[0], 0.0), _as_float(point[1], 0.0)])
    out["profile"] = normalized
    if out.get("location") is not None:
        out["location"] = _coerce_vec3(out["location"], (0.0, 0.0, 0.0))
    if out.get("rotation") is not None:
        out["rotation"] = _coerce_vec3(out["rotation"], (0.0, 0.0, 0.0))
    if out.get("scale") is not None:
        out["scale"] = _coerce_vec3(out["scale"], (1.0, 1.0, 1.0))
    return out
