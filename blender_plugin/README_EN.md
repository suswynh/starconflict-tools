# Star Conflict MSH Importer — Blender Add-on

Import Hammer Engine (Star Conflict) `.mdl-mshXXX` static meshes into Blender.

**Compatible Versions**: Blender 4.2 LTS, Blender 5.0+

> **v2.1** (2026-06) — Fixed front axis: MSH front -Z→+Z, default up-axis changed to Z-up→Y-up. Import-ready for Blender.
> **Pro Edition** (`io_import_starconflict_msh_pro`) available: MDF material parsing, auto texture linking, Principled BSDF networks.

## Installation

### Method 1: ZIP Install (Recommended)

1. Package the `io_import_starconflict_msh` folder as a `.zip` (Right-click → Send to → Compressed folder)
2. Blender → Edit → Preferences → Add-ons → ▼ (top-right) → **Install from Disk...**
3. Select the `.zip` file
4. Search "Star Conflict", enable the checkbox

### Method 2: Manual Copy

Copy the `io_import_starconflict_msh` folder to the Blender addons directory:

```
# Windows (Blender 4.2)
%APPDATA%\Blender Foundation\Blender\4.2\scripts\addons\

# Windows (Blender 5.0)
%APPDATA%\Blender Foundation\Blender\5.0\scripts\addons\
```

Then enable it via Preferences → Add-ons.

## Usage

After installation, two options appear in **File → Import**:

### Import Star Conflict MSH (.mdl-msh*)
Import one or more MSH files.

| Option | Description |
|--------|-------------|
| Scale | Scale factor (default 1.0) |
| Join LOD Models | Group different LOD files of the same model |

### Import Star Conflict MSH Batch (directory)
Batch import all `.mdl-msh*` files from a directory.

| Option | Description |
|--------|-------------|
| Scale | Scale factor |
| Max Files | Maximum number of files to import (0 = unlimited) |
| Show Details | Print status of each file to console |

## Supported Formats

| VBytes | Usage |
|--------|-------|
| 20 | Basic mesh |
| 24 | Extended mesh |
| 28 | Scene objects |
| 32 | Medium mesh |
| 36 | Large mesh |
| 40 | Character model |
| 44 | Decoration model |

Number range: `.mdl-msh000` ~ `.mdl-msh1308`

## Exporting to FBX

After import, use Blender's built-in exporter:
**File → Export → FBX (.fbx)**

Recommended settings:
- Path Mode: `Copy` (copies textures alongside FBX)
- Scale: `1.00`
- Apply Scalings: `FBX All`

## File Structure

```
blender_plugin/
├── io_import_starconflict_msh/          # Basic edition (mesh import only)
│   └── __init__.py
├── io_import_starconflict_msh_pro/      # Pro edition (material pipeline)
│   ├── __init__.py
│   ├── msh_parser.py
│   ├── msh_importer.py
│   ├── mdf_parser.py
│   ├── material_builder.py
│   └── ...
├── io_import_starconflict_msh_pro.zip   # Pro edition ZIP package
└── README.md
```

## Using with msh2fbx

| Scenario | Recommended Tool |
|----------|-----------------|
| Batch convert all 62K files | `msh2fbx.exe --batch` |
| Preview a single model | Blender add-on |
| Manual editing/rigging needed | Blender add-on |
| Automated pipeline | `msh2fbx.exe` |

## Pro Edition Path Configuration

The Pro edition (`io_import_starconflict_msh_pro`) supports automatic texture linking with recursive sub-folder search.

| Setting | Recommended Path | Description |
|---------|-----------------|-------------|
| Texture Search Paths | `scunpack\tex_universe_check\` | Converted DDS textures |
| MDF Search Paths | `scunpack\output\` | MDF material definitions |
| Texture Extensions | `.dds,.png,.tga` | Extension priority |

> Pro edition uses **recursive search** (`os.walk`) — specify top-level directory only.
> See `io_import_starconflict_msh_pro/README_PRO.md` for full documentation.

---

## Pro Edition Notes

### Installation

| Item | Notes |
|------|-------|
| **Separate addon** | Pro and Basic are **separate addons** — do not bundle in same zip |
| **Can coexist** | Both can be enabled simultaneously without conflicts |
| **Folder name** | Pro: `io_import_starconflict_msh_pro`, install same as Basic |

### Prerequisites

Pro edition requires these resources for automatic material creation:

| Resource | Path | How to generate |
|----------|------|-----------------|
| DDS textures | `scunpack\tex_universe_check\` | `python batch_tex_all.py` |
| MDF files | `scunpack\output\` | `tpak_extract.py` extraction |

> ⚠️ Without textures, Pro edition still imports meshes but won't create materials (same as Basic).

### First-Time Setup

1. Install and enable the addon
2. **Edit → Preferences → Add-ons → Star Conflict MSH Importer Pro** → expand
3. Add **Texture Search Paths**: `<project>\scunpack\tex_universe_check`
4. Add **MDF Search Paths**: `<project>\scunpack\output`
5. Import MSH → enable **Auto-Link Materials**

> First import builds texture index (~11,628 DDS files), takes 5-10 seconds. Subsequent imports use cache.

### Known Limitations

| Limitation | Notes |
|------------|-------|
| Material slot mapping | MSH lacks face-material mapping; assigned by MDF block↔MSH index order |
| Shader restoration | Manual preset mapping, not automatic .fx parsing |
| Cubemap | EnvSampler / ReflectionsSampler not yet implemented |
| DDS compatibility | Some RGBA DDS may require Honeyview/GIMP |

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Pink/purple model | Textures not found | Check Texture Search Paths, clear cache |
| No materials created | MDF not found | Verify MDF is alongside MSH, or add MDF Search Path |
| Wrong textures | Cache stale | Sidebar → **Clear Texture Cache** |
