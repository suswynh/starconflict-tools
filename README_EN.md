# Star Conflict Asset Reverse Engineering Toolkit

A collection of tools for extracting and converting Star Conflict game assets. The game is developed by Star Gem Inc. using the **Hammer Engine**.

## Tools

| Tool | Function | Dependency |
|------|----------|------------|
| `tpak_extract.py` | TPAK v7/v8 container unpacking (844 .pak fully supported) | Python 3.7+ |
| `msh_to_obj_v3.py` | MSH mesh → OBJ (VBytes 20-44, covers 000~1308) | Python 3.7+ |
| `msh2fbx/` | ⚡ **MSH → FBX standalone converter** — Pure C, zero deps, ~183 files/s | Visual Studio 2019+ |
| `blender_plugin/` | 🎨 **Blender import add-on** — Import .mdl-msh* directly, supports 4.2 LTS / 5.0+ | Blender 4.2+ |
| `tex_targem_py.py` | 🔥 **Primary texture converter** — Pure Python, PHP TargemImage logic, all formats | Python 3.7+ |
| `rawtex_py.py` | Simple TFH+DDSx texture → standard DDS (superseded by `tex_targem_py.py`) | Python 3.7+ |
| `batch_tex_all.py` | Batch .tfh → .dds conversion, multi-process, preserves directory structure | Python 3.7+ |
| `batch_extract.py` | Batch unpack all .pak files | Python 3.7+ |
| `batch_msh_export.py` | Batch MSH → OBJ export | Python 3.7+ |
| `organize_assets.py` | Clean up invalid files, generate asset reports | Python 3.7+ |
| `batch_quickbms.ps1` | Batch quickbms unpacking (fallback method) | quickbms |
| `clutch.bms` | quickbms script, TPAK v7/v8 parsing | quickbms |
| `batch_noesis_fbx.py` | Batch Noesis MSH → FBX export | Noesis 4.x+ |
| `rename_fbx.py` | Batch FBX file renaming | Python 3.7+ |
| `test_noesis_cmd.py` | Noesis command-line test script | Noesis 4.x+ |
| `noesis_plugins/` | **Complete Noesis plugin pack** (26 model + 3 texture plugins) | Noesis 4.x+ |
| **Audio Tools** | | |
| `fsbext/` | 🔈 **FSB audio extractor** — by Luigi Auriemma, supports FSB1~FSB5, CLI | Windows/Linux |
| `vgmstream/` | 🔈 **Vorbis audio fix** — vgmstream-cli, generates valid WAV headers | Windows/Linux |
| `FsbExtractor_16.10.21/` | 🖱️ FSB Extractor GUI — graphical alternative | Windows |

## Tool Chain Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                    TPAK v7/v8 Container Unpack                    │
│                  tpak_extract.py / scunpack.exe                   │
└─────────┬────────────────┬───────────────┬───────────────────────┘
          │                │               │
   ┌──────▼──────┐ ┌───────▼──────┐ ┌──────▼──────┐
   │ .mdl-mshXXX │ │ .tfh + .tfd  │ │ .dds / .lua │
   │  Model files│ │ Texture pairs│ │  / .fsb etc  │
   └──────┬──────┘ └───────┬──────┘ └─────────────┘
          │                │
   ┌──────▼───────────────────────────────┐
   │         Model Conversion (3 routes)   │
   │                                      │
   │  ┌─────────────┐  ┌──────────────┐   │
   │  │ msh_to_obj   │  │  msh2fbx     │   │     ┌──────────────────┐
   │  │ _v3.py       │  │  (C, ~183/s) │   │     │ blender_plugin   │
   │  │ (Python)     │  │  Standalone  │   │     │ (Blender import) │
   │  └──────┬───────┘  └──────┬───────┘   │     └────────┬─────────┘
   │         │                 │           │              │
   │         ▼                 ▼           │              ▼
   │      .obj              .fbx          │      Blender → .fbx
   └──────────────────────────────────────┘
            │                │
   ┌────────▼────────────────▼────────────┐
   │          Texture Conversion           │
   │  tex_targem_py.py (Pure Python)      │
   │  batch_tex_all.py (Batch, preserve dir)│
   │  Noesis v2/v3/v4 plugins (preview)   │
   └──────────────────┬───────────────────┘
                      │
               ┌──────▼──────┐
               │   .dds      │
               │  Standard   │
               └─────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    Audio Extraction (.fsb)                     │
│                                                              │
│  ┌──────────────────┐       ┌──────────────────────────┐     │
│  │ fsbext (CLI)     │       │ FSB Extractor (GUI)      │     │
│  │ PCM/MPEG → WAV/  │       │ Drag FSB in → right-     │     │
│  │ MP3 (playable)   │       │ click extract            │     │
│  └────────┬─────────┘       └──────────────────────────┘     │
│           │                                                   │
│           │ Vorbis encoded → .ogg (no container header,       │
│           │                    not playable)                  │
│           │                                                   │
│  ┌────────▼─────────┐                                        │
│  │ vgmstream-cli    │                                        │
│  │ Re-extract → .wav│                                        │
│  │ Standard RIFF    │                                        │
│  │ header           │                                        │
│  └──────────────────┘                                        │
└──────────────────────────────────────────────────────────────┘
```

## `msh2fbx` — MSH → FBX Standalone Converter

> Pure C99 implementation, zero runtime dependencies, single-file executable. See [`msh2fbx/README.md`](msh2fbx/README.md) for details.

| Feature | Details |
|---------|---------|
| Speed | ~183 files/s (single-threaded, I/O bound) |
| Format | FBX 7400 Binary |
| Range | `.mdl-msh000` ~ `.msh1308` (VBytes 20/24/28/32/36/40/44) |
| Tested | 62,825 files → 100% success rate, 1.65 GB |

```powershell
# Build
cd msh2fbx; .\build.bat

# Usage
.\msh2fbx.exe model.mdl-msh000
.\msh2fbx.exe --batch input_dir output_dir
```

## `blender_plugin` — Blender Import Add-on

> Import `.mdl-mshXXX` files directly in Blender, supports 4.2 LTS / 5.0+. See [`blender_plugin/README.md`](blender_plugin/README.md) for details.

| Feature | Details |
|---------|---------|
| Import method | File → Import → Star Conflict MSH (.mdl-msh*) |
| UV support | ✅ UV channel (named "map1") |
| Coordinate system | 5 presets (default Y-up → Z-up) |
| Batch | ✅ Directory batch import supported |
| Vertex colors | ❌ MSH format does not contain vertex color data |

**Installation**: Package as `.zip` → Blender Preferences → Add-ons → Install from Disk.

## Noesis Plugin Pack (`noesis_plugins/`)

> **Dependency**: [Noesis](https://richwhitehouse.com/index.php?content=inc_projects.php) 4.x+

| Category | File | Count | Function |
|----------|------|-------|----------|
| Texture plugin | `tex_StarConflict_tfh_tfd_v2.py` | 1 | Bitstream parsing + guess_size fallback (fonts/DXT) |
| Texture plugin | `tex_StarConflict_tfh_tfd_v3.py` | 1 | PHP mip table logic + v2 fallback (all formats) |
| Texture plugin | `tex_StarConflict_tfh_tfd_v4_php.py` | 1 | Pure PHP port (comparison/verification) |
| Model plugin | `fmt_StarConflict_msh_A~Z.py` | 26 | Covers `.mdl-msh000` ~ `.msh987` |
| Archive | `_archived/` | 3 | v1 texture plugins, early model base classes |

## Audio Extraction (FSB → WAV / MP3)

FSB (FMOD Sample Bank) is FMOD audio engine's container format. Star Conflict contains **41 FSB files** (~0.96 GB) with audio streams in three encodings.

### Encoding Distribution

| Encoding | File Count | Tool | Notes |
|----------|-----------|------|-------|
| MPEG (MP3) | 2,136 | fsbext | Direct extraction, ready to play |
| PCM16 (WAV) | 488 | fsbext | Auto-adds RIFF header |
| Vorbis (OGG) | 578 | fsbext + vgmstream | fsbext lacks container header, needs vgmstream fix |

> ⚠️ **Known Issue**: fsbext outputs raw Vorbis data blocks when extracting Vorbis audio, missing the OGG container header (`OggS`). This makes files unplayable in PotPlayer / Windows Media Player. Use vgmstream to re-extract and generate valid WAV.

### 14 FSBs Affected by Vorbis

`aura` `hangar` `hit` `mnstr` `modules_vorbis` `raid` `swarm` `ui2` `weapon` `weapon2` `weapon3` `weapon4` `weapon_paper` `weapon_vorbis`

### Usage

```powershell
# Method 1: Batch extraction (recommended)
# Step 1 — fsbext quickly extracts all .fsb
$fsbext = ".\fsbext\fsbext.exe"
Get-ChildItem .\sound -Filter *.fsb | ForEach-Object {
    New-Item -ItemType Directory -Force -Path $_.BaseName
    & $fsbext -d "$($_.BaseName)" $_.FullName
}

# Step 2 — Check for Vorbis (.ogg files), fix with vgmstream
$vgm = ".\vgmstream\vgmstream-cli.exe"
$oggFsbs = @("aura","hangar","hit","mnstr","modules_vorbis","raid",
             "swarm","ui2","weapon","weapon2","weapon3","weapon4",
             "weapon_paper","weapon_vorbis")
foreach ($name in $oggFsbs) {
    $count = (& $vgm -m "$name.fsb" 2>&1 | Select-String "stream count: (\d+)").Matches.Groups[1].Value
    for ($i = 1; $i -le $count; $i++) {
        $sname = (& $vgm -m -s $i "$name.fsb" 2>&1 | Select-String "stream name: (.+)").Matches.Groups[1].Value
        & $vgm -s $i -o "$name\$sname.wav" "$name.fsb"
    }
}
```

### Tool Sources

| Tool | Version | Download | License |
|------|---------|----------|---------|
| fsbext | 0.3.8a | [aluigi.org/papers.htm#fsbext](https://aluigi.altervista.org/search.php?src=fsbext) | Open Source (GPL) |
| vgmstream | r1916+ | [github.com/vgmstream/vgmstream](https://github.com/vgmstream/vgmstream) | Open Source (ISC) |
| FSB Extractor | 16.10.21 | [aezay.dk/aezay/fsbextractor](http://aezay.dk/aezay/fsbextractor/) | Freeware |

## Quick Start

```powershell
# 1. Unpack
python tpak_extract.py "StarConflict\data" -o ./extracted

# 2. Batch texture conversion (one-shot full set)
python batch_tex_all.py --workers 8

# 3. Single-file texture conversion
python tex_targem_py.py texture.tfh
python tex_targem_py.py texture.tfh output.dds

# 4. Batch model export (OBJ / FBX)
python batch_msh_export.py --root ./extracted          # OBJ
.\msh2fbx\msh2fbx.exe --batch extracted fbx_output     # FBX

# 5. Preview in Blender
# Install blender_plugin/, then File → Import → Star Conflict MSH

# 6. Asset report
python organize_assets.py --root ./extracted --report
```

## Format Support

| Format | Coverage | Tool | Notes |
|--------|----------|------|-------|
| TPAK v7/v8 | ██████ 100% | `tpak_extract.py` | All 844 .pak supported |
| MSH Models | ██████ 99.7% | `msh_to_obj_v3.py` + `msh2fbx` + 26 Noesis plugins | .msh000~1308, VBytes 20-44 |
| TFH Textures | ██████ 99.6% | `tex_targem_py.py` | 11,671 .tfh → 11,623 successful |
| FSB Audio | ██████ 100% | `fsbext` + `vgmstream` | 41 .fsb → 3,247 playable (WAV+MP3) |

### Texture Support Status (2026-06-18)

| Texture Type | Status | Format | Notes |
|-------------|--------|--------|-------|
| _d, _nm (diffuse/normal) | ✅ Complete | DXT1/3/5 | Fully supported |
| _s (specular) | ✅ Complete | DXT1/5/RGBA | Both old and new versions |
| _s1 (specular) | ✅ Complete | DXT1/5/RGBA | format 0x07→DXT1, non-square support |
| fonts (R8/L8/ARGB) | ✅ Complete | Custom formats | 70/70, Noesis v2/v3 |
| mapskit / decorative | ✅ Complete | DXT1/3/5/RGBA | Fully supported |
| levels / backgrounds | ✅ Basic | Mixed | Some missing TFD (irradiance cubemap) |
| particles / reaper / ui | ✅ Complete | Mixed | Fully supported |

## Progress

**113,749 files** extracted from 844 .pak files, including:

| Asset Type | Count | Status |
|-----------|-------|--------|
| DDS Textures | 11,628 | ✅ 99.6% successfully converted |
| FBX Models | 62,825 | ✅ 100% successfully converted |
| OBJ Models | 487 | ✅ Available |
| Lua Scripts | 1,005 | ✅ Extracted |
| FSB Audio | 3,247 | ✅ 100% playable (1,066 WAV + 2,136 MP3) |

### Known Limitations

| Issue | Impact | Status |
|-------|--------|--------|
| Noesis RGBA rendering glitch | B/R channel swap when previewing RGBA textures | ⚠️ Under investigation (use scripts to batch export DDS instead) |
| Tiny textures | Some mip-level textures are only a few pixels, viewers may flag as empty | ℹ️ Normal |
| RGBA DDS compatibility | Some image viewers don't support uncompressed RGBA DDS | ℹ️ Use Honeyview/GIMP/PS to view |
| irradiance cubemap | Missing TFD files for level environment lightmaps | ⚠️ May need re-extraction / runtime-generated, not asset data |
| VBytes=44 character models | UV offset is estimated, bone data identified | ⚠️ UV needs precise verification |
| Vertex colors | MSH format does not contain vertex color data | ℹ️ Not supported by design |

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v5 | 2026-06 | Added FSB audio extraction (fsbext + vgmstream), fixed Vorbis OGG container header |
| v4 | 2026-06 | Added `msh2fbx` (C FBX converter) + `blender_plugin` (Blender import) |
| v3 | 2026-06 | tex_v3 PHP mip table precise calculation + v2 fallback |
| v2 | 2026-05 | tex_v2 NoeBitStream + guess_size fallback + font |
| v1 | 2026-04 | Initial toolset (rawtex_py, tpak_extract, msh_to_obj) |

## Acknowledgments

- **Mater (gamemodels3D)** — Provided TargemImage.php, which was instrumental in solving texture conversion challenges
- **Suigintou (Discord channel)** — Provided the original Noesis texture and model preview scripts and quickbms scripts
