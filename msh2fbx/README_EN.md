# msh2fbx — Star Conflict MSH → FBX Converter

A pure C command-line tool that converts Hammer Engine `.mdl-mshXXX` static meshes to Autodesk FBX format. Zero external dependencies — no Noesis or Autodesk SDK required.

## Building

**Prerequisites**: Visual Studio 2019 or 2022 (with C++ Desktop Development workload)

```powershell
cd msh2fbx
.\build.bat
```

Output: `msh2fbx.exe` (~500 KB, single-file redistributable)

## Usage

```
msh2fbx <input.msh>                  # Single file, auto-generates <input>.fbx
msh2fbx <input.msh> <output.fbx>     # Single file, custom output path
msh2fbx --batch <dir> <outdir>       # Batch recursive conversion of directory tree
msh2fbx --help                        # Show help
```

## Arguments

| Argument | Description |
|----------|-------------|
| `<input.msh>` | Input `.mdl-mshXXX` file path |
| `<output.fbx>` | Output FBX path (optional, default = input path + `.fbx`) |
| `--batch <dir> <outdir>` | Batch mode: recursively scan `<dir>` for all `.mdl-msh*`, output to `<outdir>` |
| `--help`, `-h` | Show help |

## Naming Convention

In batch mode, output filenames follow this rule (consistent with Noesis pipeline):

| Input | Output |
|-------|--------|
| `plasma_gun_mod1.mdl-msh000` | `plasma_gun_mod1000.fbx` |
| `map.mdl-msh001` | `map001.fbx` |
| `ship_hull.mdl-msh005` | `ship_hull005.fbx` |

Rule: remove the `.mdl-msh` portion, keep model name + LOD number, append `.fbx` extension.

## Batch Conversion

Batch mode recursively traverses the input directory, preserving directory hierarchy:

```powershell
# Convert entire backgrounds directory
.\msh2fbx.exe --batch quickbms_unpacksource\mapskit\backgrounds fbx_output\backgrounds
```

Output directory structure:
```
fbx_output/
└── backgrounds/
    └── area1/
        ├── allidium_in_danger/
        │   ├── map000.fbx
        │   ├── map001.fbx
        │   └── map002.fbx
        └── allidium_yard/
            ├── map000.fbx
            ├── map001.fbx
            └── map002.fbx
```

**Resume support**: Existing output files (>0 bytes) are automatically skipped. Re-run after interruption without re-converting.

## Conversion Pipeline

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  .mdl-mshXXX     │ →   │  msh2fbx.exe     │ →   │  .fbx (7400)     │
│  (Hammer Engine) │     │  MSH parse + FBX  │     │  (Autodesk FBX)  │
└──────────────────┘     │  write            │     └──────────────────┘
                         └──────────────────┘
```

Exported data:
- Vertex positions (position xyz)
- UV coordinates (set 0, per-vertex mapping, V auto-flipped)
- Triangle face indices

Not included (MSH format lacks this data):
- Bones/skinning
- Material/texture references
- Animation
- Normals (can be computed later)

## Performance

| Scale | File Count | Time | Throughput |
|-------|-----------|------|------------|
| Small batch | 83 | 0.5 s | ~173 files/s |
| Medium batch | 622 | 3.4 s | ~183 files/s |
| Full set (estimated) | ~188,000 | ~17 min | — |

## Supported Formats

| VBytes | Flag Condition | UV Offset | Common Usage |
|--------|---------------|-----------|--------------|
| 20 | — | 12 | Basic mesh |
| 24 | — | 16 | Extended mesh |
| 28 | flag=0xE, 5 | 16 | Scene objects |
| 28 | flag=0x11 | 20 | Special objects |
| 32 | — | 20 | Medium mesh |
| 36 | — | 20 | Large mesh |
| 40 | — | 24 | Character model |

Number range: `.mdl-msh000` ~ `.mdl-msh1308`

## Dependencies

- **Build-time**: ufbx_write (MIT licensed, bundled in `msh2fbx/`)
- **Runtime**: No external dependencies — `msh2fbx.exe` is self-contained

## Differences from Noesis Pipeline

| | Noesis Pipeline | msh2fbx |
|---|---|---|
| Execution | Noesis + Python scripts | Single .exe file |
| Dependencies | Noesis (closed-source) + Python | None |
| Speed | ~1-2 files/s | ~183 files/s |
| Parallelism | Python multi-process | Serial (I/O is fast enough) |
| FBX Version | Noesis internal format | Standard 7400 binary |
| Portability | Must bundle Noesis | Single file, copy-and-run |

## FAQ

**Q: What software can open the generated FBX files?**
Blender, Unity, Unreal Engine, 3ds Max, Maya, and other major 3D software all support FBX 7400 format.

**Q: Why are there no materials/textures?**
`.mdl-mshXXX` contains pure mesh data only, with no material information. Material definitions are in `.mdf` files, and textures are stored in `.tfh`/`.tfd` files. Material association requires additional processing scripts.

**Q: Can it batch convert all 188,000 files?**
Yes. Run `msh2fbx --batch quickbms_unpacksource fbx_output`, approximately 17 minutes. The resume mechanism ensures you can continue after interruption.

**Q: Does it work on Linux?**
The source code is cross-platform C99. To build on Linux:
```bash
gcc -O2 -DUFBXW_STATIC -o msh2fbx msh2fbx.c ufbx_write.c -lm
```

**Q: What if conversion fails?**
Check that the MSH file is intact (TPAK unpacking was successful). The tool prints error messages to stderr.
