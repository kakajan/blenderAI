# Render (Blender 5.1)

## Engines

Common ids: `BLENDER_EEVEE`, `BLENDER_EEVEE_NEXT`, `CYCLES`. Prefer EEVEE for realtime viewport feedback.

## Motion blur

- Cycles / shared: `scene.render.use_motion_blur`, `motion_blur_shutter`
- EEVEE: `scene.eevee.use_motion_blur` when present

## Timeline

- `scene.render.fps`, `frame_start`, `frame_end`, `frame_set`

## BlenderAI tools

- `render.set` — engine, samples, resolution, fps, frames, motion_blur, shutter
- Skill: `render.optimize`
