from __future__ import annotations

import math
from typing import Any

import bpy
import bmesh

from ..context import scene as scene_ctx
from .allowlist import KNOWN_TOOLS
from .paths import require_allowed_file


def run_tool(tool: str, args: dict[str, Any], context) -> dict[str, Any]:
    if tool not in KNOWN_TOOLS:
        return {"ok": False, "error": "Unknown tool"}
    try:
        if tool == "scene.summary":
            return {"ok": True, "summary": scene_ctx.build_summary(context)}
        if tool == "viewport.capture":
            views = args.get("views")
            if views:
                shots = scene_ctx.capture_views(
                    context,
                    views,
                    shading=args.get("shading"),
                    target=args.get("target") or args.get("object"),
                    distance=args.get("distance"),
                    azimuth=args.get("azimuth"),
                    elevation=args.get("elevation"),
                )
                if not shots:
                    return {"ok": False, "error": "No views captured"}
                return {"ok": True, "views": shots, "path": shots[0]["path"]}
            path = scene_ctx.capture_viewport(
                context,
                shading=args.get("shading"),
                view=args.get("view"),
                target=args.get("target") or args.get("object"),
                distance=args.get("distance"),
                azimuth=args.get("azimuth"),
                elevation=args.get("elevation"),
            )
            return {"ok": True, "path": path}
        if tool == "undo":
            bpy.ops.ed.undo()
            return {"ok": True}
        if tool == "redo":
            bpy.ops.ed.redo()
            return {"ok": True}
        if tool == "scene.create_object":
            return _create_object(args, context)
        if tool == "mesh.from_data":
            return _mesh_from_data(args, context)
        if tool == "selection.set":
            return _selection_set(args, context)
        if tool == "mesh.select":
            return _mesh_select(args, context)
        if tool == "mesh.extrude":
            return _mesh_extrude(args, context)
        if tool == "mesh.edge_loop":
            return _mesh_edge_loop(args, context)
        if tool == "mesh.profile_extrude":
            return _mesh_profile_extrude(args, context)
        if tool == "object.transform":
            return _object_transform(args, context)
        if tool == "object.join":
            return _object_join(args, context)
        if tool == "object.duplicate":
            return _object_duplicate(args, context)
        if tool == "object.delete":
            return _object_delete(args, context)
        if tool == "object.parent":
            return _object_parent(args, context)
        if tool == "modifier.add":
            return _modifier_add(args, context)
        if tool == "modifier.apply":
            return _modifier_apply(args, context)
        if tool == "material.create":
            return _material_create(args, context)
        if tool == "material.assign":
            return _material_assign(args, context)
        if tool == "light.set":
            return _light_set(args, context)
        if tool == "world.set":
            return _world_set(args, context)
        if tool == "world.hdri_set":
            return _world_hdri_set(args, context)
        if tool == "collection.organize":
            return _collection_organize(args, context)
        if tool == "render.set":
            return _render_set(args, context)
        if tool == "mesh.ops":
            return _mesh_ops(args, context)
        if tool == "uv.unwrap":
            return _uv_unwrap(args, context)
        if tool == "camera.set":
            return _camera_set(args, context)
        if tool == "scene.reference_image":
            return _scene_reference_image(args, context)
        if tool == "sculpt.set_brush":
            return _sculpt_brush(args, context)
        if tool == "sculpt.remesh":
            return _sculpt_remesh(args, context)
        if tool == "node.set":
            return _node_set(args, context)
        if tool == "nodes.geometry_set":
            return _nodes_geometry_set(args, context)
        if tool == "particle.fur_set":
            return _particle_fur_set(args, context)
        if tool == "viewport.set_shading":
            return _viewport_set_shading(args, context)
        if tool == "blender.introspect":
            return _blender_introspect(args, context)
        if tool == "anim.keyframes":
            return _anim_keyframes(args, context)
        if tool == "anim.walk_to_camera":
            mode = (args.get("mode") or args.get("preset") or "walk").lower()
            if mode in {"throw_bounce", "bounce", "ball_throw", "basketball"}:
                return _anim_throw_bounce(args, context)
            return _anim_walk_to_camera(args, context)
        if tool == "anim.throw_bounce":
            return _anim_throw_bounce(args, context)
        if tool == "anim.play":
            return _anim_play(args, context)
        if tool == "anim.set_frame":
            return _anim_set_frame(args, context)
        return {"ok": False, "error": f"Unknown tool: {tool}"}
    except Exception as e:
        from .. import log_client

        log_client.exception(f"Tool {tool} failed: {e}", e, component="tools")
        return {"ok": False, "error": str(e)}


def _ensure_object_mode(context) -> None:
    """Object operators (select_all, modifiers) require OBJECT mode."""
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _deselect_all_objects(context) -> None:
    """Deselect without bpy.ops — safe after EDIT/SCULPT mode."""
    for obj in context.view_layer.objects:
        obj.select_set(False)


def _activate_object(context, name: str | None = None):
    _ensure_object_mode(context)
    if name:
        obj = bpy.data.objects.get(name)
        if not obj:
            return None
        _deselect_all_objects(context)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return obj
    return context.active_object


def _flatten_scalar(value: Any) -> Any:
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


def _as_vec3(value: Any, default: tuple[float, float, float]) -> list[float]:
    value = _flatten_scalar(value)
    if value is None:
        return list(default)
    if isinstance(value, (int, float)):
        v = float(value)
        return [v, v, v]
    if isinstance(value, (list, tuple)):
        if len(value) == 1 and isinstance(value[0], (list, tuple)):
            return _as_vec3(value[0], default)
        if len(value) >= 3:
            return [_as_float(value[0], default[0]), _as_float(value[1], default[1]), _as_float(value[2], default[2])]
        if len(value) == 2:
            return [_as_float(value[0], default[0]), _as_float(value[1], default[1]), float(default[2])]
        if len(value) == 1:
            v = _as_float(value[0], default[0])
            return [v, v, v]
    return list(default)


def _create_object(args: dict[str, Any], context) -> dict[str, Any]:
    kind = (args.get("type") or args.get("primitive") or "cube").lower()
    name = args.get("name") or kind.capitalize()
    loc = _as_vec3(args.get("location"), (0.0, 0.0, 0.0))
    rot = _as_vec3(args.get("rotation"), (0.0, 0.0, 0.0))
    scale = _as_vec3(args.get("scale"), (1.0, 1.0, 1.0))
    dimensions = args.get("dimensions")
    raw_size = args.get("size")
    if isinstance(raw_size, (list, tuple)) and len(raw_size) == 3 and dimensions is None:
        dimensions = raw_size
        raw_size = None
    size = _as_float(raw_size, 2.0)
    radius = _as_float(args.get("radius"), size / 2)
    depth = _as_float(args.get("depth") or args.get("height"), size)
    segments = int(_as_float(args.get("segments") or args.get("vertices"), 32))
    rings = int(_as_float(args.get("rings"), 16))

    mapping = {
        "cube": lambda: bpy.ops.mesh.primitive_cube_add(size=size, location=loc, rotation=rot),
        "uv_sphere": lambda: bpy.ops.mesh.primitive_uv_sphere_add(
            radius=radius, location=loc, rotation=rot, segments=segments, ring_count=rings
        ),
        "sphere": lambda: bpy.ops.mesh.primitive_uv_sphere_add(
            radius=radius, location=loc, rotation=rot, segments=segments, ring_count=rings
        ),
        "ico_sphere": lambda: bpy.ops.mesh.primitive_ico_sphere_add(
            radius=radius, location=loc, rotation=rot, subdivisions=int(args.get("subdivisions") or 2)
        ),
        "cylinder": lambda: bpy.ops.mesh.primitive_cylinder_add(
            radius=radius, depth=depth, location=loc, rotation=rot, vertices=segments
        ),
        "cone": lambda: bpy.ops.mesh.primitive_cone_add(
            radius1=radius,
            radius2=_as_float(args.get("radius2"), 0.0),
            depth=depth,
            location=loc,
            rotation=rot,
            vertices=segments,
        ),
        "torus": lambda: bpy.ops.mesh.primitive_torus_add(
            location=loc,
            rotation=rot,
            major_radius=_as_float(args.get("major_radius"), radius),
            minor_radius=_as_float(args.get("minor_radius"), radius * 0.25),
            major_segments=segments,
            minor_segments=int(_as_float(args.get("minor_segments"), 12)),
        ),
        "plane": lambda: bpy.ops.mesh.primitive_plane_add(size=size, location=loc, rotation=rot),
        "monkey": lambda: bpy.ops.mesh.primitive_monkey_add(size=size, location=loc, rotation=rot),
        "grid": lambda: bpy.ops.mesh.primitive_grid_add(
            size=size,
            location=loc,
            rotation=rot,
            x_subdivisions=int(args.get("x_subdivisions") or 10),
            y_subdivisions=int(args.get("y_subdivisions") or 10),
        ),
        "empty": lambda: bpy.ops.object.empty_add(
            type=str(args.get("empty_type") or args.get("subtype") or "PLAIN_AXES").upper(),
            location=loc,
            rotation=rot,
        ),
    }
    fn = mapping.get(kind, mapping["cube"])
    fn()
    obj = context.active_object
    if obj:
        obj.name = name
        if scale != [1.0, 1.0, 1.0]:
            obj.scale = scale
        dims = dimensions or args.get("dimensions")
        if isinstance(dims, (list, tuple)) and len(dims) >= 3:
            obj.dimensions = _as_vec3(dims, (1.0, 1.0, 1.0))
    return {"ok": True, "name": obj.name if obj else name, "type": kind}


def _mesh_from_data(args: dict[str, Any], context) -> dict[str, Any]:
    """Build one or more meshes from explicit vertex/face coordinate lists."""
    _ensure_object_mode(context)
    parts = args.get("parts") or []
    if not parts:
        return {"ok": False, "error": "parts required"}

    root_name = args.get("name") or "LowPoly_Mesh"
    flat_shade = args.get("flat_shade", True)
    remove_doubles = args.get("remove_doubles", True)
    merge_threshold = _as_float(args.get("merge_threshold"), 0.0001)
    collection_name = args.get("collection")

    target_collection = context.collection
    if collection_name:
        col = bpy.data.collections.get(collection_name) or bpy.data.collections.new(collection_name)
        if col.name not in context.scene.collection.children:
            context.scene.collection.children.link(col)
        target_collection = col

    created: list[dict[str, Any]] = []
    for i, part in enumerate(parts):
        if not isinstance(part, dict):
            return {"ok": False, "error": f"Part {i}: must be an object"}
        part_name = part.get("name") or f"{root_name}_Part{i + 1}"
        vertices = part.get("vertices") or []
        faces = part.get("faces") or []
        if not vertices or not faces:
            return {"ok": False, "error": f"Part {part_name}: vertices and faces required"}

        mesh = bpy.data.meshes.new(part_name)
        mesh.from_pydata(vertices, [], faces)
        mesh.update(calc_edges=True)

        if remove_doubles:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_threshold)
            bm.to_mesh(mesh)
            bm.free()
            mesh.update()

        smooth = not flat_shade
        for poly in mesh.polygons:
            poly.use_smooth = smooth

        obj = bpy.data.objects.new(part_name, mesh)
        target_collection.objects.link(obj)

        obj.location = _as_vec3(part.get("location"), (0.0, 0.0, 0.0))
        obj.rotation_euler = _as_vec3(part.get("rotation"), (0.0, 0.0, 0.0))
        obj.scale = _as_vec3(part.get("scale"), (1.0, 1.0, 1.0))

        created.append(
            {
                "name": obj.name,
                "verts": len(mesh.vertices),
                "faces": len(mesh.polygons),
            }
        )

    _deselect_all_objects(context)
    if created:
        first_obj = bpy.data.objects.get(created[0]["name"])
        if first_obj:
            first_obj.select_set(True)
            context.view_layer.objects.active = first_obj

    return {
        "ok": True,
        "name": root_name,
        "parts": created,
        "total_verts": sum(p["verts"] for p in created),
        "total_faces": sum(p["faces"] for p in created),
    }


def _selection_set(args: dict[str, Any], context) -> dict[str, Any]:
    _ensure_object_mode(context)
    names = args.get("names") or args.get("objects") or []
    mode = args.get("mode") or "replace"
    if mode == "replace":
        _deselect_all_objects(context)
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.select_set(True)
            context.view_layer.objects.active = obj
    return {"ok": True, "selected": names}


def _axis_index(axis: str) -> int:
    return {"x": 0, "y": 1, "z": 2}.get(str(axis or "z").lower(), 2)


def _clear_mesh_selection(bm) -> None:
    for f in bm.faces:
        f.select = False
    for e in bm.edges:
        e.select = False
    for v in bm.verts:
        v.select = False


def _select_faces_semantic(bm, args: dict[str, Any]) -> int:
    """Select faces using indices, region, by_normal, top_cap, or bottom_cap."""
    selected = 0
    indices = args.get("indices")
    region = args.get("region")
    by_normal = args.get("by_normal")
    top_cap = args.get("top_cap")
    bottom_cap = args.get("bottom_cap")
    ring = args.get("ring")
    faces_key = str(args.get("faces") or "").lower()

    if by_normal or faces_key == "by_normal":
        spec = by_normal if isinstance(by_normal, dict) else {}
        direction = spec.get("direction") or args.get("direction") or [0, -1, 0]
        threshold = float(spec.get("threshold") if spec.get("threshold") is not None else args.get("threshold") or 0.7)
        if isinstance(direction, (list, tuple)) and len(direction) >= 3:
            length = math.sqrt(sum(float(d) ** 2 for d in direction[:3]))
            if length < 1e-6:
                direction = [0.0, -1.0, 0.0]
                length = 1.0
            direction = [float(direction[0]) / length, float(direction[1]) / length, float(direction[2]) / length]
            for f in bm.faces:
                n = f.normal
                dot = n.x * direction[0] + n.y * direction[1] + n.z * direction[2]
                if dot >= threshold:
                    f.select = True
                    selected += 1
    elif top_cap is not None or faces_key == "top_cap":
        spec = top_cap if isinstance(top_cap, dict) else {}
        axis_i = _axis_index(str(spec.get("axis") or args.get("axis") or "z"))
        percent = float(
            spec.get("percent") if spec.get("percent") is not None else args.get("percent") if args.get("percent") is not None else 0.15
        )
        coords = [v.co[axis_i] for v in bm.verts]
        if coords:
            vmin, vmax = min(coords), max(coords)
            cutoff = vmax - (vmax - vmin) * percent
            for f in bm.faces:
                if f.calc_center_median()[axis_i] >= cutoff:
                    f.select = True
                    selected += 1
    elif bottom_cap is not None or faces_key == "bottom_cap":
        spec = bottom_cap if isinstance(bottom_cap, dict) else {}
        axis_i = _axis_index(str(spec.get("axis") or args.get("axis") or "z"))
        percent = float(
            spec.get("percent") if spec.get("percent") is not None else args.get("percent") if args.get("percent") is not None else 0.15
        )
        coords = [v.co[axis_i] for v in bm.verts]
        if coords:
            vmin, vmax = min(coords), max(coords)
            cutoff = vmin + (vmax - vmin) * percent
            for f in bm.faces:
                if f.calc_center_median()[axis_i] <= cutoff:
                    f.select = True
                    selected += 1
    elif ring is not None or faces_key == "ring":
        spec = ring if isinstance(ring, dict) else {}
        axis_i = _axis_index(str(spec.get("axis") or args.get("axis") or "z"))
        center = float(spec.get("center") if spec.get("center") is not None else 0.0)
        width = float(spec.get("width") if spec.get("width") is not None else 0.1)
        half = width / 2.0
        for f in bm.faces:
            c = f.calc_center_median()[axis_i]
            if center - half <= c <= center + half:
                f.select = True
                selected += 1
    elif region:
        axis = str(region.get("axis") or "z").lower()
        axis_i = _axis_index(axis)
        rmin = float(region.get("min") if region.get("min") is not None else -1e9)
        rmax = float(region.get("max") if region.get("max") is not None else 1e9)
        for f in bm.faces:
            c = f.calc_center_median()[axis_i]
            if rmin <= c <= rmax:
                f.select = True
                selected += 1
    elif args.get("ring"):
        ring = args.get("ring") if isinstance(args.get("ring"), dict) else {}
        axis_i = _axis_index(str(ring.get("axis") or args.get("axis") or "z"))
        center = float(ring.get("center") if ring.get("center") is not None else 0.0)
        width = float(ring.get("width") if ring.get("width") is not None else 0.1)
        half = width / 2.0
        for f in bm.faces:
            c = f.calc_center_median()[axis_i]
            if center - half <= c <= center + half:
                f.select = True
                selected += 1
    elif indices is not None:
        for i in indices:
            if 0 <= int(i) < len(bm.faces):
                bm.faces[int(i)].select = True
                selected += 1
    else:
        for f in bm.faces:
            f.select = True
            selected += 1
    return selected


def _mesh_select(args: dict[str, Any], context) -> dict[str, Any]:
    """Select mesh components in Edit Mode (faces/edges/verts)."""
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj or obj.type != "MESH":
        return {"ok": False, "error": "Active mesh required"}

    target = (args.get("target") or args.get("mode") or "faces").lower()
    indices = args.get("indices")
    region = args.get("region")

    bpy.ops.object.mode_set(mode="EDIT")
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    _clear_mesh_selection(bm)
    selected = 0

    if target in {"all", "all_faces", "faces"}:
        if args.get("by_normal") or args.get("top_cap") or args.get("bottom_cap") or args.get("ring") or str(args.get("faces") or "").lower() in {
            "by_normal",
            "top_cap",
            "bottom_cap",
        }:
            selected = _select_faces_semantic(bm, args)
        elif indices is not None:
            for i in indices:
                if 0 <= int(i) < len(bm.faces):
                    bm.faces[int(i)].select = True
                    selected += 1
        elif region:
            selected = _select_faces_semantic(bm, {"region": region})
        else:
            for f in bm.faces:
                f.select = True
                selected += 1
        bpy.ops.mesh.select_mode(type="FACE")
    elif target in {"edges", "all_edges"}:
        if args.get("boundary"):
            for e in bm.edges:
                if len(e.link_faces) == 1:
                    e.select = True
                    selected += 1
        elif indices is not None:
            for i in indices:
                if 0 <= int(i) < len(bm.edges):
                    bm.edges[int(i)].select = True
                    selected += 1
        else:
            for e in bm.edges:
                e.select = True
                selected += 1
        bpy.ops.mesh.select_mode(type="EDGE")
    elif target in {"verts", "vertices", "all_verts"}:
        if indices is not None:
            for i in indices:
                if 0 <= int(i) < len(bm.verts):
                    bm.verts[int(i)].select = True
                    selected += 1
        else:
            for v in bm.verts:
                v.select = True
                selected += 1
        bpy.ops.mesh.select_mode(type="VERT")
    else:
        bpy.ops.object.mode_set(mode="OBJECT")
        return {"ok": False, "error": f"Unknown mesh select target: {target}"}

    bmesh.update_edit_mesh(me)
    if args.get("object_mode"):
        bpy.ops.object.mode_set(mode="OBJECT")
    return {"ok": True, "target": target, "selected": selected, "object": obj.name}


def _mesh_extrude(args: dict[str, Any], context) -> dict[str, Any]:
    """Select faces semantically, extrude, optionally inset."""
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj or obj.type != "MESH":
        return {"ok": False, "error": "Active mesh required"}

    distance = float(args.get("distance") if args.get("distance") is not None else args.get("offset") or 0.2)
    direction = args.get("direction")
    axis = str(args.get("axis") or "z").lower()

    bpy.ops.object.mode_set(mode="EDIT")
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()
    _clear_mesh_selection(bm)
    selected = _select_faces_semantic(bm, args)
    if selected == 0:
        bpy.ops.object.mode_set(mode="OBJECT")
        return {"ok": False, "error": "No faces selected for extrude", "object": obj.name}
    bmesh.update_edit_mesh(me)

    if direction and isinstance(direction, (list, tuple)) and len(direction) >= 3:
        offset = [float(direction[0]) * distance, float(direction[1]) * distance, float(direction[2]) * distance]
    else:
        offset = [0.0, 0.0, 0.0]
        offset[_axis_index(axis)] = distance

    bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": tuple(offset)})

    inset_after = args.get("inset_after")
    if inset_after is not None:
        bpy.ops.mesh.inset(thickness=float(inset_after), depth=0.0)

    bpy.ops.object.mode_set(mode="OBJECT")
    return {"ok": True, "object": obj.name, "selected": selected, "distance": distance}


def _mesh_edge_loop(args: dict[str, Any], context) -> dict[str, Any]:
    """Insert evenly spaced edge loops along an axis using bisect_plane."""
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj or obj.type != "MESH":
        return {"ok": False, "error": "Active mesh required"}

    count = max(1, int(args.get("count") or 1))
    axis_i = _axis_index(str(args.get("axis") or "z"))

    bpy.ops.object.mode_set(mode="EDIT")
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    bm.verts.ensure_lookup_table()
    coords = [v.co[axis_i] for v in bm.verts]
    if not coords:
        bpy.ops.object.mode_set(mode="OBJECT")
        return {"ok": False, "error": "Mesh has no vertices"}

    vmin, vmax = min(coords), max(coords)
    span = vmax - vmin
    if span < 1e-6:
        bpy.ops.object.mode_set(mode="OBJECT")
        return {"ok": False, "error": "Degenerate mesh bounds"}

    plane_no = [0.0, 0.0, 0.0]
    plane_no[axis_i] = 1.0
    loops_added = 0
    for i in range(1, count + 1):
        t = i / (count + 1)
        plane_co = [0.0, 0.0, 0.0]
        plane_co[axis_i] = vmin + span * t
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        try:
            bmesh.ops.bisect_plane(
                bm,
                geom=geom,
                dist=0.0001,
                plane_co=plane_co,
                plane_no=plane_no,
                clear_inner=False,
                clear_outer=False,
            )
            loops_added += 1
        except Exception:
            pass

    bmesh.update_edit_mesh(me)
    bpy.ops.object.mode_set(mode="OBJECT")
    return {"ok": True, "object": obj.name, "loops_added": loops_added, "count": count}


def _mesh_profile_extrude(args: dict[str, Any], context) -> dict[str, Any]:
    """Build a mesh by extruding a 2D profile along an axis."""
    profile = args.get("profile") or []
    if len(profile) < 3:
        return {"ok": False, "error": "Profile needs at least 3 points"}

    depth = float(args.get("depth") or 0.1)
    axis_i = _axis_index(str(args.get("axis") or "y"))
    perp = [(axis_i + 1) % 3, (axis_i + 2) % 3]
    name = str(args.get("name") or "Profile_Mesh")

    verts_front: list[list[float]] = []
    verts_back: list[list[float]] = []
    for point in profile:
        u = float(point[0])
        v = float(point[1]) if len(point) > 1 else 0.0
        front = [0.0, 0.0, 0.0]
        back = [0.0, 0.0, 0.0]
        front[perp[0]] = u
        front[perp[1]] = v
        back[perp[0]] = u
        back[perp[1]] = v
        back[axis_i] = depth
        verts_front.append(front)
        verts_back.append(back)

    n = len(profile)
    all_verts = verts_front + verts_back
    faces: list[list[int]] = []
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    for i in range(1, n - 1):
        faces.append([0, i, i + 1])
    for i in range(1, n - 1):
        faces.append([n, n + i + 1, n + i])

    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(all_verts, [], faces)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    coll = context.collection
    if args.get("collection"):
        coll = bpy.data.collections.get(str(args["collection"])) or coll
    coll.objects.link(obj)
    if args.get("location"):
        obj.location = tuple(args["location"])
    if args.get("rotation"):
        obj.rotation_euler = tuple(args["rotation"])
    if args.get("scale"):
        obj.scale = tuple(args["scale"])
    if bool(args.get("flat_shade", True)):
        for p in mesh.polygons:
            p.use_smooth = False
    context.view_layer.objects.active = obj
    obj.select_set(True)
    return {
        "ok": True,
        "name": obj.name,
        "verts": len(all_verts),
        "faces": len(faces),
    }


def _object_transform(args: dict[str, Any], context) -> dict[str, Any]:
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj:
        return {"ok": False, "error": "Object not found"}
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    if "location" in args:
        obj.location = args["location"]
    if "rotation" in args:
        obj.rotation_euler = args["rotation"]
    if "scale" in args:
        obj.scale = args["scale"]
    if "dimensions" in args:
        dims = args["dimensions"]
        if len(dims) == 3:
            obj.dimensions = dims
    if args.get("new_name") or args.get("rename"):
        obj.name = args.get("new_name") or args.get("rename")
    return {
        "ok": True,
        "name": obj.name,
        "location": list(obj.location),
        "scale": list(obj.scale),
        "dimensions": list(obj.dimensions),
    }


def _object_join(args: dict[str, Any], context) -> dict[str, Any]:
    names = args.get("objects") or args.get("names") or []
    if len(names) < 2:
        return {"ok": False, "error": "Need at least 2 objects to join"}
    _ensure_object_mode(context)
    _deselect_all_objects(context)
    objs = []
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.select_set(True)
            objs.append(obj)
    if len(objs) < 2:
        return {"ok": False, "error": "Could not find enough objects"}
    active_name = args.get("active") or names[0]
    active = bpy.data.objects.get(active_name) or objs[0]
    context.view_layer.objects.active = active
    bpy.ops.object.join()
    joined = context.active_object
    if joined and args.get("name"):
        joined.name = args["name"]
    return {"ok": True, "name": joined.name if joined else active.name, "joined": names}


def _modifier_add(args: dict[str, Any], context) -> dict[str, Any]:
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj:
        return {"ok": False, "error": "No active object"}
    mod_type = (args.get("type") or "BEVEL").upper()
    mod_name = args.get("modifier_name") or args.get("name") or mod_type.title()
    try:
        mod = obj.modifiers.new(name=mod_name, type=mod_type)
    except TypeError:
        return {"ok": False, "error": f"Unsupported modifier type: {mod_type}"}
    props = dict(args.get("props") or {})
    # Convenience aliases for BOOLEAN operand object name
    operand = (
        args.get("operand")
        or args.get("boolean_object")
        or props.pop("operand", None)
        or props.pop("object", None)
        or props.pop("boolean_object", None)
    )
    for k, v in props.items():
        if not hasattr(mod, k):
            continue
        try:
            # Resolve object-name strings to Blender Object pointers (BOOLEAN, MIRROR object, etc.)
            if isinstance(v, str) and k in {"object", "mirror_object", "offset_object", "target"}:
                resolved = bpy.data.objects.get(v)
                if resolved:
                    setattr(mod, k, resolved)
                continue
            setattr(mod, k, v)
        except Exception:
            pass
    if operand and hasattr(mod, "object"):
        resolved = bpy.data.objects.get(str(operand))
        if resolved:
            mod.object = resolved
        else:
            return {"ok": False, "error": f"BOOLEAN operand not found: {operand}", "modifier": mod.name}
    if mod_type == "BOOLEAN" and hasattr(mod, "operation"):
        op = (args.get("operation") or props.get("operation") or "DIFFERENCE")
        if isinstance(op, str):
            mod.operation = op.upper()
    return {"ok": True, "modifier": mod.name, "object": obj.name, "type": mod_type}


def _modifier_apply(args: dict[str, Any], context) -> dict[str, Any]:
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj:
        return {"ok": False, "error": "No active object"}
    mod_name = args.get("modifier") or args.get("modifier_name") or args.get("name")
    if mod_name and mod_name in obj.modifiers:
        bpy.ops.object.modifier_apply(modifier=mod_name)
        return {"ok": True, "applied": mod_name, "object": obj.name}
    mod_type = (args.get("type") or "").upper()
    if mod_type:
        for m in obj.modifiers:
            if m.type == mod_type:
                bpy.ops.object.modifier_apply(modifier=m.name)
                return {"ok": True, "applied": m.name, "object": obj.name}
    return {"ok": False, "error": "modifier not found"}


def _material_assign(args: dict[str, Any], context) -> dict[str, Any]:
    mat_name = args.get("material") or args.get("name")
    mat = bpy.data.materials.get(mat_name) if mat_name else None
    if not mat:
        return {"ok": False, "error": "material not found"}
    targets = args.get("objects") or []
    objs = [bpy.data.objects.get(n) for n in targets] if targets else [context.active_object]
    assigned = []
    for obj in objs:
        if not obj:
            continue
        if obj.data and hasattr(obj.data, "materials"):
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
            assigned.append(obj.name)
    return {"ok": True, "assigned": assigned}


def _light_set(args: dict[str, Any], context) -> dict[str, Any]:
    name = args.get("name") or "AI_Light"
    light_type = (args.get("light_type") or args.get("type") or "AREA").upper()
    if light_type not in {"POINT", "SUN", "SPOT", "AREA"}:
        light_type = "AREA"
    energy = float(args.get("energy") or 100.0)
    loc = _as_vec3(args.get("location"), (3.0, -3.0, 5.0))
    existing = bpy.data.objects.get(name)
    if existing and existing.type == "LIGHT":
        obj = existing
        if (args.get("type") or args.get("light_type")) and obj.data.type != light_type:
            obj.data.type = light_type
        obj.data.energy = energy
        obj.location = loc
    else:
        light_data = bpy.data.lights.new(name=name, type=light_type)
        light_data.energy = energy
        obj = bpy.data.objects.new(name=name, object_data=light_data)
        context.collection.objects.link(obj)
        obj.location = loc

    if "size" in args or "size_x" in args:
        size = float(args.get("size") or args.get("size_x") or 1.0)
        if hasattr(obj.data, "size"):
            obj.data.size = size
        if hasattr(obj.data, "shadow_soft_size"):
            obj.data.shadow_soft_size = float(args.get("shadow_soft_size") or size * 0.25)
    if "size_y" in args and hasattr(obj.data, "size_y"):
        obj.data.size_y = float(args["size_y"])
    if args.get("shape") and hasattr(obj.data, "shape"):
        try:
            obj.data.shape = str(args["shape"]).upper()
        except Exception:
            pass
    color = args.get("color") or args.get("base_color")
    if color and hasattr(obj.data, "color"):
        c = list(color)[:3]
        while len(c) < 3:
            c.append(1.0)
        obj.data.color = c[:3]
    if "rotation" in args:
        obj.rotation_euler = _as_vec3(args["rotation"], (0.0, 0.0, 0.0))
    look_at = args.get("look_at") or args.get("target")
    if look_at:
        from mathutils import Vector

        target = look_at
        if isinstance(look_at, str):
            target_obj = bpy.data.objects.get(look_at)
            target = list(target_obj.location) if target_obj else None
        if isinstance(target, (list, tuple)) and len(target) >= 3:
            direction = Vector(target[:3]) - Vector(obj.location)
            # Lights aim along local -Z
            obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return {"ok": True, "light": obj.name, "type": obj.data.type, "energy": obj.data.energy}


def _world_set(args: dict[str, Any], context) -> dict[str, Any]:
    world = context.scene.world or bpy.data.worlds.new("World")
    context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        if "color" in args:
            c = args["color"]
            if len(c) == 3:
                c = list(c) + [1.0]
            bg.inputs["Color"].default_value = c
        if "strength" in args:
            bg.inputs["Strength"].default_value = float(args["strength"])
    return {"ok": True}


def _collection_organize(args: dict[str, Any], context) -> dict[str, Any]:
    col_name = args.get("collection") or "AI_Collection"
    col = bpy.data.collections.get(col_name) or bpy.data.collections.new(col_name)
    if col.name not in context.scene.collection.children:
        context.scene.collection.children.link(col)
    moved = []
    for name in args.get("objects") or []:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        col.objects.link(obj)
        moved.append(name)
    return {"ok": True, "collection": col.name, "moved": moved}


def _render_set(args: dict[str, Any], context) -> dict[str, Any]:
    scene = context.scene
    render = scene.render
    if "engine" in args:
        engine = args["engine"]
        if engine in {"CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"}:
            scene.render.engine = engine
    samples = args.get("samples")
    if samples is not None:
        if hasattr(scene, "cycles"):
            try:
                scene.cycles.samples = int(samples)
            except Exception:
                pass
        eevee = getattr(scene, "eevee", None)
        if eevee is not None:
            for attr in ("taa_render_samples", "samples"):
                if hasattr(eevee, attr):
                    try:
                        setattr(eevee, attr, int(samples))
                    except Exception:
                        pass
    if "resolution_x" in args:
        render.resolution_x = int(args["resolution_x"])
    if "resolution_y" in args:
        render.resolution_y = int(args["resolution_y"])
    if "resolution_percentage" in args:
        render.resolution_percentage = int(args["resolution_percentage"])
    # Denoise / film / exposure (best-effort across versions)
    if "denoise" in args and hasattr(scene, "cycles"):
        try:
            scene.cycles.use_denoising = bool(args["denoise"])
        except Exception:
            pass
    if args.get("device") and hasattr(scene, "cycles"):
        try:
            scene.cycles.device = str(args["device"]).upper()
        except Exception:
            pass
    view = scene.view_settings
    if "exposure" in args:
        view.exposure = float(args["exposure"])
    if "gamma" in args:
        try:
            view.gamma = float(args["gamma"])
        except Exception:
            pass
    if "look" in args:
        try:
            view.look = args["look"]
        except Exception:
            pass
    if args.get("filmic") or (args.get("view_transform") or "").upper() == "FILMIC":
        try:
            view.view_transform = "Filmic"
        except Exception:
            pass
    if "view_transform" in args and not args.get("filmic"):
        try:
            view.view_transform = args["view_transform"]
        except Exception:
            pass
    if "fps" in args:
        render.fps = int(args["fps"])
    if "frame_start" in args:
        scene.frame_start = int(args["frame_start"])
    if "frame_end" in args:
        scene.frame_end = int(args["frame_end"])
    if "frame" in args:
        scene.frame_set(int(args["frame"]))
    # Output path / format (animation-ready)
    filepath = args.get("filepath") or args.get("output") or args.get("path")
    if filepath:
        render.filepath = str(filepath)
    file_format = args.get("file_format") or args.get("format")
    media_type = args.get("media_type")
    if file_format:
        fmt = str(file_format).upper()
        aliases = {"MP4": "FFMPEG", "VIDEO": "FFMPEG", "MOVIE": "FFMPEG", "JPG": "JPEG"}
        fmt = aliases.get(fmt, fmt)
        # Blender 5.1+: video formats require media_type before/instead of FFMPEG enum
        wants_video = fmt == "FFMPEG" or str(media_type or "").upper() == "VIDEO"
        if wants_video and hasattr(render.image_settings, "media_type"):
            try:
                render.image_settings.media_type = "VIDEO"
            except Exception:
                pass
        try:
            render.image_settings.file_format = fmt
        except Exception:
            # Fallback for builds where FFMPEG is selected via media_type only
            if wants_video and hasattr(render.image_settings, "media_type"):
                try:
                    render.image_settings.media_type = "VIDEO"
                except Exception:
                    pass
    elif media_type and hasattr(render.image_settings, "media_type"):
        try:
            render.image_settings.media_type = str(media_type).upper()
        except Exception:
            pass
    if "color_mode" in args:
        try:
            render.image_settings.color_mode = str(args["color_mode"]).upper()
        except Exception:
            pass
    if "color_depth" in args:
        try:
            render.image_settings.color_depth = str(args["color_depth"])
        except Exception:
            pass
    if "compression" in args:
        try:
            render.image_settings.compression = int(args["compression"])
        except Exception:
            pass
    if "quality" in args:
        try:
            render.image_settings.quality = int(args["quality"])
        except Exception:
            pass
    if render.image_settings.file_format == "FFMPEG" or str(file_format or "").upper() in {
        "FFMPEG",
        "MP4",
        "VIDEO",
        "MOVIE",
    }:
        ffmpeg = render.ffmpeg
        container = str(args.get("container") or args.get("ffmpeg_format") or "MPEG4").upper()
        codec = str(args.get("codec") or args.get("ffmpeg_codec") or "H264").upper()
        try:
            ffmpeg.format = container
        except Exception:
            pass
        try:
            ffmpeg.codec = codec
        except Exception:
            pass
        if "ffmpeg_preset" in args or "preset" in args:
            try:
                ffmpeg.constant_rate_factor = str(args.get("ffmpeg_preset") or args.get("preset") or "MEDIUM").upper()
            except Exception:
                pass
        if "audio_codec" in args:
            try:
                ffmpeg.audio_codec = str(args["audio_codec"]).upper()
            except Exception:
                pass
        if "video_bitrate" in args:
            try:
                ffmpeg.video_bitrate = int(args["video_bitrate"])
            except Exception:
                pass
    if "film_transparent" in args:
        try:
            render.film_transparent = bool(args["film_transparent"])
        except Exception:
            pass
    if "use_overwrite" in args:
        render.use_overwrite = bool(args["use_overwrite"])
    if "use_placeholder" in args:
        render.use_placeholder = bool(args["use_placeholder"])
    blur: dict[str, Any] | None = None
    if "motion_blur" in args or "shutter" in args:
        blur = _enable_motion_blur(scene, shutter=float(args.get("shutter") or 0.5))
        if args.get("motion_blur") is False:
            try:
                render.use_motion_blur = False
            except Exception:
                pass
            eevee = getattr(scene, "eevee", None)
            if eevee is not None and hasattr(eevee, "use_motion_blur"):
                try:
                    eevee.use_motion_blur = False
                except Exception:
                    pass
            blur = {"enabled": False}
    result: dict[str, Any] = {
        "ok": True,
        "engine": scene.render.engine,
        "filepath": render.filepath,
        "file_format": render.image_settings.file_format,
        "resolution": [render.resolution_x, render.resolution_y],
        "fps": int(render.fps),
        "frame_start": int(scene.frame_start),
        "frame_end": int(scene.frame_end),
    }
    if hasattr(render.image_settings, "media_type"):
        try:
            result["media_type"] = str(render.image_settings.media_type)
        except Exception:
            pass
    if blur is not None:
        result["motion_blur"] = blur
    if hasattr(scene, "cycles"):
        try:
            result["samples"] = int(scene.cycles.samples)
            result["denoise"] = bool(getattr(scene.cycles, "use_denoising", False))
        except Exception:
            pass
    return result


def _ensure_edit_selection(bm, select_all_if_empty: bool = True) -> int:
    selected = sum(1 for f in bm.faces if f.select)
    if selected == 0 and select_all_if_empty:
        for f in bm.faces:
            f.select = True
        selected = len(bm.faces)
    return selected


def _mesh_ops(args: dict[str, Any], context) -> dict[str, Any]:
    op = (args.get("op") or "").lower()
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj or obj.type != "MESH":
        return {"ok": False, "error": "Active mesh required"}

    # Optional component select before op (same call)
    pre_select = args.get("select") or args.get("select_faces")
    region = args.get("region")

    bpy.ops.object.mode_set(mode="EDIT")
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()

    if pre_select or region or args.get("select_all"):
        for f in bm.faces:
            f.select = False
        if args.get("select_all") or pre_select in {"all", "faces", True}:
            for f in bm.faces:
                f.select = True
        elif isinstance(pre_select, list):
            for i in pre_select:
                if 0 <= int(i) < len(bm.faces):
                    bm.faces[int(i)].select = True
        if region:
            axis = str(region.get("axis") or "z").lower()
            axis_i = {"x": 0, "y": 1, "z": 2}.get(axis, 2)
            rmin = float(region.get("min") if region.get("min") is not None else -1e9)
            rmax = float(region.get("max") if region.get("max") is not None else 1e9)
            for f in bm.faces:
                c = f.calc_center_median()[axis_i]
                f.select = rmin <= c <= rmax
        bmesh.update_edit_mesh(me)
        bpy.ops.mesh.select_mode(type="FACE")
    else:
        _ensure_edit_selection(bm, select_all_if_empty=True)
        bmesh.update_edit_mesh(me)

    try:
        if op in {"bevel"}:
            bpy.ops.mesh.bevel(
                offset=float(args.get("offset") or args.get("width") or 0.02),
                segments=int(args.get("segments") or 2),
                affect="EDGES",
            )
        elif op in {"extrude"}:
            bpy.ops.mesh.extrude_region_move(
                TRANSFORM_OT_translate={"value": tuple(args.get("offset") or [0, 0, 0.2])}
            )
        elif op in {"extrude_edges"}:
            bpy.ops.mesh.extrude_edges_move(
                TRANSFORM_OT_translate={"value": tuple(args.get("offset") or [0, 0, 0.1])}
            )
        elif op in {"extrude_individual", "extrude_faces_individual"}:
            bpy.ops.mesh.extrude_faces_move(
                TRANSFORM_OT_translate={"value": tuple(args.get("offset") or [0, 0, 0.1])}
            )
        elif op in {"inset"}:
            bpy.ops.mesh.inset(
                thickness=float(args.get("thickness") or 0.05),
                depth=float(args.get("depth") or 0.0),
            )
        elif op in {"subdivide"}:
            bpy.ops.mesh.subdivide(number_cuts=int(args.get("cuts") or 1))
        elif op in {"loop_cut", "loopcut"}:
            # Number of cuts along the longest edge ring of selected faces
            cuts = int(args.get("cuts") or 1)
            smoothness = float(args.get("smoothness") or 0.0)
            bpy.ops.mesh.loopcut_slide(
                MESH_OT_loopcut={
                    "number_cuts": cuts,
                    "smoothness": smoothness,
                    "falloff": "INVERSE_SQUARE",
                    "object_index": 0,
                },
                TRANSFORM_OT_edge_slide={"value": float(args.get("slide") or 0.0)},
            )
        elif op in {"dissolve", "dissolve_faces"}:
            bpy.ops.mesh.dissolve_faces()
        elif op in {"dissolve_edges"}:
            bpy.ops.mesh.dissolve_edges()
        elif op in {"delete", "delete_faces"}:
            bpy.ops.mesh.delete(type="FACE")
        elif op in {"duplicate"}:
            bpy.ops.mesh.duplicate_move(
                TRANSFORM_OT_translate={"value": tuple(args.get("offset") or [0.5, 0, 0])}
            )
        elif op in {"bridge", "bridge_edge_loops"}:
            bpy.ops.mesh.bridge_edge_loops()
        elif op in {"smooth", "shade_smooth"}:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.shade_smooth()
            return {"ok": True, "op": op, "object": obj.name}
        elif op in {"shade_flat"}:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.shade_flat()
            return {"ok": True, "op": op, "object": obj.name}
        elif op in {"remove_doubles", "merge_by_distance"}:
            bpy.ops.mesh.remove_doubles(threshold=float(args.get("threshold") or 0.0001))
        elif op in {"recalculate_normals", "normals"}:
            bpy.ops.mesh.normals_make_consistent(inside=False)
        elif op in {"poke"}:
            bpy.ops.mesh.poke()
        elif op in {"wireframe"}:
            bpy.ops.mesh.wireframe(thickness=float(args.get("thickness") or 0.02))
        elif op in {"solidify"}:
            # Destructive solidify via operator
            bpy.ops.mesh.solidify(thickness=float(args.get("thickness") or 0.05))
        elif op in {"bisect"}:
            plane_co = tuple(args.get("plane_co") or [0, 0, 0])
            plane_no = tuple(args.get("plane_no") or [0, 0, 1])
            bpy.ops.mesh.bisect(
                plane_co=plane_co,
                plane_no=plane_no,
                clear_inner=bool(args.get("clear_inner") or False),
                clear_outer=bool(args.get("clear_outer") or False),
            )
        elif op in {"knife", "cut"}:
            # Non-interactive knife: cut through selected faces along a plane (bisect alias)
            plane_co = tuple(args.get("plane_co") or [0, 0, 0])
            plane_no = tuple(args.get("plane_no") or [1, 0, 0])
            bpy.ops.mesh.bisect(plane_co=plane_co, plane_no=plane_no)
        elif op in {"edge_slide", "edgeslide"}:
            bpy.ops.transform.edge_slide(value=float(args.get("value") or args.get("slide") or 0.2))
        elif op in {"merge", "merge_center"}:
            typ = (args.get("type") or "CENTER").upper()
            if typ not in {"CENTER", "CURSOR", "COLLAPSE", "FIRST", "LAST"}:
                typ = "CENTER"
            bpy.ops.mesh.merge(type=typ)
        elif op in {"fill", "grid_fill", "f"}:
            try:
                bpy.ops.mesh.fill_grid()
            except Exception:
                bpy.ops.mesh.fill()
        elif op in {"spin"}:
            bpy.ops.mesh.spin(
                steps=int(args.get("steps") or 8),
                angle=float(args.get("angle") or 6.283185),
                center=tuple(args.get("center") or list(obj.location)),
                axis=tuple(args.get("axis") or [0, 0, 1]),
            )
        elif op in {"crease", "edge_crease"}:
            val = float(args.get("value") if args.get("value") is not None else 1.0)
            bpy.ops.object.mode_set(mode="OBJECT")
            me = obj.data
            for e in me.edges:
                if e.select or args.get("select_all"):
                    e.crease = val
            return {"ok": True, "op": op, "object": obj.name, "value": val}
        elif op in {"bevel_weight", "edge_bevel_weight"}:
            val = float(args.get("value") if args.get("value") is not None else 1.0)
            bpy.ops.object.mode_set(mode="OBJECT")
            me = obj.data
            for e in me.edges:
                if e.select or args.get("select_all"):
                    e.bevel_weight = val
            return {"ok": True, "op": op, "object": obj.name, "value": val}
        else:
            return {"ok": False, "error": f"Unknown mesh op: {op}"}
    finally:
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    return {"ok": True, "op": op, "object": obj.name}


def _object_duplicate(args: dict[str, Any], context) -> dict[str, Any]:
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj:
        return {"ok": False, "error": "Object not found"}
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.duplicate(linked=bool(args.get("linked") or False))
    new = context.active_object
    if new and args.get("new_name"):
        new.name = args["new_name"]
    if new and args.get("offset"):
        off = args["offset"]
        new.location = (
            new.location[0] + float(off[0]),
            new.location[1] + float(off[1]),
            new.location[2] + float(off[2]),
        )
    return {"ok": True, "name": new.name if new else "", "from": obj.name}


def _object_delete(args: dict[str, Any], context) -> dict[str, Any]:
    names = args.get("objects") or args.get("names") or []
    if args.get("object"):
        names = list(names) + [args["object"]]
    if args.get("name") and args["name"] not in names:
        names = list(names) + [args["name"]]
    if not names:
        return {"ok": False, "error": "No objects specified"}
    _ensure_object_mode(context)
    _deselect_all_objects(context)
    deleted = []
    for name in names:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        obj.select_set(True)
        deleted.append(name)
    if not deleted:
        missing = [str(n) for n in names]
        return {"ok": False, "error": f"No matching objects: {', '.join(missing)}"}
    bpy.ops.object.delete()
    return {"ok": True, "deleted": deleted}


def _object_parent(args: dict[str, Any], context) -> dict[str, Any]:
    parent_name = args.get("parent")
    children = args.get("children") or args.get("objects") or []
    parent = bpy.data.objects.get(parent_name) if parent_name else None
    if not parent:
        return {"ok": False, "error": "Parent not found"}
    linked = []
    for name in children:
        child = bpy.data.objects.get(name)
        if not child or child == parent:
            continue
        child.parent = parent
        if args.get("keep_transform", True):
            child.matrix_parent_inverse = parent.matrix_world.inverted()
        linked.append(name)
    return {"ok": True, "parent": parent.name, "children": linked}


def _uv_unwrap(args: dict[str, Any], context) -> dict[str, Any]:
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj or obj.type != "MESH":
        return {"ok": False, "error": "Active mesh required"}
    method = (args.get("method") or "smart").lower()
    if args.get("mark_seam"):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.mark_seam(clear=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        if method in {"smart", "smart_project"}:
            bpy.ops.uv.smart_project(
                angle_limit=float(args.get("angle_limit") or 66.0) * 3.14159 / 180.0,
                island_margin=float(args.get("island_margin") or 0.02),
            )
        else:
            bpy.ops.uv.unwrap(
                method="ANGLE_BASED",
                margin=float(args.get("margin") or 0.001),
            )
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    return {"ok": True, "object": obj.name, "method": method}


def _camera_set(args: dict[str, Any], context) -> dict[str, Any]:
    name = args.get("name") or "AI_Camera"
    loc = args.get("location") or [3, -3, 2]
    cam_obj = bpy.data.objects.get(name)
    if not cam_obj or cam_obj.type != "CAMERA":
        data = bpy.data.cameras.new(name=name)
        cam_obj = bpy.data.objects.new(name, data)
        context.collection.objects.link(cam_obj)
    cam_obj.location = loc
    if "rotation" in args:
        cam_obj.rotation_euler = args["rotation"]
    look_at = args.get("look_at") or args.get("target")
    track_to = args.get("track_to") or args.get("track_object")
    if look_at and not track_to:
        target = None
        if isinstance(look_at, str):
            target = bpy.data.objects.get(look_at)
            if target:
                look_at = list(target.location)
        if isinstance(look_at, (list, tuple)) and len(look_at) == 3:
            from mathutils import Vector

            direction = Vector(look_at) - Vector(cam_obj.location)
            cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    if track_to:
        target_obj = bpy.data.objects.get(str(track_to)) if isinstance(track_to, str) else None
        if target_obj:
            for c in list(cam_obj.constraints):
                if c.type in {"TRACK_TO", "DAMPED_TRACK"}:
                    cam_obj.constraints.remove(c)
            track = cam_obj.constraints.new(type="TRACK_TO")
            track.target = target_obj
            track.track_axis = "TRACK_NEGATIVE_Z"
            track.up_axis = "UP_Y"
    if "lens" in args or "focal" in args:
        cam_obj.data.lens = float(args.get("lens") or args.get("focal") or 50)
    if "clip_start" in args:
        cam_obj.data.clip_start = float(args["clip_start"])
    if "clip_end" in args:
        cam_obj.data.clip_end = float(args["clip_end"])
    if args.get("dof") or args.get("use_dof"):
        cam_obj.data.dof.use_dof = True
        focus = args.get("focus_object") or args.get("dof_object")
        if isinstance(focus, str) and bpy.data.objects.get(focus):
            cam_obj.data.dof.focus_object = bpy.data.objects.get(focus)
        if "focus_distance" in args:
            cam_obj.data.dof.focus_distance = float(args["focus_distance"])
        if "aperture" in args or "fstop" in args:
            cam_obj.data.dof.aperture_fstop = float(args.get("aperture") or args.get("fstop") or 2.8)
    if args.get("set_active", True):
        context.scene.camera = cam_obj
    return {
        "ok": True,
        "camera": cam_obj.name,
        "location": list(cam_obj.location),
        "track_to": str(track_to) if track_to else None,
        "lens": float(cam_obj.data.lens),
    }


def _world_hdri_set(args: dict[str, Any], context) -> dict[str, Any]:
    path = args.get("path") or args.get("filepath") or args.get("file")
    if not path:
        return {"ok": False, "error": "HDRI path required"}
    allowed, err = require_allowed_file(path)
    if err:
        return err
    assert allowed is not None
    world = context.scene.world or bpy.data.worlds.new("World")
    context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(allowed, check_existing=True)
    bg.inputs["Strength"].default_value = float(args.get("strength") or 1.0)
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return {"ok": True, "path": allowed, "strength": bg.inputs["Strength"].default_value}


def _scene_reference_image(args: dict[str, Any], context) -> dict[str, Any]:
    path = args.get("path") or args.get("filepath") or args.get("file")
    if not path:
        return {"ok": False, "error": "Image path required"}
    allowed, err = require_allowed_file(path)
    if err:
        return err
    assert allowed is not None
    name = args.get("name") or "AI_Reference"
    # Empty image reference
    bpy.ops.object.empty_add(type="IMAGE", location=args.get("location") or [0, -2, 1])
    empty = context.active_object
    if empty:
        empty.name = name
        img = bpy.data.images.load(allowed, check_existing=True)
        empty.data = img
        empty.empty_display_size = float(args.get("size") or 2.0)
        if "opacity" in args and hasattr(empty, "color"):
            empty.color[3] = float(args["opacity"])
        if args.get("rotation"):
            empty.rotation_euler = args["rotation"]
    return {"ok": True, "name": empty.name if empty else name, "path": allowed}


def _material_create(args: dict[str, Any], context) -> dict[str, Any]:
    name = args.get("name") or "AI_Material"
    template = (args.get("template") or args.get("type") or "principled").lower()
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if not bsdf:
        return {"ok": True, "material": mat.name}

    if template in {"glossy_eye", "eye", "eye_glossy"}:
        color = args.get("base_color") or args.get("color") or [0.02, 0.02, 0.04, 1.0]
        if len(color) == 3:
            color = list(color) + [1.0]
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = float(args.get("roughness") or 0.04)
        bsdf.inputs["Metallic"].default_value = float(args.get("metallic") or 0.0)
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = float(args.get("specular") or 0.9)
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = float(args.get("coat") or 0.6)
            bsdf.inputs["Coat Roughness"].default_value = float(args.get("coat_roughness") or 0.05)
        if "IOR" in bsdf.inputs:
            bsdf.inputs["IOR"].default_value = float(args.get("ior") or 1.45)
        return {"ok": True, "material": mat.name, "template": template}

    if template in {"soft_fur", "fur", "velvet"}:
        color = args.get("base_color") or args.get("color") or [0.42, 0.15, 0.68, 1.0]
        if len(color) == 3:
            color = list(color) + [1.0]
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = float(args.get("roughness") or 0.92)
        if "Sheen Weight" in bsdf.inputs:
            bsdf.inputs["Sheen Weight"].default_value = float(args.get("sheen") or 0.35)
        if "Sheen Roughness" in bsdf.inputs:
            bsdf.inputs["Sheen Roughness"].default_value = float(args.get("sheen_roughness") or 0.8)
        return {"ok": True, "material": mat.name, "template": template}

    if template in {"plastic", "matte_plastic"}:
        color = args.get("base_color") or args.get("color") or [0.96, 0.48, 0.1, 1.0]
        if len(color) == 3:
            color = list(color) + [1.0]
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = float(args.get("roughness") or 0.35)
        bsdf.inputs["Metallic"].default_value = 0.0
        return {"ok": True, "material": mat.name, "template": template}

    color = args.get("base_color") or args.get("color") or [0.8, 0.8, 0.8, 1.0]
    if len(color) == 3:
        color = list(color) + [1.0]
    bsdf.inputs["Base Color"].default_value = color
    if "roughness" in args:
        bsdf.inputs["Roughness"].default_value = float(args["roughness"])
    if "metallic" in args:
        bsdf.inputs["Metallic"].default_value = float(args["metallic"])
    if "specular" in args and "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = float(args["specular"])
    tex_path = args.get("image") or args.get("diffuse") or args.get("albedo")
    if tex_path:
        err = _link_image_to_principled(nt, bsdf, tex_path, "Base Color")
        if err:
            return err
    rough_path = args.get("roughness_map")
    if rough_path:
        err = _link_image_to_principled(nt, bsdf, rough_path, "Roughness", non_color=True)
        if err:
            return err
    normal_path = args.get("normal_map") or args.get("normal")
    if normal_path:
        err = _link_normal_map(nt, bsdf, normal_path)
        if err:
            return err
    return {"ok": True, "material": mat.name, "template": template}


def _link_image_to_principled(nt, bsdf, path: str, input_name: str, *, non_color: bool = False):
    allowed, err = require_allowed_file(path)
    if err:
        return err
    assert allowed is not None
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(allowed, check_existing=True)
    if non_color and tex.image:
        try:
            tex.image.colorspace_settings.name = "Non-Color"
        except Exception:
            pass
    if input_name in bsdf.inputs:
        nt.links.new(tex.outputs["Color"], bsdf.inputs[input_name])
    return None


def _link_normal_map(nt, bsdf, path: str):
    allowed, err = require_allowed_file(path)
    if err:
        return err
    assert allowed is not None
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(allowed, check_existing=True)
    try:
        if tex.image:
            tex.image.colorspace_settings.name = "Non-Color"
    except Exception:
        pass
    nrm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tex.outputs["Color"], nrm.inputs["Color"])
    if "Normal" in bsdf.inputs:
        nt.links.new(nrm.outputs["Normal"], bsdf.inputs["Normal"])
    return None


def _node_set(args: dict[str, Any], context) -> dict[str, Any]:
    """Parametric Principled wiring — not freeform node graphs."""
    mat_name = args.get("material") or args.get("name")
    mat = bpy.data.materials.get(mat_name) if mat_name else None
    if not mat:
        mat = bpy.data.materials.new(name=mat_name or "AI_Material")
        mat.use_nodes = True
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if not bsdf:
        return {"ok": False, "error": "Principled BSDF missing"}
    template = (args.get("template") or args.get("op") or "principled").lower()
    if template in {"principled", "set"}:
        props = args.get("props") or args
        if "base_color" in props or "color" in props:
            c = props.get("base_color") or props.get("color")
            if len(c) == 3:
                c = list(c) + [1.0]
            bsdf.inputs["Base Color"].default_value = c
        for key, socket in (("roughness", "Roughness"), ("metallic", "Metallic")):
            if key in props:
                bsdf.inputs[socket].default_value = float(props[key])
    if args.get("image") or args.get("diffuse"):
        err = _link_image_to_principled(nt, bsdf, args.get("image") or args.get("diffuse"), "Base Color")
        if err:
            return err
    if args.get("roughness_map"):
        err = _link_image_to_principled(nt, bsdf, args["roughness_map"], "Roughness", non_color=True)
        if err:
            return err
    if args.get("normal_map") or args.get("normal"):
        err = _link_normal_map(nt, bsdf, args.get("normal_map") or args.get("normal"))
        if err:
            return err
    if template in {"mix_wear", "wear"}:
        # Simple mix: darker edge wear via fresnel factor into base color mix
        mix = nt.nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MIX"
        fresnel = nt.nodes.new("ShaderNodeFresnel")
        wear = list(args.get("wear_color") or [0.15, 0.15, 0.15, 1.0])
        if len(wear) == 3:
            wear = wear + [1.0]
        mix.inputs["Color2"].default_value = wear
        base = bsdf.inputs["Base Color"].default_value[:]
        mix.inputs["Color1"].default_value = base
        nt.links.new(fresnel.outputs["Fac"], mix.inputs["Fac"])
        nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    return {"ok": True, "material": mat.name, "template": template}


def _nodes_geometry_set(args: dict[str, Any], context) -> dict[str, Any]:
    """Limited Geometry Nodes templates: scatter, array, extrude."""
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj or obj.type != "MESH":
        return {"ok": False, "error": "Active mesh required"}
    template = (args.get("template") or "array").lower()
    mod_name = args.get("modifier_name") or "AI_GeometryNodes"
    # Prefer modifier-based approximations for reliability across Blender versions
    if template in {"array"}:
        count = int(args.get("count") or 3)
        offset = args.get("offset") or [1.1, 0, 0]
        mod = obj.modifiers.new(name=mod_name, type="ARRAY")
        mod.count = count
        mod.relative_offset_displace = offset
        return {"ok": True, "template": "array", "modifier": mod.name, "object": obj.name}
    if template in {"scatter", "instance", "fur"}:
        return _particle_fur_set(
            {
                "object": obj.name,
                "modifier_name": mod_name,
                "count": args.get("count"),
                "length": args.get("size") or args.get("length"),
                "color": args.get("color"),
            },
            context,
        )
    if template in {"extrude", "solidify"}:
        mod = obj.modifiers.new(name=mod_name, type="SOLIDIFY")
        mod.thickness = float(args.get("thickness") or 0.05)
        return {"ok": True, "template": "extrude", "modifier": mod.name, "object": obj.name}
    if template in {"subdivide", "subsurf"}:
        mod = obj.modifiers.new(name=mod_name, type="SUBSURF")
        mod.levels = int(args.get("levels") or 2)
        return {"ok": True, "template": "subdivide", "modifier": mod.name, "object": obj.name}
    return {"ok": False, "error": f"Unknown geometry template: {template}"}


def _set_if(obj, attr: str, value) -> None:
    """Set optional particle attrs defensively across Blender versions."""
    try:
        if hasattr(obj, attr):
            setattr(obj, attr, value)
    except Exception:
        pass


def _configure_fur_settings(settings, args: dict[str, Any]) -> None:
    preset = (args.get("preset") or args.get("style") or "soft").lower()
    length = float(args.get("length") or args.get("size") or 0.012)
    count = int(args.get("count") or 1200)
    settings.type = "HAIR"
    settings.emit_from = "FACE"
    _set_if(settings, "use_emit_random", True)
    _set_if(settings, "use_advanced_hair", True)
    settings.count = count
    settings.hair_length = length
    _set_if(settings, "root_radius", float(args.get("root_radius") or length * 0.35))
    _set_if(settings, "tip_radius", float(args.get("tip_radius") or length * 0.08))
    _set_if(settings, "display_step", 3)
    _set_if(settings, "render_step", 4)
    if preset in {"soft", "fluffy", "down", "velvet"}:
        settings.child_type = "INTERPOLATED"
        _set_if(settings, "child_nbr", int(args.get("children") or 12))
        _set_if(settings, "rendered_child_count", int(args.get("children") or 12) * 2)
        _set_if(settings, "child_length", float(args.get("child_length") or 0.6))
        _set_if(settings, "child_radius", float(args.get("child_radius") or 0.4))
        _set_if(settings, "clump_factor", float(args.get("clump") or 0.25))
        _set_if(settings, "roughness_1", float(args.get("roughness_1") or 0.12))
        _set_if(settings, "roughness_1_size", 0.6)
        _set_if(settings, "roughness_2", float(args.get("roughness_2") or 0.05))
        _set_if(settings, "kink", "CURL")
        _set_if(settings, "kink_amplitude", float(args.get("kink") or 0.003))
        _set_if(settings, "kink_frequency", 2.0)
    elif preset in {"spiky", "rough"}:
        settings.child_type = "SIMPLE"
        _set_if(settings, "child_nbr", int(args.get("children") or 4))
        _set_if(settings, "child_length", float(args.get("child_length") or 0.8))
        _set_if(settings, "roughness_1", 0.4)


def _particle_fur_set(args: dict[str, Any], context) -> dict[str, Any]:
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj or obj.type != "MESH":
        return {"ok": False, "error": "Active mesh required"}
    mod_name = args.get("modifier_name") or args.get("name") or "AI_Fur"
    existing = obj.modifiers.get(mod_name)
    if existing and existing.type == "PARTICLE_SYSTEM":
        psys_mod = existing
        psys = obj.particle_systems[existing.name] if existing.name in obj.particle_systems else obj.particle_systems[-1]
        settings = psys.settings
    else:
        psys_mod = obj.modifiers.new(name=mod_name, type="PARTICLE_SYSTEM")
        psys = obj.particle_systems[-1]
        settings = psys.settings
    _configure_fur_settings(settings, args)
    return {
        "ok": True,
        "modifier": psys_mod.name,
        "object": obj.name,
        "count": settings.count,
        "length": settings.hair_length,
        "preset": args.get("preset") or "soft",
    }


def _viewport_set_shading(args: dict[str, Any], context) -> dict[str, Any]:
    mode = (args.get("mode") or args.get("type") or args.get("shading") or "MATERIAL").upper()
    if mode not in {"MATERIAL", "RENDERED", "SOLID", "WIREFRAME"}:
        return {"ok": False, "error": f"Unknown shading mode: {mode}"}
    updated = 0
    for area in context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        for space in area.spaces:
            if space.type == "VIEW_3D":
                space.shading.type = mode
                updated += 1
    return {"ok": True, "mode": mode, "areas": updated}


def _sculpt_remesh(args: dict[str, Any], context) -> dict[str, Any]:
    obj = _activate_object(context, args.get("object") or args.get("name"))
    if not obj or obj.type != "MESH":
        return {"ok": False, "error": "Active mesh required"}
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    mode = (args.get("mode") or "voxel").lower()
    if mode == "voxel":
        obj.data.remesh_voxel_size = float(args.get("voxel_size") or 0.05)
        bpy.ops.object.voxel_remesh()
    else:
        # Quad remesh fallback
        try:
            bpy.ops.object.quadriflow_remesh()
        except Exception:
            obj.data.remesh_voxel_size = float(args.get("voxel_size") or 0.05)
            bpy.ops.object.voxel_remesh()
    return {"ok": True, "object": obj.name, "mode": mode}


def _sculpt_brush(args: dict[str, Any], context) -> dict[str, Any]:
    brush_name = args.get("brush") or "Draw"
    size = args.get("size")
    strength = args.get("strength")
    try:
        if context.mode != "SCULPT":
            bpy.ops.object.mode_set(mode="SCULPT")
        brush = bpy.data.brushes.get(brush_name)
        if brush and hasattr(context.tool_settings, "sculpt"):
            context.tool_settings.sculpt.brush = brush
            if size is not None:
                brush.size = int(size)
            if strength is not None:
                brush.strength = float(strength)
        # Optional simple stroke: inflate along normals via mesh op approximation
        if args.get("stroke") == "inflate":
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.transform.shrink_fatten(value=float(args.get("amount") or 0.05))
            bpy.ops.object.mode_set(mode="SCULPT")
        return {"ok": True, "brush": brush_name}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _clear_object_animation(obj) -> None:
    if obj.animation_data:
        obj.animation_data_clear()


def _set_bezier_interpolation(obj) -> None:
    _set_fcurve_interpolation(obj, "BEZIER")


def _iter_datablock_fcurves(datablock) -> list[Any]:
    """Collect F-Curves for an ID across Blender 4.x legacy and 5.x layered Actions."""
    ad = getattr(datablock, "animation_data", None)
    if not ad or not ad.action:
        return []
    action = ad.action
    fcurves: list[Any] = []
    # Blender 5.x / slotted Actions
    try:
        layers = getattr(action, "layers", None)
        slots = getattr(action, "slots", None)
        slot = getattr(ad, "action_slot", None)
        if layers and len(layers) and slots is not None:
            strip = layers[0].strips[0]
            candidates = [slot] if slot is not None else list(slots)
            for s in candidates:
                if s is None:
                    continue
                try:
                    bag = strip.channelbag(s)
                except Exception:
                    bag = None
                if bag is not None:
                    fcurves.extend(list(bag.fcurves))
            if fcurves:
                return fcurves
    except Exception:
        pass
    # Legacy Action.fcurves proxy (removed in Blender 5.0+)
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        try:
            return list(legacy)
        except Exception:
            return []
    return fcurves


def _insert_loc_rot(obj, frame: int) -> None:
    obj.keyframe_insert(data_path="location", frame=frame)
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def _set_fcurve_interpolation(obj, interpolation: str = "BEZIER") -> None:
    for fcurve in _iter_datablock_fcurves(obj):
        for kp in fcurve.keyframe_points:
            kp.interpolation = interpolation
            if interpolation == "BEZIER":
                try:
                    kp.handle_left_type = "AUTO_CLAMPED"
                    kp.handle_right_type = "AUTO_CLAMPED"
                except Exception:
                    pass


def _apply_modifier_props(obj, modifiers_spec: Any) -> list[str]:
    """Set modifier properties and return RNA data_paths for keyframing.

    modifiers_spec: {"Waves": {"time": 1.5}} or [{"name":"Waves","time":1.5}]
    """
    paths: list[str] = []
    if not modifiers_spec:
        return paths
    items: list[tuple[str, dict[str, Any]]] = []
    if isinstance(modifiers_spec, dict):
        for mod_name, props in modifiers_spec.items():
            if isinstance(props, dict):
                items.append((str(mod_name), props))
    elif isinstance(modifiers_spec, list):
        for entry in modifiers_spec:
            if not isinstance(entry, dict):
                continue
            mod_name = str(entry.get("name") or entry.get("modifier") or "")
            if not mod_name:
                continue
            props = {k: v for k, v in entry.items() if k not in {"name", "modifier"}}
            items.append((mod_name, props))
    for mod_name, props in items:
        mod = obj.modifiers.get(mod_name)
        if not mod:
            continue
        for key, value in props.items():
            if not hasattr(mod, key):
                continue
            try:
                setattr(mod, key, value)
                paths.append(f'modifiers["{mod_name}"].{key}')
            except Exception:
                pass
    return paths


def _anim_keyframes(args: dict[str, Any], context) -> dict[str, Any]:
    """Insert or clear keyframes on one or more objects (Blender 5.x safe)."""
    op = (args.get("op") or args.get("action") or "insert").lower()
    names = list(args.get("objects") or args.get("names") or [])
    if args.get("object"):
        names.append(str(args["object"]))
    if args.get("name") and str(args["name"]) not in names:
        names.append(str(args["name"]))
    if not names and context.active_object:
        names = [context.active_object.name]
    if not names:
        return {"ok": False, "error": "No objects specified"}

    paths = args.get("data_paths") or args.get("paths")
    if isinstance(paths, str):
        paths = [paths]
    if not paths:
        paths = []
        if args.get("data_path"):
            paths.append(str(args["data_path"]))
        # Explicit booleans / presence
        if args.get("location") is True or (
            isinstance(args.get("location"), (list, tuple)) and "keyframes" not in args
        ):
            paths.append("location")
        if args.get("rotation") or args.get("rotation_euler"):
            paths.append("rotation_euler")
        if args.get("scale") is True or isinstance(args.get("scale"), (list, tuple)):
            paths.append("scale")
        if args.get("modifiers"):
            # Modifier paths are resolved per object when applying props
            pass
        elif not paths:
            paths = ["location", "rotation_euler"]
    # dedupe
    paths = list(dict.fromkeys(str(p) for p in paths))

    frame = int(args.get("frame") or context.scene.frame_current)
    interpolation = str(args.get("interpolation") or "BEZIER").upper()
    touched: list[str] = []
    keyframed = 0
    used_paths: list[str] = list(paths)

    for name in names:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        if op in {"clear", "delete", "remove"}:
            _clear_object_animation(obj)
            if getattr(obj, "data", None) is not None and args.get("clear_data", True):
                try:
                    _clear_object_animation(obj.data)
                except Exception:
                    pass
            touched.append(obj.name)
            continue

        # Batch keyframes: args.keyframes = [{frame, location?, rotation?, scale?, modifiers?}, ...]
        batch = args.get("keyframes") or args.get("keys")
        if isinstance(batch, list) and batch:
            for item in batch:
                if not isinstance(item, dict):
                    continue
                f = int(item.get("frame") or frame)
                if "location" in item:
                    obj.location = _as_vec3(item["location"], tuple(obj.location))
                if "rotation" in item or "rotation_euler" in item:
                    obj.rotation_euler = _as_vec3(
                        item.get("rotation") or item.get("rotation_euler"),
                        tuple(obj.rotation_euler),
                    )
                if "scale" in item:
                    obj.scale = _as_vec3(item["scale"], tuple(obj.scale))
                item_paths = list(paths)
                if "modifiers" in item:
                    mod_paths = _apply_modifier_props(obj, item.get("modifiers"))
                    item_paths = list(dict.fromkeys(item_paths + mod_paths))
                    used_paths = list(dict.fromkeys(used_paths + mod_paths))
                # Default transform paths when batch has loc/rot/scale but no explicit data_paths
                if not item_paths:
                    if "location" in item:
                        item_paths.append("location")
                    if "rotation" in item or "rotation_euler" in item:
                        item_paths.append("rotation_euler")
                    if "scale" in item:
                        item_paths.append("scale")
                for path in item_paths:
                    try:
                        obj.keyframe_insert(data_path=path, frame=f)
                        keyframed += 1
                    except Exception:
                        pass
            try:
                _set_fcurve_interpolation(obj, interpolation)
            except Exception:
                pass
            touched.append(obj.name)
            continue

        if "location" in args and isinstance(args.get("location"), (list, tuple)):
            obj.location = _as_vec3(args["location"], tuple(obj.location))
        if "rotation" in args or "rotation_euler" in args:
            obj.rotation_euler = _as_vec3(
                args.get("rotation") or args.get("rotation_euler"),
                tuple(obj.rotation_euler),
            )
        if "scale" in args and isinstance(args.get("scale"), (list, tuple)):
            obj.scale = _as_vec3(args["scale"], tuple(obj.scale))
        insert_paths = list(paths)
        if args.get("modifiers"):
            mod_paths = _apply_modifier_props(obj, args.get("modifiers"))
            insert_paths = list(dict.fromkeys(insert_paths + mod_paths))
            used_paths = list(dict.fromkeys(used_paths + mod_paths))
        for path in insert_paths:
            try:
                obj.keyframe_insert(data_path=path, frame=frame)
                keyframed += 1
            except Exception:
                pass
        # Optional camera lens key on data block
        if obj.type == "CAMERA" and "lens" in args and obj.data:
            obj.data.lens = float(args["lens"])
            try:
                obj.data.keyframe_insert(data_path="lens", frame=frame)
                keyframed += 1
            except Exception:
                pass
        try:
            _set_fcurve_interpolation(obj, interpolation)
            if obj.type == "CAMERA" and obj.data:
                _set_fcurve_interpolation(obj.data, interpolation)
        except Exception:
            pass
        touched.append(obj.name)

    if not touched:
        return {"ok": False, "error": f"No matching objects: {', '.join(names)}"}
    return {
        "ok": True,
        "op": op,
        "objects": touched,
        "frame": frame,
        "data_paths": used_paths,
        "keyframe_inserts": keyframed,
        "interpolation": interpolation,
    }


def _blender_introspect(args: dict[str, Any], context) -> dict[str, Any]:
    """Read-only Blender capability snapshot for adaptive prompting (never executes ops)."""
    scene = context.scene
    domain = str(args.get("domain") or args.get("topic") or "").lower()
    active = context.active_object
    addons: list[str] = []
    try:
        prefs = context.preferences.addons
        for mod in list(prefs.keys())[:40]:
            addons.append(str(mod))
    except Exception:
        pass

    operator_hints: dict[str, list[str]] = {
        "animation": [
            "keyframe_insert location/rotation_euler",
            "animation_data_clear",
            "TRACK_TO constraint on camera",
            "layered Actions / channelbag fcurves (Blender 5.x)",
        ],
        "lighting": [
            "AREA softboxes with size/size_y",
            "world Background strength/color",
            "look-at via light local -Z",
        ],
        "camera": [
            "camera looks down local -Z",
            "TRACK_TO track=-Z up=Y",
            "animate camera.data.lens separately",
        ],
        "render": [
            "BLENDER_EEVEE / CYCLES",
            "render.use_motion_blur + shutter",
            "scene.render.fps / frame_start / frame_end",
        ],
        "modeling": [
            "mesh primitives via ops",
            "edit-mode extrude/bevel/inset",
            "modifiers SUBSURF/BEVEL/BOOLEAN",
        ],
    }
    hints = operator_hints.get(domain) or []
    if not hints and domain:
        for key, vals in operator_hints.items():
            if key in domain or domain in key:
                hints = vals
                break
    if args.get("include_all_hints"):
        hints = sorted({h for vals in operator_hints.values() for h in vals})

    active_info = None
    if active:
        active_info = {
            "name": active.name,
            "type": active.type,
            "location": list(active.location),
            "dimensions": list(active.dimensions) if hasattr(active, "dimensions") else None,
            "has_animation": bool(getattr(active, "animation_data", None) and active.animation_data.action),
        }
        if active.type == "MESH" and active.data:
            active_info["verts"] = len(active.data.vertices)
            active_info["polygons"] = len(active.data.polygons)

    return {
        "ok": True,
        "read_only": True,
        "blender_version": list(bpy.app.version),
        "blender_version_string": bpy.app.version_string,
        "engine": scene.render.engine,
        "fps": int(scene.render.fps),
        "frame_current": int(scene.frame_current),
        "frame_start": int(scene.frame_start),
        "frame_end": int(scene.frame_end),
        "mode": context.mode,
        "active_object": active_info,
        "object_count": len(scene.objects),
        "addons_sample": addons[:20],
        "domain": domain or None,
        "operator_hints": hints,
        "note": "Introspection is read-only. Execute scene changes only via allowlisted tools.",
    }


def _ensure_ground_plane(context, name: str = "CourtFloor", size: float = 40.0) -> str:
    existing = bpy.data.objects.get(name)
    if existing:
        return existing.name
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0.0, 0.0, 0.0))
    ground = context.active_object
    if ground:
        ground.name = name
    mat = bpy.data.materials.get("CourtFloorMat") or bpy.data.materials.new("CourtFloorMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.12, 0.12, 0.13, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.85
    if ground and ground.data:
        if ground.data.materials:
            ground.data.materials[0] = mat
        else:
            ground.data.materials.append(mat)
    return ground.name if ground else name


def _enable_motion_blur(scene, shutter: float = 0.55) -> dict[str, Any]:
    enabled: dict[str, Any] = {"shutter": shutter}
    try:
        scene.render.use_motion_blur = True
        scene.render.motion_blur_shutter = float(shutter)
        enabled["render"] = True
    except Exception:
        enabled["render"] = False
    eevee = getattr(scene, "eevee", None)
    if eevee is not None:
        for attr, value in (
            ("use_motion_blur", True),
            ("motion_blur_shutter", float(shutter)),
            ("motion_blur_max", 32),
            ("motion_blur_steps", 1),
        ):
            if hasattr(eevee, attr):
                try:
                    setattr(eevee, attr, value)
                    enabled[attr] = value
                except Exception:
                    pass
    return enabled


def _simulate_throw_bounce(
    *,
    start: list[float],
    velocity: list[float],
    gravity: float,
    restitution: float,
    friction: float,
    ground_z: float,
    radius: float,
    fps: float,
    frame_count: int,
    spin_axis: list[float],
) -> list[tuple[int, list[float], list[float]]]:
    """Forward-Euler ballistic path with ground contact bounce."""
    dt = 1.0 / max(fps, 1.0)
    pos = [float(start[0]), float(start[1]), float(start[2])]
    vel = [float(velocity[0]), float(velocity[1]), float(velocity[2])]
    rot = [0.0, 0.0, 0.0]
    axis = spin_axis[:] if len(spin_axis) >= 3 else [1.0, 0.0, 0.0]
    samples: list[tuple[int, list[float], list[float]]] = []
    for i in range(frame_count):
        frame = i + 1
        samples.append((frame, pos[:], rot[:]))
        vel[2] += gravity * dt
        pos[0] += vel[0] * dt
        pos[1] += vel[1] * dt
        pos[2] += vel[2] * dt
        speed = math.sqrt(vel[0] * vel[0] + vel[1] * vel[1] + vel[2] * vel[2])
        spin = speed * 0.55 * dt
        rot[0] += axis[0] * spin
        rot[1] += axis[1] * spin
        rot[2] += axis[2] * spin
        contact = ground_z + radius
        if pos[2] <= contact and vel[2] < 0.0:
            pos[2] = contact
            vel[2] = -vel[2] * restitution
            vel[0] *= friction
            vel[1] *= friction
            if abs(vel[2]) < 0.35:
                vel[2] = 0.0
                pos[2] = contact
    return samples


def _anim_throw_bounce(args: dict[str, Any], context) -> dict[str, Any]:
    """Bake a throw + multi-bounce with cinematic camera follow and motion blur."""
    scene = context.scene
    obj_name = args.get("object") or args.get("name") or "Basketball"
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return {"ok": False, "error": f"Object not found: {obj_name}"}

    fps = float(args.get("fps") or scene.render.fps or 24)
    scene.render.fps = int(fps)
    duration_s = float(args.get("duration") or 4.0)
    frame_count = int(args.get("frames") or max(24, round(duration_s * fps)))
    frame_start = int(args.get("frame_start") or 1)
    frame_end = frame_start + frame_count - 1

    radius = float(args.get("radius") or max(obj.dimensions.z * 0.5, 0.5))
    ground_z = float(args.get("ground_z") or 0.0)
    start = _as_vec3(args.get("start") or args.get("start_location"), (-10.0, 0.0, max(3.5, radius + 2.0)))
    velocity = _as_vec3(args.get("velocity"), (11.0, 0.35, 6.5))
    gravity = float(args.get("gravity") or -18.0)
    restitution = float(args.get("restitution") or 0.68)
    friction = float(args.get("friction") or 0.9)
    spin_axis = _as_vec3(args.get("spin_axis"), (0.0, 1.0, 0.15))

    ground_name = None
    if args.get("create_ground", True):
        ground_name = _ensure_ground_plane(
            context,
            name=str(args.get("ground") or "CourtFloor"),
            size=float(args.get("ground_size") or 50.0),
        )

    samples = _simulate_throw_bounce(
        start=start,
        velocity=velocity,
        gravity=gravity,
        restitution=restitution,
        friction=friction,
        ground_z=ground_z,
        radius=radius,
        fps=fps,
        frame_count=frame_count,
        spin_axis=spin_axis,
    )

    _ensure_object_mode(context)
    _clear_object_animation(obj)

    # Prefer shared anim.keyframes primitive for the baked path
    batch = [
        {
            "frame": frame_start + frame_i - 1,
            "location": loc,
            "rotation": rot,
        }
        for frame_i, loc, rot in samples
    ]
    kf = _anim_keyframes(
        {
            "object": obj.name,
            "op": "insert",
            "keyframes": batch,
            "data_paths": ["location", "rotation_euler"],
            "interpolation": "LINEAR",
        },
        context,
    )
    if not kf.get("ok"):
        return kf

    cam_name = str(args.get("camera") or "ThrowCam")
    target_name = str(args.get("camera_target") or "ThrowCamTarget")
    cam = bpy.data.objects.get(cam_name)
    if not cam or cam.type != "CAMERA":
        data = bpy.data.cameras.new(name=cam_name)
        cam = bpy.data.objects.new(cam_name, data)
        context.collection.objects.link(cam)
    target = bpy.data.objects.get(target_name)
    if not target:
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=start)
        target = context.active_object
        if target:
            target.name = target_name
            target.empty_display_size = 0.35

    _clear_object_animation(cam)
    if cam.type == "CAMERA" and cam.data:
        _clear_object_animation(cam.data)
    if target:
        _clear_object_animation(target)

    for c in list(cam.constraints):
        if c.type in {"TRACK_TO", "DAMPED_TRACK", "COPY_LOCATION"}:
            cam.constraints.remove(c)
    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    cam_offset = _as_vec3(args.get("camera_offset"), (-2.8, -7.5, 3.2))
    lead_frames = int(args.get("camera_lead_frames") or 4)
    lag_frames = int(args.get("camera_lag_frames") or 3)
    push_in = float(args.get("camera_push") or 0.35)

    for idx, (frame_i, loc, _rot) in enumerate(samples):
        f = frame_start + frame_i - 1
        lead_idx = min(len(samples) - 1, idx + lead_frames)
        lag_idx = max(0, idx - lag_frames)
        lead_loc = samples[lead_idx][1]
        lag_loc = samples[lag_idx][1]
        look = [
            lag_loc[0] * 0.35 + lead_loc[0] * 0.65,
            lag_loc[1] * 0.35 + lead_loc[1] * 0.65,
            lag_loc[2] * 0.25 + lead_loc[2] * 0.75 + 0.35,
        ]
        if target:
            target.location = look
            target.keyframe_insert(data_path="location", frame=f)

        t = idx / max(len(samples) - 1, 1)
        ease = t * t * (3.0 - 2.0 * t)
        scale = 1.0 - push_in * ease
        cam.location = (
            loc[0] + cam_offset[0] * scale,
            loc[1] + cam_offset[1] * scale,
            max(loc[2] + cam_offset[2] * (0.85 + 0.15 * ease), radius + 1.2),
        )
        cam.keyframe_insert(data_path="location", frame=f)

        if cam.type == "CAMERA" and cam.data:
            cam.data.lens = float(args.get("lens") or 35.0) + 12.0 * ease
            cam.data.keyframe_insert(data_path="lens", frame=f)

    try:
        _set_fcurve_interpolation(cam, "BEZIER")
        if cam.type == "CAMERA" and cam.data:
            _set_fcurve_interpolation(cam.data, "BEZIER")
        if target:
            _set_fcurve_interpolation(target, "BEZIER")
    except Exception:
        pass

    scene.camera = cam
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.frame_set(frame_start)

    blur: dict[str, Any] = {}
    if args.get("motion_blur", True):
        blur = _enable_motion_blur(scene, shutter=float(args.get("shutter") or 0.55))

    if args.get("set_engine", True):
        engine = str(args.get("engine") or "BLENDER_EEVEE").upper()
        try:
            scene.render.engine = engine
        except Exception:
            try:
                scene.render.engine = "BLENDER_EEVEE_NEXT"
            except Exception:
                pass

    if args.get("viewport_camera", True):
        for area in context.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.region_3d.view_perspective = "CAMERA"
                    if args.get("shading"):
                        space.shading.type = str(args["shading"]).upper()
                    elif args.get("motion_blur", True):
                        space.shading.type = "RENDERED"

    played = False
    # Default off: timer-driven bridge context often lacks screen; callers opt in.
    if args.get("play", False):
        played = _animation_play_safe(context, play=True)

    return {
        "ok": True,
        "object": obj.name,
        "camera": cam.name,
        "camera_target": target.name if target else None,
        "ground": ground_name,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "fps": int(fps),
        "samples": len(samples),
        "motion_blur": blur,
        "start": start,
        "velocity": velocity,
        "playing": played,
    }


def _anim_walk_to_camera(args: dict[str, Any], context) -> dict[str, Any]:
    """Bake a cute walk cycle toward the active/front camera."""
    body_name = args.get("object") or args.get("name") or "Bird_Body"
    cam_name = args.get("camera") or "Bird_Camera"
    body = bpy.data.objects.get(body_name)
    cam = bpy.data.objects.get(cam_name)
    if not body:
        return {"ok": False, "error": f"Object not found: {body_name}"}

    scene = context.scene
    fps = int(args.get("fps") or 24)
    scene.render.fps = fps
    start = int(args.get("start_frame") or 1)
    frames = int(args.get("frames") or 48)
    end = start + frames - 1
    scene.frame_start = start
    scene.frame_end = end

    if cam and args.get("set_active_camera", True):
        scene.camera = cam

    if args.get("start_location"):
        body.location = tuple(args["start_location"])
    start_loc = list(body.location)

    walk_distance = float(args.get("distance") or 2.0)
    from mathutils import Vector

    if cam:
        bpos = Vector(body.location)
        cpos = Vector(cam.location)
        delta = Vector((cpos.x - bpos.x, cpos.y - bpos.y, 0.0))
        if delta.length > 1e-6:
            direction = delta.normalized()
            travel = min(walk_distance, delta.length * 0.7)
            end_loc = list(bpos + direction * travel)
        else:
            end_loc = [start_loc[0], start_loc[1] - walk_distance, start_loc[2]]
    else:
        end_loc = [start_loc[0], start_loc[1] - walk_distance, start_loc[2]]

    targets = [body]
    for part in ("Foot_L", "Foot_R", "Wing_L", "Wing_R"):
        part_obj = bpy.data.objects.get(part)
        if part_obj:
            targets.append(part_obj)

    if args.get("clear_existing", True):
        for obj in targets:
            _clear_object_animation(obj)

    base_rots = {obj.name: list(obj.rotation_euler) for obj in targets}
    base_locs = {obj.name: list(obj.location) for obj in targets}

    for f in range(start, end + 1):
        scene.frame_set(f)
        t = (f - start) / max(frames - 1, 1)
        bob = math.sin(t * math.pi * 8)
        sway = math.sin(t * math.pi * 4)

        body.location = (
            start_loc[0] + (end_loc[0] - start_loc[0]) * t,
            start_loc[1] + (end_loc[1] - start_loc[1]) * t,
            start_loc[2] + bob * 0.035,
        )
        body.rotation_euler = (bob * 0.04, 0.0, sway * 0.02)
        body.keyframe_insert(data_path="location", frame=f)
        body.keyframe_insert(data_path="rotation_euler", frame=f)

        for foot_name, phase in (("Foot_L", 0.0), ("Foot_R", 0.5)):
            foot = bpy.data.objects.get(foot_name)
            if not foot:
                continue
            base = base_locs[foot.name]
            step = max(0.0, math.sin((t * 8 + phase) * math.pi * 2))
            foot.location = (base[0], base[1], base[2] + step * 0.06)
            foot.keyframe_insert(data_path="location", frame=f)

        for wing_name, phase in (("Wing_L", 0.0), ("Wing_R", math.pi)):
            wing = bpy.data.objects.get(wing_name)
            if not wing:
                continue
            base = base_rots[wing.name]
            flap = math.sin((t * 6 + phase / math.pi) * math.pi) * 0.08
            wing.rotation_euler = (base[0] + flap, base[1], base[2])
            wing.keyframe_insert(data_path="rotation_euler", frame=f)

    for obj in targets:
        _set_bezier_interpolation(obj)

    scene.frame_set(start)
    return {
        "ok": True,
        "object": body.name,
        "camera": cam.name if cam else None,
        "start_frame": start,
        "end_frame": end,
        "start_location": start_loc,
        "end_location": end_loc,
        "fps": fps,
    }


def _wm_play_override(context) -> dict[str, Any] | None:
    """Resolve window/screen(/area) for operators that require a UI context.

    Tools often run from ``bpy.app.timers`` via ``blender_ai.execute_tool``. That
    path can leave ``context.screen`` null; ``bpy.ops.screen.animation_play`` then
    crashes inside ``ED_screen_animation_play`` (ACCESS_VIOLATION on Windows).
    """
    window = getattr(context, "window", None)
    screen = getattr(context, "screen", None)
    if window is None or screen is None:
        wm = getattr(context, "window_manager", None) or bpy.context.window_manager
        windows = getattr(wm, "windows", None) if wm else None
        if not windows:
            return None
        window = windows[0]
        screen = window.screen
    if window is None or screen is None:
        return None
    override: dict[str, Any] = {"window": window, "screen": screen}
    for area in screen.areas:
        if area.type == "VIEW_3D":
            override["area"] = area
            for region in area.regions:
                if region.type == "WINDOW":
                    override["region"] = region
                    break
            break
    return override


def _animation_play_safe(context, *, play: bool = True) -> bool:
    """Toggle playback only with a valid screen override. Never call bare ops.play."""
    override = _wm_play_override(context)
    if override is None:
        return False
    screen = override["screen"]
    playing = bool(getattr(screen, "is_animation_playing", False))
    if play and playing:
        return True
    if not play and not playing:
        return True
    try:
        with context.temp_override(**override):
            bpy.ops.screen.animation_play()
        return True
    except Exception:
        return False


def _anim_play(args: dict[str, Any], context) -> dict[str, Any]:
    scene = context.scene
    start = int(args.get("start_frame") or scene.frame_start)
    end = int(args.get("end_frame") or scene.frame_end)
    scene.frame_start = start
    scene.frame_end = end
    scene.frame_set(start)
    want_play = bool(args.get("play", True))
    if want_play and not _animation_play_safe(context, play=True):
        return {
            "ok": False,
            "error": "Animation play requires an open Blender window/screen context",
            "playing": False,
            "frame_start": start,
            "frame_end": end,
        }
    if not want_play:
        _animation_play_safe(context, play=False)
    return {"ok": True, "playing": want_play, "frame_start": start, "frame_end": end}


def _anim_set_frame(args: dict[str, Any], context) -> dict[str, Any]:
    frame = int(args.get("frame") or context.scene.frame_current)
    context.scene.frame_set(frame)
    if args.get("shading"):
        _viewport_set_shading({"mode": args["shading"]}, context)
    return {"ok": True, "frame": frame}
