# Animation (Blender 5.1)

## Keyframing

- Prefer `obj.keyframe_insert(data_path="location", frame=f)` / `rotation_euler`.
- Clearing: `obj.animation_data_clear()` (also clear `obj.data.animation_data` for camera lens keys).

## Layered / slotted Actions

In Blender 5.x, `Action.fcurves` is gone. F-Curves live in channelbags:

```text
action.layers[0].strips[0].channelbag(slot).fcurves
```

Also use `animation_data.action_slot` when present. BlenderAI helpers iterate fcurves via channelbags with a legacy fallback.

## Interpolation

- Ballistics / physics-baked paths: `LINEAR` on location fcurves.
- Cinematic camera: `BEZIER` with auto-clamped handles.

## Constraints for follow-cams

- `TRACK_TO`: track_axis `-Z`, up_axis `Y` for cameras.
- Animate an Empty as look-target with lead/lag for cinematic smoothing.

## BlenderAI tools

- `anim.keyframes` — insert/clear keys for location/rotation/scale/custom paths
- `anim.set_frame` / `anim.play`
- `anim.throw_bounce` — recipe-style ballistics helper built on keyframe helpers
- Playback: never call bare `bpy.ops.screen.animation_play()` from the bridge timer.
  Use a `window`/`screen` `temp_override` (see `_animation_play_safe`). Missing screen
  context crashes Blender (`ED_screen_animation_play` ACCESS_VIOLATION).
- `anim.throw_bounce` defaults `play` to `false`; pass `"play": true` only when a UI
  window is available.
