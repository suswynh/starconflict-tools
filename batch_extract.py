"""
Batch extract Star Conflict resources.
Usage: python batch_extract.py --pak-dir <data_dir> --out <out_dir> [--all] [--textures] [--models] [--gamedata]
Example: python batch_extract.py --pak-dir "StarConflict/data" --out ./extracted --all
"""
import os, sys, shutil, subprocess

def run_extract(pak_list, label, file_types=None):
    """Extract a list of pak files"""
    print(f"\n{'='*60}")
    print(f"Extracting: {label} ({len(pak_list)} files)")
    print(f"{'='*60}")
    
    for i, pak_path in enumerate(pak_list):
        name = os.path.basename(pak_path)
        print(f"\n[{i+1}/{len(pak_list)}] {name} ({os.path.getsize(pak_path)/1024/1024:.1f} MB)")
        
        cmd = [sys.executable, EXTRACTOR, pak_path, "-o", OUT_DIR]
        if file_types:
            cmd.extend(["-t", file_types])
        
        try:
            subprocess.run(cmd, timeout=300)
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT - skipping large file")
        except Exception as e:
            print(f"  ERROR: {e}")

def rename_tfd_to_dds():
    """Rename all .tfd files to .dds (Dagor DDSx → DDS rename)"""
    print(f"\n{'='*60}")
    print("Renaming .tfd → .dds...")
    print(f"{'='*60}")
    count = 0
    for root, dirs, files in os.walk(OUT_DIR):
        for f in files:
            if f.endswith('.tfd'):
                old = os.path.join(root, f)
                new = old[:-4] + '.dds'
                os.rename(old, new)
                count += 1
    print(f"  Renamed {count} files")

def rename_tfh():
    """Also keep .tfh as metadata"""
    pass  # .tfh files are kept as-is

def extract_simple_obj(OUT_DIR):
    """Convert all simple MSH files to OBJ"""
    msh_to_obj = os.path.join(os.path.dirname(__file__), 'msh_to_obj_v2.py')
    if not os.path.exists(msh_to_obj):
        print("  WARNING: msh_to_obj_v2.py not found, skipping")
        return
    print(f"\n{'='*60}")
    print("Converting simple MSH → OBJ...")
    print(f"{'='*60}")
    count = 0
    for root, dirs, files in os.walk(OUT_DIR):
        for f in files:
            if f.endswith('.mdl-msh000'):
                msh_path = os.path.join(root, f)
                size = os.path.getsize(msh_path)
                if size < 10000:  # Only small files (simple models)
                    obj_path = msh_path + '.obj'
                    try:
                        subprocess.run([sys.executable, msh_to_obj, msh_path, "-o", obj_path], 
                                     timeout=10, capture_output=True)
                        count += 1
                    except:
                        pass
    print(f"  Converted {count} files")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--pak-dir', required=True, help='Path to StarConflict/data directory with .pak files')
    parser.add_argument('--out', default='./extracted', help='Output directory')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--textures', action='store_true')
    parser.add_argument('--models', action='store_true')
    parser.add_argument('--gamedata', action='store_true')
    parser.add_argument('--rename', action='store_true', help='Only rename .tfd→.dds')
    parser.add_argument('--obj', action='store_true', help='Convert simple MSH→OBJ')
    args = parser.parse_args()
    
    PAK_DIR = args.pak_dir
    OUT_DIR = args.out
    EXTRACTOR = os.path.join(os.path.dirname(__file__), 'tpak_extract.py')
    
    if not os.path.exists(EXTRACTOR):
        print(f"ERROR: tpak_extract.py not found at {EXTRACTOR}")
        print("Please ensure tpak_extract.py is in the same directory as this script.")
        sys.exit(1)
    
    os.makedirs(OUT_DIR, exist_ok=True)
    
    if not os.path.isdir(PAK_DIR):
        print(f"ERROR: --pak-dir '{PAK_DIR}' does not exist")
        sys.exit(1)
    
    pak_files = [os.path.join(PAK_DIR, f) for f in os.listdir(PAK_DIR) if f.endswith('.pak')]
    
    if args.rename:
        rename_tfd_to_dds()
        sys.exit(0)
    
    if args.obj:
        extract_simple_obj(OUT_DIR)
        sys.exit(0)
    
    # Categorize
    gamedata = [p for p in pak_files if 'gamedata' in os.path.basename(p)]
    textures = [p for p in pak_files if 'textures' in os.path.basename(p) or 'fonts' in os.path.basename(p)]
    models_p = [p for p in pak_files if 'models' in os.path.basename(p)]
    maps = [p for p in pak_files if 'mapskit' in os.path.basename(p) or 'levels' in os.path.basename(p)]
    other = [p for p in pak_files if p not in gamedata + textures + models_p + maps]
    
    do_all = args.all or (not args.textures and not args.models and not args.gamedata)
    
    if args.gamedata or do_all:
        run_extract(gamedata, "GAMEDATA (Lua scripts)")
    
    if args.textures or do_all:
        run_extract(textures, "TEXTURES + FONTS")
        rename_tfd_to_dds()
    
    if args.models or do_all:
        run_extract(models_p, "MODELS")
        extract_simple_obj(OUT_DIR)
    
    if do_all:
        run_extract(maps, "MAPS & LEVELS")
        run_extract(other, "OTHER")
        rename_tfd_to_dds()
        extract_simple_obj(OUT_DIR)
    
    print(f"\n{'='*60}")
    print("ALL DONE")
    print(f"Output: {OUT_DIR}")
