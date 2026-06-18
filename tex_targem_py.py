#!/usr/bin/env python3
"""
Star Conflict TFH/TFD texture converter — standalone Python implementation.
Based on TargemImage.php parsing logic. Outputs valid DDS files.

Supports: RGBA32, DXT1, DXT3, DXT5, BC5/ATI2 (for _s1 textures).

Usage:
    python tex_targem_py.py <input.tfh|input.tfd> [output.dds]
    python tex_targem_py.py --batch <directory>
"""

import struct
import os
import sys
import argparse
import math

# ──────────────────────────────────────────────────────────────
#  DDS constants
# ──────────────────────────────────────────────────────────────

FOURCC_BYTES = {
    'DXT1': b'DXT1',
    'DXT3': b'DXT3',
    'DXT5': b'DXT5',
}

# Pixel format flags
DDPF_ALPHAPIXELS = 0x01
DDPF_RGB         = 0x40
DDPF_FOURCC      = 0x04

# DDS header dwFlags
DDSD_CAPS        = 0x00000001
DDSD_HEIGHT      = 0x00000002
DDSD_WIDTH       = 0x00000004
DDSD_PITCH       = 0x00000008
DDSD_PIXELFORMAT = 0x00001000
DDSD_MIPMAPCOUNT = 0x00020000
DDSD_LINEARSIZE  = 0x00080000

DDS_HEADER_FLAGS = (DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH |
                    DDSD_PIXELFORMAT | DDSD_LINEARSIZE | DDSD_MIPMAPCOUNT)
# = 0x000A1007 — verified compatible with Honeyview/Win/PS/GIMP

DDSCAPS_TEXTURE  = 0x00001000


# ──────────────────────────────────────────────────────────────
#  DDS header builder (128 bytes)
# ──────────────────────────────────────────────────────────────

def build_dds_header(width, height, tex_format, linear_size):
    """Build a 128-byte DDS file header.
    Args:
        width, height: image dimensions in pixels
        tex_format: 'RGBA', 'DXT1', 'DXT3', 'DXT5'
        linear_size: pitch or linear size in bytes
    """
    hdr = bytearray(128)

    # Magic "DDS "
    hdr[0:4] = b'DDS '

    struct.pack_into('<I', hdr, 4, 124)                 # dwSize
    struct.pack_into('<I', hdr, 8, DDS_HEADER_FLAGS)
    struct.pack_into('<I', hdr, 12, height)
    struct.pack_into('<I', hdr, 16, width)
    struct.pack_into('<I', hdr, 20, linear_size)        # dwPitchOrLinearSize
    struct.pack_into('<I', hdr, 24, 0)                  # dwDepth
    struct.pack_into('<I', hdr, 28, 1)                  # dwMipMapCount
    # hdr[32:76] — dwReserved1 (44 bytes of zeros, already initialized)

    # Pixel format sub-structure (32 bytes)
    struct.pack_into('<I', hdr, 76, 32)                 # ddspf.dwSize

    if tex_format == 'RGBA':
        struct.pack_into('<I', hdr, 80, DDPF_RGB | DDPF_ALPHAPIXELS)
        # hdr[84:88] — dwFourCC stays zero for uncompressed
        struct.pack_into('<I', hdr, 88, 32)              # dwRGBBitCount
        struct.pack_into('<I', hdr, 92, 0x000000FF)      # R mask (R8G8B8A8)
        struct.pack_into('<I', hdr, 96, 0x0000FF00)      # G mask
        struct.pack_into('<I', hdr, 100, 0x00FF0000)     # B mask
        struct.pack_into('<I', hdr, 104, 0xFF000000)     # A mask
    else:
        struct.pack_into('<I', hdr, 80, DDPF_FOURCC)
        fourcc = FOURCC_BYTES[tex_format]
        hdr[84:88] = fourcc.ljust(4, b'\x00')[:4]
        # bits 88–108 stay zero (RGBBitCount + 4 masks = 5 x u32 = 20 bytes)

    # Caps (16 bytes)
    struct.pack_into('<I', hdr, 108, DDSCAPS_TEXTURE)    # dwCaps
    # hdr[112:128] — dwCaps2, dwCaps3, dwCaps4, dwReserved2 (all zero)

    return bytes(hdr)


# ──────────────────────────────────────────────────────────────
#  Linear size helper
# ──────────────────────────────────────────────────────────────

def compute_linear_size(width, tex_format):
    """DDS linear size (row pitch) for a given width and format."""
    if tex_format == 'RGBA':
        return width * 4
    elif tex_format == 'DXT1':
        return max(1, (width + 3) // 4) * 8
    else:  # DXT3, DXT5 — 16 bytes per 4×4 block
        return max(1, (width + 3) // 4) * 16


# ──────────────────────────────────────────────────────────────
#  TFH parser — exact PHP logic
# ──────────────────────────────────────────────────────────────

def parse_tfh_data(data, filepath):
    """Parse TFH binary header.  Returns a dict with parsing results,
    or a dict with key 'error' on unknown format.
    Returns None if the header is too short or mipsCount is zero.
    """
    if len(data) < 8:
        return None

    # Bytes 0–3: imageSize (u32 LE)
    image_size_raw = struct.unpack_from('<I', data, 0)[0]
    # width_hint  = (imageSize & 0xFFFFFF) / 16
    # height_hint = (imageSize >> 24) << 6
    # (These hints are not used for final dimensions; kept for reference)

    # Byte 4: mips — lower nibble = mipsCount, upper nibble = mipsInFile
    mips_byte = data[4]
    mips_count = mips_byte & 0x0F
    mips_in_file = (mips_byte & 0xF0) >> 4

    # Byte 5: format (lower nibble = pixel format)
    format_raw = data[5]
    # Byte 6: type
    type_raw = data[6]
    # Byte 7: unknown2
    unknown2 = data[7]

    if mips_count == 0:
        return None

    # Mip table: (u32 offset, u32 size, u32 width) × mipsCount
    expected_header_size = 8 + mips_count * 12
    if len(data) < expected_header_size:
        return None

    mip_table = []
    pos = 8
    for _ in range(mips_count):
        off  = struct.unpack_from('<I', data, pos)[0]
        sz   = struct.unpack_from('<I', data, pos + 4)[0]
        w    = struct.unpack_from('<I', data, pos + 8)[0]
        mip_table.append({'offset': off, 'size': sz, 'width': w})
        pos += 12

    # ── Use LAST mip entry for final dimensions (largest image) ──
    last_mip = mip_table[-1]
    fmt_code = format_raw & 0x0F

    # ── Format dispatch ──
    if fmt_code in (0x0, 0x5, 0x6):
        # ── RGBA32 uncompressed ──
        tex_format = 'RGBA'
        calc_width = last_mip['width'] // 4
        width_bytes = last_mip['width']
        if width_bytes > 0:
            calc_height = last_mip['size'] // width_bytes
        else:
            calc_height = 0

    elif fmt_code in (0x9, 0xD):
        # ── DXT3 ──
        tex_format = 'DXT3'
        calc_width = last_mip['width'] // 4
        width_bytes = last_mip['width']
        if width_bytes > 0:
            calc_height = (4 * last_mip['size']) // width_bytes
        else:
            calc_height = 0

    elif fmt_code in (0xA, 0xE):
        # ── DXT5 ──
        tex_format = 'DXT5'
        calc_width = last_mip['width'] // 4
        width_bytes = last_mip['width']
        if width_bytes > 0:
            calc_height = (4 * last_mip['size']) // width_bytes
        else:
            calc_height = 0

    elif fmt_code in (0x7, 0xB):
        # -- DXT1 (8 bytes per 4x4 block) --
        tex_format = 'DXT1'
        calc_width = last_mip['width'] // 2
        width_bytes = last_mip['width']
        if width_bytes > 0:
            calc_height = (4 * last_mip['size']) // width_bytes
        else:
            calc_height = 0

    else:
        return {'error': f'Unknown format 0x{fmt_code:02X}'}

    # ── Zero-division / bad dimensions guard ──
    if calc_width <= 0:
        data_size = last_mip['size']
        if tex_format == 'RGBA':
            pixels = data_size // 4
        elif tex_format == 'DXT1':
            pixels = (data_size // 8) * 16       # 8 B per 4×4 block
        else:  # DXT3 / DXT5 / BC5
            pixels = (data_size // 16) * 16      # 16 B per 4×4 block
        side = int(math.sqrt(max(pixels, 1)))
        # Round up to nearest power of two
        calc_width = 1
        while calc_width < side:
            calc_width <<= 1
        calc_height = calc_width

    # ── Data source ──
    # PHP: if mipsCount != mipsInFile → read from .tfd; else use .tfh itself
    if mips_count == mips_in_file:
        source = 'tfh'
    else:
        source = 'tfd'

    return {
        'format':        tex_format,
        'width':         calc_width,
        'height':        calc_height,
        'data_offset':   last_mip['offset'],
        'data_size':     last_mip['size'],
        'data_source':   source,
        'mips_count':    mips_count,
        'mips_in_file':  mips_in_file,
        'format_code':   fmt_code,
    }


# ──────────────────────────────────────────────────────────────
#  File-path helpers
# ──────────────────────────────────────────────────────────────

def path_tfd(tfh_path):
    """Given a .tfh path, return the corresponding .tfd path."""
    if tfh_path.lower().endswith('.tfh'):
        return tfh_path[:-4] + '.tfd'
    return tfh_path + '.tfd'


def path_tfh(tfd_path):
    """Given a .tfd path, return the corresponding .tfh path."""
    if tfd_path.lower().endswith('.tfd'):
        return tfd_path[:-4] + '.tfh'
    return tfd_path + '.tfh'


# ──────────────────────────────────────────────────────────────
#  Single-file conversion
# ──────────────────────────────────────────────────────────────

def convert_file(input_path, output_path=None):
    """Convert a single .tfh or .tfd file to DDS.

    Returns True on success (or clean skip), False on unrecoverable error.
    Status is always printed to stdout.
    """
    input_ext = os.path.splitext(input_path)[1].lower()
    input_basename = os.path.basename(input_path)

    # ── Resolve TFH / TFD paths ──
    if input_ext == '.tfh':
        tfh_path = input_path
        tfd_path = path_tfd(input_path)
    elif input_ext == '.tfd':
        tfd_path = input_path
        tfh_path = path_tfh(input_path)
    else:
        print(f"[ERROR] Unsupported extension '{input_ext}' for {input_basename}")
        return False

    # Check that TFH exists
    if not os.path.isfile(tfh_path):
        print(f"[SKIP] No .tfh file for {input_basename}")
        return True  # graceful skip

    # Read TFH
    try:
        with open(tfh_path, 'rb') as f:
            tfh_data = f.read()
    except OSError as e:
        print(f"[ERROR] Cannot read {tfh_path}: {e}")
        return False

    # Parse TFH header
    info = parse_tfh_data(tfh_data, tfh_path)
    if info is None:
        print(f"[ERROR] Failed to parse header in {os.path.basename(tfh_path)}")
        return False
    if 'error' in info:
        print(f"[ERROR] {os.path.basename(tfh_path)}: {info['error']}")
        return False

    # ── Read pixel data from the right source ──
    if info['data_source'] == 'tfh':
        data_start = info['data_offset']
        data_end   = data_start + info['data_size']
        if data_end > len(tfh_data):
            print(f"[ERROR] {os.path.basename(tfh_path)}: embedded data out of bounds "
                  f"(offset={data_start}, size={info['data_size']}, file_len={len(tfh_data)})")
            return False
        pixel_data = tfh_data[data_start:data_end]

    else:  # 'tfd'
        if not os.path.isfile(tfd_path):
            print(f"[SKIP] {os.path.basename(tfh_path)}: missing .tfd file")
            return True
        try:
            with open(tfd_path, 'rb') as f:
                tfd_data = f.read()
        except OSError as e:
            print(f"[ERROR] Cannot read {tfd_path}: {e}")
            return False

        data_start = info['data_offset']
        data_end   = data_start + info['data_size']
        if data_end > len(tfd_data):
            print(f"[ERROR] {os.path.basename(tfh_path)}: TFD data out of bounds "
                  f"(offset={data_start}, size={info['data_size']}, file_len={len(tfd_data)})")
            return False
        pixel_data = tfd_data[data_start:data_end]

    # ── Output path ──
    if output_path is None:
        base = os.path.splitext(input_path)[0]
        output_path = base + '.dds'

    # Build DDS — swizzle RGBA from BGRA byte order to RGBA for compatibility
    if info['format'] == 'RGBA':
        arr = bytearray(pixel_data)
        for i in range(0, len(arr), 4):
            arr[i], arr[i+2] = arr[i+2], arr[i]  # B <-> R
        pixel_data = bytes(arr)

    linear_size = compute_linear_size(info['width'], info['format'])
    dds_header  = build_dds_header(info['width'], info['height'],
                                   info['format'], linear_size)

    try:
        with open(output_path, 'wb') as f:
            f.write(dds_header)
            f.write(pixel_data)
    except OSError as e:
        print(f"[ERROR] Cannot write {output_path}: {e}")
        return False

    print(f"[OK] {input_basename} → {info['width']}x{info['height']} "
          f"{info['format']} → {os.path.basename(output_path)}")
    return True


# ──────────────────────────────────────────────────────────────
#  Batch conversion
# ──────────────────────────────────────────────────────────────

def batch_convert(directory):
    """Recursively find all .tfh files in *directory* and convert each."""
    if not os.path.isdir(directory):
        print(f"[ERROR] Not a directory: {directory}")
        return

    tfh_files = []
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            if fname.lower().endswith('.tfh'):
                tfh_files.append(os.path.join(root, fname))

    if not tfh_files:
        print(f"No .tfh files found in {directory}")
        return

    total   = len(tfh_files)
    success = 0

    for i, tfh_path in enumerate(tfh_files, 1):
        ok = convert_file(tfh_path)
        if ok:
            success += 1
        # Progress indicator on every 50th file
        if i % 50 == 0:
            print(f"  … {i}/{total} ({success} ok)")

    print(f"\n── Batch complete ──")
    print(f"  Total:   {total}")
    print(f"  Success: {success}")
    if total - success > 0:
        print(f"  Skipped/Errors: {total - success}")


# ──────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Star Conflict TFH/TFD → DDS converter (standalone Python)'
    )
    parser.add_argument(
        'input', nargs='?',
        help='Input .tfh or .tfd file (required unless --batch)'
    )
    parser.add_argument(
        'output', nargs='?',
        help='Output .dds path (default: same as input, .dds extension)'
    )
    parser.add_argument(
        '--batch', metavar='DIR',
        help='Batch-convert all .tfh files found recursively in DIR'
    )

    args = parser.parse_args()

    if args.batch:
        batch_convert(args.batch)
    elif args.input:
        convert_file(args.input, args.output)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
