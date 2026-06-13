# Star Conflict TPAK Extractor — English Documentation

## 1. Overview

TPAK is the resource container format used by Star Conflict, version 7. The game is developed by Star Gem Inc. using the Hammer Engine (same engine as Crossout). This extractor unpacks all raw asset files from `.pak` archives.

**Extractor File**: `tpak_extract.py`

**Dependencies**: Python 3.7+, standard library only (no third-party packages)

---

## 2. TPAK Format Structure (Algorithm)

### 2.1 Architecture

```
┌──────────────────────────────────────────────┐
│ HEADER (28 bytes)                             │
│  TPAK | ver=7 | flags | file_count | reserved │
│  uncomp_nametable | comp_nametable            │
├──────────────────────────────────────────────┤
│ Filename Table (raw deflate compressed)       │
│  → Before decompress: XOR first 4B by file_count│
│  → After decompress: XOR decode each entry    │
├──────────────────────────────────────────────┤
│ File Index Table (file_count × 4B, skipped)   │
├──────────────────────────────────────────────┤
│ File Data Table (raw deflate compressed)      │
│  → XOR key = file_count + comp_size          │
│  → 16B per entry: size|name_off|chunks|chunk_idx│
├──────────────────────────────────────────────┤
│ File Chunk Table (raw deflate compressed)     │
│  → XOR key = file_count + comp_cs + chunks    │
│  → 16B per entry: unkwn|uncomp|offset|comp_size│
├──────────────────────────────────────────────┤
│ Raw File Chunk Data (raw deflate or stored)   │
└──────────────────────────────────────────────┘
```

### 2.2 Core Algorithm Steps

```
1. Read header → extract file_count, comp_nametable_size
2. Decompress filename table:
   a. Read comp_nametable_size bytes
   b. XOR first 4 bytes with file_count
   c. zlib raw deflate (wbits=-15) decompress
   d. XOR decode each filename entry:
       byte[j] ^= ((position + length) × 2 + (length%5 + index))
       Entry skip = 4(len header) + length(name) + 1(extra null)
3. Skip file index table (file_count × 4 bytes)
4. Decompress file data table:
   a. Scan forward for valid compressed size (0-3 bytes padding)
   b. XOR first 4 bytes with (file_count + comp_size)
   c. raw deflate → 16 bytes metadata per file
5. Decompress file chunk table:
   a. Align to 4-byte boundary
   b. XOR first 4 bytes with (file_count + comp_cs + chunk_count)
   c. raw deflate → 16 bytes metadata per chunk
6. Extract files:
   a. Locate data via chunk offset table
   b. If compressed == uncompressed → read directly
   c. Otherwise → raw deflate decompress
```

### 2.3 Key Technical Details

| Detail | Description |
|--------|-------------|
| Compression | zlib raw deflate (NOT standard zlib-wrapped) |
| Encryption | XOR obfuscation (NOT AES), different keys per table |
| Filename decode | Custom XOR, depends on entry length and index |
| Endianness | Little-endian throughout |
| Padding | 1 extra null byte after each filename table entry |

---

## 3. Usage

> **Path Note**: No scripts contain hardcoded paths. Helper scripts (`batch_extract.py`, etc.) auto-locate `tpak_extract.py` from their own directory. Replace `<game_data_dir>` with your actual path, e.g. `D:\Steam\steamapps\common\Star Conflict\data`.

### 3.1 Basic Commands

```powershell
# List files in a pak (no extraction)
python tpak_extract.py "<game_data_dir>\gamedata.pak" -l

# Extract single pak
python tpak_extract.py "<game_data_dir>\gamedata.pak" -o ./extracted

# Extract ALL paks in data/ directory
python tpak_extract.py "<game_data_dir>" -o ./extracted

# Filter by file extension
python tpak_extract.py "<game_data_dir>" -o ./extracted -t .tfd,.tfh,.dds
```

### 3.2 Arguments

| Argument | Description |
|----------|-------------|
| `path` | `.pak` file path OR `data/` directory path |
| `-o` / `--output` | Output directory (default: `./extracted`) |
| `-l` / `--list` | List files only, do not extract |
| `-t` / `--type` | Extension filter, comma-separated (e.g. `.dds,.lua`) |

### 3.3 Batch Extraction Examples

```powershell
# Category-based batch extraction (requires --pak-dir)
python batch_extract.py --pak-dir "<game_data_dir>" --out ./extracted --gamedata
python batch_extract.py --pak-dir "<game_data_dir>" --out ./extracted --textures
python batch_extract.py --pak-dir "<game_data_dir>" --out ./extracted --models

# Batch MSH → OBJ export
python batch_msh_export.py --root ./extracted --dry-run   # preview first
python batch_msh_export.py --root ./extracted             # actual export

# Texture conversion
python rawtex_py.py ./extracted --auto

# Cleanup + report
python organize_assets.py --root ./extracted --clean
python organize_assets.py --root ./extracted --report
```

### 3.4 Output Structure

```
output/
├── gamedata/
│   └── gamedata/def/ex/active.lua    ← game scripts
├── textures_armor_part1/
│   └── textures/armor/bp21_fabric.tfh  ← texture header
│   └── textures/armor/bp21_fabric.tfd  ← texture data
├── models_modules_part1/
│   └── models/modules/m_active/
│       ├── module_destroyerring.mdl-hdr   ← model bounding box
│       ├── module_destroyerring.mdl-msh000 ← mesh LOD0
│       ├── module_destroyerring.mdl-skl   ← skeleton data
│       └── module_destroyerring_d.tfh     ← texture
└── sound/
    └── sound/music.fsb                ← FMOD sound bank
```

---

## 4. Code Structure

```python
# Core functions
decode_nametable()    # XOR-decode filename table entries
read_tpak()           # Main parser, returns (names, files, chunks, data_start, raw_data)
extract_file()        # Extract single file (with raw deflate decompression)
extract_all()         # Extract all files from a pak
list_files()          # List files without extraction

# Helpers
xor4()                # XOR first 4 bytes of buffer
try_decompress()      # raw deflate decompression wrapper
scan_valid_int32()    # Scan for valid int32 (handles alignment offsets)
```

---

## 5. Verified Status

| File | Files | Status |
|------|-------|--------|
| `gamedata.pak` | 333 (Lua) | ✅ 333/333 |
| `textures_armor_part1.pak` | 22 (DDS) | ✅ 22/22 |
| `textures_effects_simple.pak` | 81 (DDS) | ✅ 81/81 |
| `fonts.pak` | 88 (fonts) | ✅ 88/88 |
| `models_modules_part1.pak` | 906 (models) | ✅ 906/906 |
| `models_weapons_part2.pak` | 4368 (models) | ✅ 4368/4368 |
| `sound_music.pak` | 1 (FSB) | ✅ 1/1 |
| All 844 paks | 113,749 files | ✅ 753/844 |

---

## 6. Post-Extraction Format Conversion

Extracted files are **not all directly usable**. Further conversion is needed depending on file type:

### 6.1 Textures (.tfd + .tfh → .dds)

`.tfd` is Hammer Engine DDSx texture data, `.tfh` is the texture metadata header.

| Tool | Coverage | Usage |
|------|----------|-------|
| `rawtex_py.py` (in-house) | ~50% (simple TFH) | `python rawtex_py.py dir/ --auto` |
| `tex_StarConflict_tfh_tfd_v2.py` (Noesis plugin) | ~70% (fonts ✅, _d/_nm ✅) | Drag .tfh into Noesis |
| `rawtex` (id-daemon) | ~90% (fallback) | `RawtexCmd.exe file.dds DXT5` |

**Converted usable**: fonts (70/70), _d/_nm (simple + compressed), mapskit/decorative mostly usable.

**Blocker**: _s1 (BC5/ATI2 non-square), new-format _s, background/level textures — majority of compressed TFH remain unresolved.

### 6.2 Models (.mdl-msh → .obj)

Two format variants exist:

| Format | Share | Tool | Notes |
|--------|-------|------|-------|
| **Simple MSH** (uncompressed) | ~11% (487 files) | `msh_to_obj_v3.py` (in-house) ✅ | VBytes=20-40 auto-detect, direct OBJ export |
| **Complex MSH** (compressed) | ~89% (3,871 files) | Noesis 26-plugin pack ⚠️ | `.msh000~987` (99.5%), `.msh988+` via CLI |

**Blocker**: Complex MSH uses Hammer Engine proprietary compression. Our 26 Noesis plugins cover `.msh000~987` (99.5%), `.msh988+` via `msh_to_obj_v3.py` CLI.

- AceWell plugin: [Yandex Disk](https://yadi.sk/d/iJiQ4Ajr3PeySZ)
- Noesis: [richwhitehouse.com](https://richwhitehouse.com/noesis/)
- CGIG forum: [cgig.ru/forum/viewtopic.php?t=2602](https://cgig.ru/forum/viewtopic.php?t=2602)
- Fallback: Ninja Ripper (runtime capture), RenderDoc (GPU frame capture)

### 6.3 Audio (.fsb → .wav/.ogg)

`.fsb` is FMOD Sound Bank format, 41 files total (0.96 GB).

| Tool | Usage |
|------|-------|
| `fsb_aud_extr` | `fsb_aud_extr.exe music.fsb` |
| foobar2000 + vgmstream plugin | Drag .fsb → Right-click Convert |
| FSBExtractor (GUI) | Graphical interface |

### 6.4 Game Scripts (.lua / .blk)

✅ No conversion needed, directly readable. Lua scripts contain ship/weapon/mission configs, BLK files are key-value pairs.

### 6.5 Conversion Pipeline Overview

```
TPAK Extraction
  │
  ├── .tfd + .tfh ──→ rawtex_py / Noesis v2 ──→ .dds (fonts ✅, _s1/_s ❌)
  │     └── Blocker: _s1 non-square BC5/ATI2, new-format _s, bg textures
  │
  ├── .mdl-msh ──→ msh_to_obj_v3.py ──→ .obj (11% simple format)
  │     └── Blocker: 89% complex compressed, via Noesis 26 plugins
  │
  ├── .fsb ──→ fsb_aud_extr ──→ .wav / .ogg ✅
  │
  ├── .lua / .blk ──→ directly readable ✅
  │
  └── .dae / .ma ──→ Blender direct import ✅
```

---

## 7. References

- Johnnynator/tpak — C reference implementation: https://github.com/Johnnynator/tpak
- clutch.bms — QuickBMS script: http://aluigi.org/bms/clutch.bms
- CGIG.ru — Hammer Engine discussion: https://cgig.ru/forum/viewtopic.php?t=2602
