"""
Batch MSH → OBJ exporter
Scans all .mdl-msh000 files, detects format, exports simple/skinned ones.
Usage: python batch_msh_export.py --root <extracted_dir> [--dry-run]
"""
import os, sys, struct, subprocess

MSH2OBJ = os.path.join(os.path.dirname(__file__), 'msh_to_obj_v3.py')

def is_simple_msh(path):
    """Quick check if MSH is simple (uncompressed) format"""
    try:
        with open(path, 'rb') as f:
            hdr = f.read(16)
        if len(hdr) < 16:
            return False
        h0 = struct.unpack_from('<I', hdr, 0)[0]
        h4 = struct.unpack_from('<I', hdr, 4)[0]
        return h0 == 0 and 0 < h4 < 1000
    except:
        return False

def batch_export(ROOT, dry_run=False):
    total = 0
    success = 0
    complex_count = 0
    simple_count = 0
    
    msh_files = []
    for dirpath, dirs, files in os.walk(ROOT):
        for f in files:
            if f.endswith('.mdl-msh000'):
                msh_files.append(os.path.join(dirpath, f))
    
    print(f"Found {len(msh_files)} .mdl-msh000 files")
    
    for i, msh_path in enumerate(msh_files):
        total += 1
        name = os.path.basename(msh_path)
        size_mb = os.path.getsize(msh_path) / 1024 / 1024
        
        if not is_simple_msh(msh_path):
            complex_count += 1
            continue
        
        simple_count += 1
        obj_path = msh_path + '.obj'
        
        if dry_run:
            print(f"  [{i+1}/{len(msh_files)}] {name} ({size_mb:.1f}MB) -> would export")
            continue
        
        try:
            result = subprocess.run(
                [sys.executable, MSH2OBJ, msh_path, '-o', obj_path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                success += 1
                if success % 50 == 0:
                    print(f"  [{success}] {name}")
            else:
                if 'Cannot detect' in result.stderr:
                    complex_count += 1
                    simple_count -= 1
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT: {name}")
        except Exception:
            pass
    
    print(f"\nResults:")
    print(f"  Total MSH files: {total}")
    print(f"  Simple format (exported): {success}/{simple_count}")
    print(f"  Complex format (skipped): {complex_count}")
    
    obj_count = sum(1 for _ in os.walk(ROOT) for f in _[2] if f.endswith('.obj'))
    print(f"  Total OBJ files in output: {obj_count}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, help='Path to extracted assets directory')
    parser.add_argument('--dry-run', action='store_true', help='List only, no export')
    args = parser.parse_args()
    batch_export(args.root, dry_run=args.dry_run)
