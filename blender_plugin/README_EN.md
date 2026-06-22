# Star Conflict MSH Importer — Blender Add-on

Import Hammer Engine (Star Conflict) `.mdl-mshXXX` static meshes into Blender.

**Compatible Versions**: Blender 4.2 LTS, Blender 5.0+

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
io_import_starconflict_msh/
└── __init__.py    # All plugin logic (MSH parsing + Blender import + batch)
```

## Using with msh2fbx

| Scenario | Recommended Tool |
|----------|-----------------|
| Batch convert all 62K files | `msh2fbx.exe --batch` |
| Preview a single model | Blender add-on |
| Manual editing/rigging needed | Blender add-on |
| Automated pipeline | `msh2fbx.exe` |
