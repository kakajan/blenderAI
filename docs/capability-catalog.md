# BlenderAI Capability Catalog

Product intents (what users ask for), mapped to bridge primitives and skills.
This is the source of truth for coverage gaps — **not** a dump of every `bpy.ops`.

Related: [architecture.md](architecture.md) · [blender-refs/](blender-refs/) · skills in `/skills`

Status legend: `done` · `partial` · `missing`  
Priority: `P0` (ship soon) · `P1` · `P2`

## Modeling

| Intent | Domain | Primitives | Skill / recipe | Status | Priority |
|--------|--------|------------|----------------|--------|----------|
| Add primitive (cube/sphere/…) | modeling | `scene.create_object` | `modeling.primitives` | done | P0 |
| Blockout from boxes | modeling | `scene.create_object`, `object.transform`, `object.join` | `modeling.blockout` | done | P0 |
| Extrude / inset / bevel | modeling | `mesh.ops`, `mesh.extrude`, `mesh.select` | `modeling.surface_advanced`, `modeling.modify_mesh` | done | P0 |
| Build mesh from verts/faces | modeling | `mesh.from_data` | `modeling.low_poly` | done | P0 |
| Profile extrude / edge loop | modeling | `mesh.profile_extrude`, `mesh.edge_loop` | `modeling.hardsurface` | done | P0 |
| Boolean / cleanup | modeling | `modifier.add`, `modifier.apply`, `mesh.ops` | `modeling.boolean`, `modeling.cleanup` | partial | P1 |
| Stylized character pipeline | modeling | surface + materials + capture | `modeling.character_stylized`, `modeling.turnaround_character` | done | P0 |
| Duplicate / delete / parent | modeling | `object.duplicate`, `object.delete`, `object.parent` | — | done | P0 |
| Selection set | modeling | `selection.set`, `mesh.select` | — | done | P0 |

## Materials & shading

| Intent | Domain | Primitives | Skill / recipe | Status | Priority |
|--------|--------|------------|----------------|--------|----------|
| Create / assign material | materials | `material.create`, `material.assign` | `materials.create_pbr` | done | P0 |
| From description / image maps | materials | `material.create`, `node.set` | `materials.from_description` | partial | P1 |
| Parametric principled tweaks | materials | `node.set` | — | partial | P1 |
| Fur / hair particles | materials | `particle.fur_set` | — | partial | P1 |

## Lighting

| Intent | Domain | Primitives | Skill / recipe | Status | Priority |
|--------|--------|------------|----------------|--------|----------|
| Three-point / studio softboxes | lighting | `light.set`, `world.set`, `collection.organize` | `lighting.three_point` | partial | P0 |
| HDRI environment | lighting | `world.hdri_set` | `lighting.hdri_setup` | done | P0 |
| World color / strength | lighting | `world.set` | — | done | P0 |
| Area light size / look-at / color | lighting | `light.set` | — | done | P0 |
| Light linking / portals | lighting | — | — | missing | P2 |

## Camera & viewport

| Intent | Domain | Primitives | Skill / recipe | Status | Priority |
|--------|--------|------------|----------------|--------|----------|
| Place camera + look-at | camera | `camera.set` | — | done | P0 |
| Track-To / follow target | camera | `camera.set` (`track_to`) | — | partial | P0 |
| DOF / focal animate | camera | `camera.set` | — | partial | P1 |
| Viewport shading | viewport | `viewport.set_shading` | — | done | P0 |
| Capture / turnaround | viewport | `viewport.capture` | `review.critique` | done | P0 |
| Reference image empty | scene | `scene.reference_image` | — | done | P1 |

## Animation

| Intent | Domain | Primitives | Skill / recipe | Status | Priority |
|--------|--------|------------|----------------|--------|----------|
| Insert location/rotation keyframes | animation | `anim.keyframes` | — | done | P0 |
| Clear object animation | animation | `anim.keyframes` (`clear`) | — | done | P0 |
| Set frame / play | animation | `anim.set_frame`, `anim.play` | — | done | P0 |
| Throw + bounce ballistics | animation | `anim.keyframes`, `anim.throw_bounce`, `camera.set`, `render.set` | recipe / adaptive | partial | P0 |
| Walk cycle helper | animation | `anim.walk_to_camera` | — | partial | P1 |
| Camera path follow + lead/lag | animation | `anim.keyframes`, `camera.set` | adaptive recipes | partial | P0 |
| Action / NLA editing | animation | — | — | missing | P2 |
| Rig / armature pose keys | animation | — | — | missing | P2 |

## Render

| Intent | Domain | Primitives | Skill / recipe | Status | Priority |
|--------|--------|------------|----------------|--------|----------|
| Engine / resolution / samples | render | `render.set` | `render.optimize` | done | P0 |
| Motion blur + shutter | render | `render.set` | — | done | P0 |
| FPS / frame range | render | `render.set` | — | done | P0 |
| Output path / format | render | — | — | missing | P1 |

## Nodes / sculpt / physics

| Intent | Domain | Primitives | Skill / recipe | Status | Priority |
|--------|--------|------------|----------------|--------|----------|
| Geometry Nodes templates | nodes | `nodes.geometry_set` | `nodes.geometry_basic` | partial | P1 |
| Sculpt brush / remesh | sculpt | `sculpt.set_brush`, `sculpt.remesh` | `sculpt.brush_assist` | partial | P1 |
| Rigid body / soft body bake | physics | — | — | missing | P1 |
| Cloth / particles (non-fur) | physics | — | — | missing | P2 |

## Scene / review / adaptive

| Intent | Domain | Primitives | Skill / recipe | Status | Priority |
|--------|--------|------------|----------------|--------|----------|
| Scene summary | scene | `scene.summary` | — | done | P0 |
| Blender introspect (read-only) | scene | `blender.introspect` | adaptive | done | P0 |
| Organize collections | scene | `collection.organize` | `scene.organize` | done | P0 |
| Undo / redo | scene | `undo`, `redo` | — | done | P0 |
| Critique / iterate | review | `viewport.capture` | `review.critique`, `review.iterate` | done | P0 |
| Personal recipes from past success | adaptive | LearningEngine | hot user skills | partial | P0 |
| Hot-load local user skills | adaptive | SkillEngine `user_skills` | — | done | P0 |
| Knowledge RAG (blender-refs) | adaptive | knowledge module | — | done | P0 |
| Record capability gaps | adaptive | LearningEngine / DB | — | done | P0 |

## P0 backlog (implementation checklist)

1. `anim.keyframes` — generic insert/clear/interpolation
2. `camera.set` — Track-To constraint + follow helpers
3. `render.set` — motion blur (done) keep unified
4. Refactor `anim.throw_bounce` to call `anim.keyframes` helpers internally
5. `blender.introspect` — version, engine, active RNA, domain operator hints
6. Knowledge retrieval from `docs/blender-refs/`
7. Capability gap recording when primitives missing
8. Evals covering catalog `done` intents

## How to extend

1. Add a row here first (intent + status `missing`).
2. Prefer a **primitive** if many intents need it.
3. Prefer a **skill/recipe** if composing existing primitives is enough.
4. Never add freeform Python execution as a tool.
