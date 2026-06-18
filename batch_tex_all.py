#!/usr/bin/env python3
"""
Batch convert ALL Star Conflict .tfh textures to .dds
Preserves source directory structure under tex_universe_check/
Supports parallel processing, incremental resume, progress reporting.

Usage:
    python batch_tex_all.py [--workers N] [--dry-run]
"""
import os, sys, struct, time, argparse, math, traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Add tools dir to path
TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'starconflict-tools')
sys.path.insert(0, TOOLS_DIR)

SOURCE_BASE = r'scunpack\output'
TARGET_BASE = r'scunpack\tex_universe_check'
os.makedirs(TARGET_BASE, exist_ok=True)

# ── DDS constants ──
FOURCC_BYTES = {'DXT1': b'DXT1', 'DXT3': b'DXT3', 'DXT5': b'DXT5'}
DDPF_ALPHAPIXELS, DDPF_RGB, DDPF_FOURCC = 0x01, 0x40, 0x04
DDSD_CAPS, DDSD_HEIGHT, DDSD_WIDTH = 0x1, 0x2, 0x4
DDSD_PIXELFORMAT, DDSD_LINEARSIZE, DDSD_MIPMAPCOUNT = 0x1000, 0x80000, 0x20000
DDS_FLAGS = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE | DDSD_MIPMAPCOUNT
DDSCAPS_TEXTURE = 0x1000


def build_dds_header(w, h, fmt, linear_size):
    hdr = bytearray(128)
    hdr[0:4] = b'DDS '
    struct.pack_into('<I', hdr, 4, 124)
    struct.pack_into('<I', hdr, 8, DDS_FLAGS)
    struct.pack_into('<I', hdr, 12, h)
    struct.pack_into('<I', hdr, 16, w)
    struct.pack_into('<I', hdr, 20, linear_size)
    struct.pack_into('<I', hdr, 28, 1)
    struct.pack_into('<I', hdr, 76, 32)
    if fmt == 'RGBA':
        struct.pack_into('<I', hdr, 80, DDPF_RGB | DDPF_ALPHAPIXELS)
        struct.pack_into('<I', hdr, 88, 32)
        struct.pack_into('<I', hdr, 92, 0x000000FF)
        struct.pack_into('<I', hdr, 96, 0x0000FF00)
        struct.pack_into('<I', hdr, 100, 0x00FF0000)
        struct.pack_into('<I', hdr, 104, 0xFF000000)
    else:
        struct.pack_into('<I', hdr, 80, DDPF_FOURCC)
        hdr[84:88] = FOURCC_BYTES[fmt].ljust(4, b'\x00')[:4]
    struct.pack_into('<I', hdr, 108, DDSCAPS_TEXTURE)
    return bytes(hdr)


def compute_linear_size(w, fmt):
    if fmt == 'RGBA':
        return w * 4
    elif fmt == 'DXT1':
        return max(1, (w + 3) // 4) * 8
    else:
        return max(1, (w + 3) // 4) * 16


def parse_tfh(data, filepath):
    """PHP-style TFH parser. Returns dict or None."""
    if len(data) < 8:
        return None
    mc = data[4] & 0x0F
    mif = (data[4] & 0xF0) >> 4
    fmt_code = data[5] & 0x0F
    if mc == 0:
        return None
    needed = 8 + mc * 12
    if len(data) < needed:
        return None
    # Read last mip
    pos = 8 + (mc - 1) * 12
    off = struct.unpack_from('<I', data, pos)[0]
    sz = struct.unpack_from('<I', data, pos + 4)[0]
    w = struct.unpack_from('<I', data, pos + 8)[0]
    if sz <= 0 or w <= 0:
        return None

    # Format dispatch (exact PHP logic)
    if fmt_code in (0x0, 0x5, 0x6):
        fmt = 'RGBA'; pw = w // 4; ph = sz // w if w > 0 else 0
    elif fmt_code in (0x7, 0xB):
        fmt = 'DXT1'; pw = w // 2; ph = (4 * sz) // w if w > 0 else 0
    elif fmt_code in (0x9, 0xD):
        fmt = 'DXT3'; pw = w // 4; ph = (4 * sz) // w if w > 0 else 0
    elif fmt_code in (0xA, 0xE):
        fmt = 'DXT5'; pw = w // 4; ph = (4 * sz) // w if w > 0 else 0
    else:
        return None

    if pw <= 0:
        # Fallback: square estimate
        import math
        bpp = {'RGBA': 4, 'DXT1': 0.5, 'DXT3': 1, 'DXT5': 1}[fmt]
        side = int(math.sqrt(max(1, sz / bpp)))
        pw = 1
        while pw < side:
            pw <<= 1
        ph = pw

    if pw <= 0 or ph <= 0 or pw > 16384 or ph > 16384:
        return None

    return {
        'format': fmt, 'width': pw, 'height': ph,
        'data_offset': off, 'data_size': sz,
        'data_source': 'tfh' if mc == mif else 'tfd',
        'fmt_code': fmt_code, 'mips': mc,
    }


def convert_one(tfh_path):
    """Convert a single .tfh to .dds. Returns (status, detail) string tuple."""
    try:
        tfd_path = tfh_path[:-4] + '.tfd'
        rel = os.path.relpath(tfh_path, SOURCE_BASE)
        out_path = os.path.join(TARGET_BASE, rel[:-4] + '.dds')

        # Skip if output exists and is newer
        if os.path.exists(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(tfh_path):
            return ('skip_exists', rel)

        # Read TFH
        with open(tfh_path, 'rb') as f:
            tfh_data = f.read()

        info = parse_tfh(tfh_data, tfh_path)
        if info is None:
            return ('error_parse', rel)

        # Read pixel data
        if info['data_source'] == 'tfh':
            start = info['data_offset']
            end = start + info['data_size']
            if end > len(tfh_data):
                return ('error_bounds', rel)
            pixel_data = tfh_data[start:end]
        else:
            if not os.path.isfile(tfd_path):
                return ('skip_no_tfd', rel)
            with open(tfd_path, 'rb') as f:
                tfd_data = f.read()
            start = info['data_offset']
            end = start + info['data_size']
            if end > len(tfd_data):
                return ('error_tfd_bounds', rel)
            pixel_data = tfd_data[start:end]

        # Swizzle RGBA: BGRA -> RGBA
        if info['format'] == 'RGBA':
            arr = bytearray(pixel_data)
            for i in range(0, len(arr), 4):
                arr[i], arr[i + 2] = arr[i + 2], arr[i]
            pixel_data = bytes(arr)

        # Build DDS
        ls = compute_linear_size(info['width'], info['format'])
        hdr = build_dds_header(info['width'], info['height'], info['format'], ls)

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(hdr)
            f.write(pixel_data)

        return ('ok', f"{rel} -> {info['width']}x{info['height']} {info['format']}")

    except Exception as e:
        return ('error_exc', f"{rel}: {e}")


def main():
    parser = argparse.ArgumentParser(description='Batch convert all Star Conflict TFH to DDS')
    parser.add_argument('--workers', type=int, default=min(8, os.cpu_count() or 4),
                        help='Parallel workers (default: cpu count, max 8)')
    parser.add_argument('--dry-run', action='store_true', help='List files without converting')
    args = parser.parse_args()

    # Collect all .tfh files
    print(f"Scanning {SOURCE_BASE} ...")
    t0 = time.time()
    tfh_files = []
    for root, dirs, files in os.walk(SOURCE_BASE):
        for f in files:
            if f.lower().endswith('.tfh'):
                tfh_files.append(os.path.join(root, f))

    total = len(tfh_files)
    print(f"Found {total} .tfh files in {time.time() - t0:.1f}s")

    if args.dry_run:
        for f in tfh_files[:50]:
            print(f"  {os.path.relpath(f, SOURCE_BASE)}")
        if total > 50:
            print(f"  ... and {total - 50} more")
        return

    # Convert
    stats = {'ok': 0, 'skip_exists': 0, 'skip_no_tfd': 0,
             'error_parse': 0, 'error_bounds': 0, 'error_tfd_bounds': 0, 'error_exc': 0}
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(convert_one, f): f for f in tfh_files}
        done = 0
        for future in as_completed(futures):
            done += 1
            status, detail = future.result()
            stats[status] = stats.get(status, 0) + 1
            # Progress every 100 files
            if done % 100 == 0 or done == total:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                print(f"  [{done}/{total}] {done * 100 // total}% "
                      f"({rate:.1f}/s, ETA {eta / 60:.0f}m) "
                      f"ok={stats['ok']} skip={stats['skip_exists']} no_tfd={stats['skip_no_tfd']} err={stats['error_parse'] + stats['error_bounds'] + stats['error_tfd_bounds'] + stats['error_exc']}",
                      flush=True)

    elapsed = time.time() - t0
    print(f"\n=== Complete in {elapsed / 60:.1f} minutes ===")
    print(f"  OK:             {stats['ok']}")
    print(f"  Skipped(exists):{stats['skip_exists']}")
    print(f"  Skipped(no tfd):{stats['skip_no_tfd']}")
    print(f"  Parse errors:   {stats['error_parse']}")
    print(f"  Bounds errors:  {stats['error_bounds'] + stats['error_tfd_bounds']}")
    print(f"  Other errors:   {stats['error_exc']}")
    print(f"  Total:          {total}")


if __name__ == '__main__':
    main()
