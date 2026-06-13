# Noesis Plugin Pack — Star Conflict Asset Extraction

## Dependencies

- **Noesis** 4.x+ (Rich Whitehouse) — https://richwhitehouse.com/
- Copy plugins to `Noesis\plugins\python\`

## Plugins

| File | Role |
|------|------|
| `tex_StarConflict_tfh_tfd_v2.py` | TFH/TFD texture loader (byte-level header + fallback) |
| `inc_starconflict_msh.py` | Shared MSH loader logic |
| `fmt_StarConflict_msh_A~Z.py` ×26 | Extension registration shells (.msh000~987, 99.5%) |

## Installation

Copy all `.py` files to `Noesis\plugins\python\`.

## Notes

- Noesis uses embedded **Python 3.2** (`core321.zip`)
- **Delete `__pycache__/`** after every `.py` change
- Noesis max ~26 Python plugins; `.msh988+` use `msh_to_obj_v3.py` CLI

## Known Issues

| Issue | Scope | Status |
|-------|-------|--------|
| `_s1` non-square textures (BC5/ATI2) | Ship equipment decals, all unresolved | ❌ Unresolved |
| `_s` new-format specular textures | New format mapping incomplete, partial support | ⚠️ Partial |
| Background/level textures (irradiance etc.) | Cubemap, missing TFD + complex headers | ❌ Unresolved |
| VBytes=40 flag=0x10 character models | UV offset unverified (does not affect ships) | ⚠️ Pending |
| Font textures (R8/L8/ARGB) | 70/70 fonts, 24-byte TFH header | ✅ Resolved (v2.1) |

## Archived (`_archived/`)

Original community scripts + earlier versions.
