from __future__ import annotations

from typing import Any

import bpy

from ..context import scene as scene_ctx


def run_tool(tool: str, args: dict[str, Any], context) -> dict[str, Any]:
    try:
        if tool == "scene.summary":
            return {"ok": True, "summary": scene_ctx.build_summary(context)}
        if tool == "viewport.capture":
            path = scene_ctx.capture_viewport(context)
            return {"ok": True, "path": path}
        if tool == "undo":
            bpy.ops.ed.undo()
            return {"ok": True}
        if tool == "redo":
            bpy.ops.ed.redo()
            return {"ok": True}
        if tool == "scene.create_object":
            return _create_object(args, context)
        if tool == "selection.set":
            return _selection_set(args, context)
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
        if tool == "collection.organize":
            return _collection_organize(args, context)
        if tool == "render.set":
            return _render_set(args, context)
        if tool == "mesh.ops":
            return _mesh_ops(args, context)
        if tool == "sculpt.set_brush":
            return _sculpt_brush(args, context)
        if tool == "node.set":
            return {"ok": True, "note": "node.set acknowledged", "args": args}
        if tool == "nodes.geometry_set":
            return {"ok": True, "note": "geometry nodes stub", "args": args}
        return {"ok": False, "error": f"Unknown tool: {tool}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _create_object(args: dict[str, Any], context) -> dict[str, Any]:
    kind = (args.get("type") or args.get("primitive") or "cube").lower()
    name = args.get("name") or kind.capitalize()
    loc = args.get("location") or [0, 0, 0]
    scale = args.get("scale") or [1, 1, 1]
    size = float(args.get("size") or 2.0)
    mapping = {
        "cube": lambda: bpy.ops.mesh.primitive_cube_add(size=size, location=loc),
        "uv_sphere": lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=size / 2, location=loc),
        "sphere": lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=size / 2, location=loc),
        "cylinder": lambda: bpy.ops.mesh.primitive_cylinder_add(radius=size / 2, depth=size, location=loc),
        "cone": lambda: bpy.ops.mesh.primitive_cone_add(radius1=size / 2, depth=size, location=loc),
        "torus": lambda: bpy.ops.mesh.primitive_torus_add(location=loc),
        "plane": lambda: bpy.ops.mesh.primitive_plane_add(size=size, location=loc),
        "monkey": lambda: bpy.ops.mesh.primitive_monkey_add(size=size, location=loc),
    }
    fn = mapping.get(kind, mapping["cube"])
    fn()
    obj = context.active_object
    if obj:
        obj.name = name
        if scale != [1, 1, 1]:
            obj.scale = scale
    return {"ok": True, "name": obj.name if obj else name, "type": kind}


def _selection_set(args: dict[str, Any], context) -> dict[str, Any]:
    names = args.get("names") or args.get("objects") or []
    mode = args.get("mode") or "replace"
    if mode == "replace":
        bpy.ops.object.select_all(action="DESELECT")
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.select_set(True)
            context.view_layer.objects.active = obj
    return {"ok": True, "selected": names}


def _modifier_add(args: dict[str, Any], context) -> dict[str, Any]:
    obj = context.active_object
    if not obj:
        return {"ok": False, "error": "No active object"}
    mod_type = (args.get("type") or "BEVEL").upper()
    name = args.get("name") or mod_type.title()
    mod = obj.modifiers.new(name=name, type=mod_type)
    for k, v in (args.get("props") or {}).items():
        if hasattr(mod, k):
            setattr(mod, k, v)
    return {"ok": True, "modifier": mod.name}


def _modifier_apply(args: dict[str, Any], context) -> dict[str, Any]:
    obj = context.active_object
    if not obj:
        return {"ok": False, "error": "No active object"}
    name = args.get("name")
    if name and name in obj.modifiers:
        bpy.ops.object.modifier_apply(modifier=name)
        return {"ok": True, "applied": name}
    return {"ok": False, "error": "Modifier not found"}


def _material_create(args: dict[str, Any], context) -> dict[str, Any]:
    name = args.get("name") or "AI_Material"
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf:
        color = args.get("base_color") or args.get("color") or [0.8, 0.8, 0.8, 1.0]
        if len(color) == 3:
            color = list(color) + [1.0]
        bsdf.inputs["Base Color"].default_value = color
        if "roughness" in args:
            bsdf.inputs["Roughness"].default_value = float(args["roughness"])
        if "metallic" in args:
            bsdf.inputs["Metallic"].default_value = float(args["metallic"])
    return {"ok": True, "material": mat.name}


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
    energy = float(args.get("energy") or 100.0)
    loc = args.get("location") or [3, -3, 5]
    existing = bpy.data.objects.get(name)
    if existing and existing.type == "LIGHT":
        existing.data.energy = energy
        existing.location = loc
        return {"ok": True, "light": name, "updated": True}
    light_data = bpy.data.lights.new(name=name, type=light_type if light_type in {"POINT", "SUN", "SPOT", "AREA"} else "AREA")
    light_data.energy = energy
    obj = bpy.data.objects.new(name=name, object_data=light_data)
    context.collection.objects.link(obj)
    obj.location = loc
    return {"ok": True, "light": name}


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
    if "engine" in args:
        engine = args["engine"]
        if engine in {"CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"}:
            scene.render.engine = engine
    if "samples" in args and hasattr(scene.cycles, "samples"):
        scene.cycles.samples = int(args["samples"])
    if "resolution_x" in args:
        scene.render.resolution_x = int(args["resolution_x"])
    if "resolution_y" in args:
        scene.render.resolution_y = int(args["resolution_y"])
    return {"ok": True, "engine": scene.render.engine}


def _mesh_ops(args: dict[str, Any], context) -> dict[str, Any]:
    op = (args.get("op") or "").lower()
    obj = context.active_object
    if not obj or obj.type != "MESH":
        return {"ok": False, "error": "Active mesh required"}
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        if op in {"bevel",}:
            bpy.ops.mesh.bevel(offset=float(args.get("offset") or 0.02), segments=int(args.get("segments") or 2))
        elif op in {"extrude",}:
            bpy.ops.mesh.extrude_region_move(
                TRANSFORM_OT_translate={"value": tuple(args.get("offset") or [0, 0, 0.2])}
            )
        elif op in {"inset",}:
            bpy.ops.mesh.inset(thickness=float(args.get("thickness") or 0.05))
        elif op in {"subdivide",}:
            bpy.ops.mesh.subdivide(number_cuts=int(args.get("cuts") or 1))
        elif op in {"remove_doubles", "merge_by_distance"}:
            bpy.ops.mesh.remove_doubles(threshold=float(args.get("threshold") or 0.0001))
        elif op in {"recalculate_normals", "normals"}:
            bpy.ops.mesh.normals_make_consistent(inside=False)
        else:
            return {"ok": False, "error": f"Unknown mesh op: {op}"}
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    return {"ok": True, "op": op}


def _sculpt_brush(args: dict[str, Any], context) -> dict[str, Any]:
    brush_name = args.get("brush") or "Draw"
    size = args.get("size")
    strength = args.get("strength")
    # Best-effort; sculpt paint settings vary by Blender version
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
        return {"ok": True, "brush": brush_name}
    except Exception as e:
        return {"ok": False, "error": str(e)}
