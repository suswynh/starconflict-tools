"""
Organize extracted assets:
1. Delete invalid .dds (not real DDS), keep _real.dds
2. Move _real.dds to replace originals
3. Generate resource report
Usage: python organize_assets.py --root <extracted_dir> [--clean] [--report]
"""
import os, struct, shutil

def is_valid_dds(path):
    """Check if file starts with DDS magic"""
    try:
        with open(path, 'rb') as f:
            return f.read(4) == b'DDS '
    except:
        return False

def organize():
    deleted = 0
    kept_real = 0
    moved = 0
    
    print("Scanning...")
    
    for dirpath, dirs, files in os.walk(ROOT):
        real_dds = {}
        orig_dds = []
        
        for f in files:
            if f.endswith('_real.dds'):
                base = f[:-9]  # Remove '_real.dds'
                real_dds[base] = os.path.join(dirpath, f)
            elif f.endswith('.dds'):
                orig_dds.append(f)
        
        # For each _real.dds, delete the original invalid .dds and rename
        for base, real_path in real_dds.items():
            # Find matching original (could be .dds or .tfd renamed to .dds)
            for orig_name in orig_dds:
                orig_base = os.path.splitext(orig_name)[0]
                if orig_base == base:
                    orig_path = os.path.join(dirpath, orig_name)
                    if not is_valid_dds(orig_path):
                        os.remove(orig_path)
                        deleted += 1
                    break
            
            # Rename _real.dds → .dds
            new_path = os.path.join(dirpath, base + '.dds')
            if not os.path.exists(new_path):
                os.rename(real_path, new_path)
                moved += 1
                kept_real += 1
        
        if deleted % 500 == 0 and deleted > 0:
            print(f"  Progress: {deleted} deleted, {moved} moved...")
    
    print(f"\nResults:")
    print(f"  Deleted invalid .dds: {deleted}")
    print(f"  Renamed _real.dds → .dds: {moved}")

def generate_report():
    """Generate resource statistics"""
    from collections import Counter
    
    ext_count = Counter()
    total_size = 0
    total_files = 0
    
    category_size = Counter()
    category_files = Counter()
    
    for dirpath, dirs, files in os.walk(ROOT):
        for f in files:
            path = os.path.join(dirpath, f)
            size = os.path.getsize(path)
            ext = os.path.splitext(f)[1].lower()
            
            ext_count[ext] += 1
            total_size += size
            total_files += 1
            
            # Categorize
            rel = os.path.relpath(dirpath, ROOT)
            top = rel.split(os.sep)[0] if rel != '.' else 'root'
            category_files[top] += 1
            category_size[top] += size
    
    print(f"\n{'='*60}")
    print(f"  Star Conflict Resource Report")
    print(f"{'='*60}")
    print(f"  Total files: {total_files:,}")
    print(f"  Total size:  {total_size/1024/1024/1024:.2f} GB")
    print(f"\n  By extension:")
    for ext, count in ext_count.most_common(15):
        print(f"    {ext:8s}: {count:>8,} files")
    
    print(f"\n  By category (top-level dir):")
    for cat, count in category_files.most_common(15):
        size_mb = category_size[cat] / 1024 / 1024
        print(f"    {cat[:40]:40s}: {count:>6,} files, {size_mb:>8,.0f} MB")
    
    # Count valid DDS
    valid_dds = 0
    dds_size = 0
    for dirpath, dirs, files in os.walk(ROOT):
        for f in files:
            if f.endswith('.dds'):
                path = os.path.join(dirpath, f)
                if is_valid_dds(path):
                    valid_dds += 1
                    dds_size += os.path.getsize(path)
    
    print(f"\n  Valid DDS textures: {valid_dds:,} ({dds_size/1024/1024:.0f} MB)")
    
    # Count models
    msh_count = sum(1 for _ in os.walk(ROOT) for f in _[2] if '.mdl-msh' in f)
    obj_count = sum(1 for _ in os.walk(ROOT) for f in _[2] if f.endswith('.obj'))
    lua_count = sum(1 for _ in os.walk(ROOT) for f in _[2] if f.endswith('.lua'))
    dae_count = sum(1 for _ in os.walk(ROOT) for f in _[2] if f.endswith('.dae'))
    
    print(f"  MSH models: {msh_count:,}")
    print(f"  OBJ models: {obj_count:,}")
    print(f"  DAE models: {dae_count:,}")
    print(f"  Lua scripts: {lua_count:,}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, help='Path to extracted assets directory')
    parser.add_argument('--clean', action='store_true', help='Clean up invalid DDS files')
    parser.add_argument('--report', action='store_true', help='Generate report only')
    args = parser.parse_args()
    
    ROOT = args.root
    if args.clean or (not args.report):
        organize()
    generate_report()
