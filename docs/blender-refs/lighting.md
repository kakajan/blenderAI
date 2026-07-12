# Lighting (Blender 5.1)

## Light types

`POINT`, `SUN`, `SPOT`, `AREA`. Studio setups prefer large `AREA` softboxes.

## Area softbox tips

- Set `size` / `size_y` large for soft shadows.
- Aim with Track-To style look-at (light local −Z toward subject).
- Classic ratio: Key ≫ Fill; Rim slightly cooler or warmer for separation.

## World

- Background shader color + strength for ambient fill.
- HDRI via Environment Texture → Background (BlenderAI: `world.hdri_set`).

## BlenderAI tools

- `light.set` — type, energy, color, size, look_at
- `world.set` / `world.hdri_set`
- Skill: `lighting.three_point`, `lighting.hdri_setup`
