# Camera (Blender 5.1)

## Basics

- Camera looks down local −Z.
- `look_at` = set `rotation_euler` from direction vector with `to_track_quat("-Z", "Y")`.

## Follow / track

- Add `TRACK_TO` constraint to an Empty or object.
- For cinematic follow: keyframe camera location offset from subject; keyframe target with lead frames.

## Lens

- Animate `camera.data.lens` for push-ins (separate datablock animation_data).

## BlenderAI tools

- `camera.set` — location, look_at/target, lens, track_to, set_active
- Combine with `anim.keyframes` for paths
