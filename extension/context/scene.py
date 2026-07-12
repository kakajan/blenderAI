from __future__ import annotations

import os
import tempfile
from typing import Any

import bpy


def build_summary(context=None) -> dict[str, Any]:
    context = context or bpy.context
    scene = context.scene
    obj = context.active_object
    selected = [o.name for o in context.selected_objects]
    materials = [m.name for m in bpy.data.materials[:30]]
    collections = [c.name for c in bpy.data.collections[:40]]
    objects = []
    total_verts = 0
    total_faces = 0
    for o in scene.objects[:80]:
        entry: dict[str, Any] = {
            "name": o.name,
            "type": o.type,
            "location": [round(v, 4) for v in o.location],
            "dimensions": [round(v, 4) for v in o.dimensions] if hasattr(o, "dimensions") else None,
        }
        if o.type == "MESH" and o.data:
            me = o.data
            n_verts = len(me.vertices)
            n_faces = len(me.polygons)
            total_verts += n_verts
            total_faces += n_faces
            entry["verts"] = n_verts
            entry["faces"] = n_faces
            entry["edges"] = len(me.edges)
            entry["uv_layers"] = len(me.uv_layers) if hasattr(me, "uv_layers") else 0
            entry["material_slots"] = len(o.material_slots)
            mods = [f"{m.name}:{m.type}" for m in o.modifiers]
            if mods:
                entry["modifiers"] = mods
        objects.append(entry)

    summary: dict[str, Any] = {
        "blend_file": bpy.data.filepath or "",
        "mode": context.mode,
        "render_engine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "active_object": None,
        "selection_count": len(selected),
        "selected": selected,
        "collections": collections,
        "materials": materials,
        "objects": objects,
        "object_names": [o["name"] for o in objects],
        "mesh_stats": {"total_verts": total_verts, "total_faces": total_faces, "object_count": len(objects)},
    }
    if obj:
        mods = [m.name + ":" + m.type for m in getattr(obj, "modifiers", [])]
        active: dict[str, Any] = {
            "name": obj.name,
            "type": obj.type,
            "location": [round(v, 4) for v in obj.location],
            "dimensions": [round(v, 4) for v in obj.dimensions] if hasattr(obj, "dimensions") else None,
            "modifiers": mods,
            "material_slots": len(getattr(obj, "material_slots", []) or []),
        }
        if obj.type == "MESH" and obj.data:
            me = obj.data
            active["verts"] = len(me.vertices)
            active["faces"] = len(me.polygons)
            active["edges"] = len(me.edges)
            active["uv_layers"] = len(me.uv_layers) if hasattr(me, "uv_layers") else 0
            # Rough non-manifold hint via loose edges count is expensive; skip — report doubles risk via face/vert ratio.
            if active["faces"] and active["verts"]:
                active["vert_face_ratio"] = round(active["verts"] / max(active["faces"], 1), 3)
        summary["active_object"] = active

    try:
        _area, space, _region = _find_view3d(context)
        if space and getattr(space, "region_3d", None):
            r3d = space.region_3d
            rot = r3d.view_rotation
            summary["viewport"] = {
                "shading": getattr(getattr(space, "shading", None), "type", None),
                "perspective": getattr(r3d, "view_perspective", None),
                "view_location": [round(float(v), 4) for v in r3d.view_location],
                "view_rotation": [round(float(v), 6) for v in (rot.w, rot.x, rot.y, rot.z)],
                "view_distance": round(float(r3d.view_distance), 4),
            }
    except Exception:
        pass

    try:
        cam = scene.camera
        if cam:
            summary["camera"] = {
                "name": cam.name,
                "location": [round(float(v), 4) for v in cam.location],
                "rotation_euler": [round(float(v), 4) for v in cam.rotation_euler],
                "lens": round(float(getattr(cam.data, "lens", 0.0) or 0.0), 2)
                if getattr(cam, "data", None)
                else None,
            }
    except Exception:
        pass

    try:
        lights = []
        for o in scene.objects:
            if o.type != "LIGHT":
                continue
            entry: dict[str, Any] = {
                "name": o.name,
                "type": getattr(getattr(o, "data", None), "type", None),
                "energy": round(float(getattr(getattr(o, "data", None), "energy", 0.0) or 0.0), 3),
                "location": [round(float(v), 4) for v in o.location],
            }
            lights.append(entry)
            if len(lights) >= 10:
                break
        if lights:
            summary["lights"] = lights
    except Exception:
        pass

    try:
        world = scene.world
        if world and getattr(world, "node_tree", None):
            bg = None
            for node in world.node_tree.nodes:
                if getattr(node, "type", None) == "BACKGROUND":
                    bg = node
                    break
            if bg is not None:
                color = list(bg.inputs[0].default_value)[:3] if len(bg.inputs) > 0 else None
                strength = float(bg.inputs[1].default_value) if len(bg.inputs) > 1 else None
                summary["world"] = {
                    "background_color": [round(float(c), 4) for c in color] if color else None,
                    "background_strength": round(strength, 3) if strength is not None else None,
                }
        elif world and hasattr(world, "color"):
            summary["world"] = {
                "background_color": [round(float(c), 4) for c in list(world.color)[:3]],
                "background_strength": None,
            }
    except Exception:
        pass

    return summary


# Named orthographic-style viewpoints: (azimuth degrees, elevation degrees).
# Azimuth 0 = front (looking from -Y), 90 = right (+X), 180 = back, -90 = left.
_VIEW_ANGLES = {
    "front": (0.0, 0.0),
    "back": (180.0, 0.0),
    "right": (90.0, 0.0),
    "left": (-90.0, 0.0),
    "side": (90.0, 0.0),
    "top": (0.0, 89.0),
    "three_quarter": (35.0, 12.0),
}


def _find_view3d(context):
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            space = next((sp for sp in area.spaces if sp.type == "VIEW_3D"), None)
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if space:
                return area, space, region
    return None, None, None


def _scene_focus(context, target=None):
    """World-space center + framing distance for a target object/point or all visible meshes."""
    from mathutils import Vector

    if isinstance(target, str):
        obj = bpy.data.objects.get(target)
        if obj:
            bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
            center = sum(bbox, Vector()) / 8.0
            size = max(
                max(v[i] for v in bbox) - min(v[i] for v in bbox) for i in range(3)
            )
            return center, max(size * 2.2, 0.5)
    if isinstance(target, (list, tuple)) and len(target) >= 3:
        return Vector((float(target[0]), float(target[1]), float(target[2]))), 3.0

    pts = []
    for o in context.scene.objects:
        if o.type == "MESH" and o.visible_get():
            pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    if not pts:
        return Vector((0.0, 0.0, 0.8)), 3.0
    mins = Vector(tuple(min(p[i] for p in pts) for i in range(3)))
    maxs = Vector(tuple(max(p[i] for p in pts) for i in range(3)))
    center = (mins + maxs) / 2.0
    size = max(maxs - mins)
    return center, max(size * 1.9, 0.8)


def _apply_view(space, view: str, center, dist: float, azimuth=None, elevation=None) -> None:
    from math import radians

    from mathutils import Euler

    r3d = space.region_3d
    if view == "camera":
        r3d.view_perspective = "CAMERA"
        return
    if azimuth is None or elevation is None:
        azimuth, elevation = _VIEW_ANGLES.get(view, (0.0, 0.0))
    r3d.view_perspective = "PERSP"
    r3d.view_rotation = Euler(
        (radians(90.0 - float(elevation)), 0.0, radians(float(azimuth))), "XYZ"
    ).to_quaternion()
    r3d.view_location = center
    r3d.view_distance = float(dist)


def _opengl_capture(context, area, region, path: str) -> bool:
    scene = context.scene
    prev = scene.render.filepath
    scene.render.filepath = path
    try:
        if area and region:
            with context.temp_override(area=area, region=region):
                bpy.ops.render.opengl(write_still=True)
        else:
            bpy.ops.render.opengl(write_still=True)
    finally:
        scene.render.filepath = prev
    return os.path.exists(path)


def capture_viewport(
    context=None,
    *,
    shading: str | None = None,
    view: str | None = None,
    target=None,
    distance: float | None = None,
    azimuth: float | None = None,
    elevation: float | None = None,
) -> str | None:
    """Capture one viewport image, optionally from a named or custom angle."""
    paths = capture_views(
        context,
        [view or "user"],
        shading=shading,
        target=target,
        distance=distance,
        azimuth=azimuth,
        elevation=elevation,
    )
    return paths[0]["path"] if paths else None


def capture_views(
    context=None,
    views=None,
    *,
    shading: str | None = None,
    target=None,
    distance: float | None = None,
    azimuth: float | None = None,
    elevation: float | None = None,
) -> list[dict[str, Any]]:
    """Capture the scene from multiple angles (front/side/back/...) in one call.

    Returns [{"view": name, "path": png_path, "framing": {...}}, ...].
    "user" keeps the current viewport orientation untouched.
    """
    context = context or bpy.context
    views = [str(v).lower() for v in (views or ["user"])]
    results: list[dict[str, Any]] = []
    try:
        import time

        tmp = tempfile.gettempdir()
        area, space, region = _find_view3d(context)

        prev_shading = space.shading.type if space else None
        saved_view = None
        if space:
            r3d = space.region_3d
            saved_view = (
                r3d.view_perspective,
                r3d.view_rotation.copy(),
                r3d.view_location.copy(),
                r3d.view_distance,
            )
        if shading and space:
            mode = shading.upper()
            if mode in {"MATERIAL", "RENDERED", "SOLID", "WIREFRAME"}:
                space.shading.type = mode

        center, auto_dist = _scene_focus(context, target)
        dist = float(distance) if distance else auto_dist
        framing = {
            "center": [round(float(c), 4) for c in center],
            "distance": float(dist),
        }

        try:
            stamp = int(time.time() * 1000)
            for i, v in enumerate(views):
                if v != "user" and space:
                    _apply_view(
                        space,
                        v,
                        center,
                        dist,
                        azimuth=azimuth if v == "custom" else None,
                        elevation=elevation if v == "custom" else None,
                    )
                path = os.path.join(tmp, f"blender_ai_view_{v}_{stamp}_{i}.png")
                if _opengl_capture(context, area, region, path):
                    results.append({"view": v, "path": path, "framing": framing})
        finally:
            if space and saved_view:
                r3d = space.region_3d
                r3d.view_perspective = saved_view[0]
                r3d.view_rotation = saved_view[1]
                r3d.view_location = saved_view[2]
                r3d.view_distance = saved_view[3]
            if space and prev_shading:
                space.shading.type = prev_shading
        return results
    except Exception:
        return results
