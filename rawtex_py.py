"""
Star Conflict / Hammer Engine DDSx → DDS converter
Replaces rawtex for batch texture conversion.
Parses TFH to get format/size/offset, rebuilds valid DDS.
"""
import struct, os, sys

# DDS FourCC codes
FOURCC = {
    'DXT1': b'DXT1', 'DXT3': b'DXT3', 'DXT5': b'DXT5',
    'BC1': b'DXT1', 'BC3': b'DXT5', 'BC5': b'ATI2',
}

def build_dds_header(width, height, fourcc, mip_count=1):
    """Build a 128-byte DDS header"""
    flags = 0x000A1007  # CAPS|HEIGHT|WIDTH|PIXELFORMAT|MIPMAPCOUNT|LINEARSIZE
    caps = 0x00401008   # TEXTURE|COMPLEX|MIPMAP

    if isinstance(fourcc, str):
        fourcc = FOURCC.get(fourcc.upper(), fourcc.encode())

    pitch = max(1, (width + 3) // 4) * 8 if fourcc[:3] == b'DXT' else width * 4

    hdr = struct.pack('<I', 124)       # dwSize
    hdr += struct.pack('<I', flags)
    hdr += struct.pack('<I', height)
    hdr += struct.pack('<I', width)
    hdr += struct.pack('<I', pitch)
    hdr += struct.pack('<I', 0)         # depth
    hdr += struct.pack('<I', mip_count)
    hdr += b'\x00' * 44                 # reserved
    hdr += struct.pack('<I', 32)        # pfSize
    hdr += struct.pack('<I', 4)         # pfFlags = DDPF_FOURCC
    hdr += fourcc.ljust(4, b'\x00')[:4]
    hdr += struct.pack('<I', 0) * 5     # RGBBitCount + masks
    hdr += struct.pack('<I', caps)
    hdr += struct.pack('<I', 0) * 4     # reserved2
    return hdr

def parse_simple_tfh(tfh_data):
    """Parse a clean (uncompressed) TFH file"""
    if len(tfh_data) < 8:
        return None

    vals = struct.unpack_from(f'<{len(tfh_data)//4}I', tfh_data, 0)
    
    # TFH[0] = magic (e.g. 0x10008000)
    # TFH[1] = data offset in TFD
    magic = vals[0]
    data_offset = vals[1]
    
    if data_offset <= 0 or data_offset > 100000:
        return None
    
    # Parse MIP table: vals[2+] = {?, width, height} triples
    mips = []
    i = 2
    while i < len(vals) - 2:
        sz_or_off = vals[i]
        w = vals[i+1]
        h = vals[i+2]
        # Valid mip: dimensions should be powers of 2, reasonable
        if 1 <= w <= 16384 and 1 <= h <= 16384 and sz_or_off < 10000000:
            mips.append((w, h, sz_or_off))
            i += 3
        else:
            # Might be the start of unknown data
            break
    
    if not mips:
        return None
    
    # Take the largest mip as base dimensions
    base_w, base_h, _ = max(mips, key=lambda x: x[0] * x[1])
    
    return {
        'data_offset': data_offset,
        'base_width': base_w,
        'base_height': base_h,
        'mip_count': len(mips),
        'magic': magic,
    }

def detect_format(tfd_data, data_offset, width, height):
    """Detect texture format based on file size and dimensions"""
    data_size = len(tfd_data) - data_offset
    
    # Try matching known formats
    # DXT1: w*h/2 bytes per mip
    # DXT5: w*h bytes per mip
    # RGBA: w*h*4 bytes per mip
    
    total_mips = 1
    while (width >> total_mips) >= 4 and (height >> total_mips) >= 4:
        total_mips += 1
    
    for fmt, mult in [('DXT1', 0.5), ('DXT5', 1.0), ('RGBA', 4.0)]:
        expected = 0
        w, h = width, height
        for _ in range(total_mips):
            expected += max(1, int(w * h * mult))
            w = max(1, w // 2)
            h = max(1, h // 2)
        if abs(expected - data_size) < max(expected * 0.1, 1024):
            return fmt, total_mips
    
    # Default fallback
    return 'DXT5', 1

def convert_tfd(tfd_path, output_path=None):
    """Convert a .tfd/.dds file using its .tfh counterpart"""
    if tfd_path.endswith('.tfd'):
        tfh_path = tfd_path[:-4] + '.tfh'
    else:
        tfh_path = tfd_path[:-4] + '.tfh'
    
    if not os.path.exists(tfh_path):
        print(f"  SKIP: no .tfh for {os.path.basename(tfd_path)}")
        return False
    
    with open(tfh_path, 'rb') as f:
        tfh = f.read()
    with open(tfd_path, 'rb') as f:
        tfd = f.read()
    
    info = parse_simple_tfh(tfh)
    if info is None:
        return False  # Compressed TFH, skip
    
    fmt, mips = detect_format(tfd, info['data_offset'], 
                               info['base_width'], info['base_height'])
    
    # Build DDS
    hdr = build_dds_header(info['base_width'], info['base_height'], fmt, mips)
    
    if output_path is None:
        output_path = tfd_path + '_real.dds'
    
    with open(output_path, 'wb') as f:
        f.write(b'DDS ')
        f.write(hdr)
        f.write(tfd[info['data_offset']:])
    
    return True

def auto_detect_and_convert(tfd_data, output_path):
    """Try to auto-detect texture format and dimensions from raw data"""
    data_size = len(tfd_data)
    
    # Common texture sizes (powers of 2)
    sizes = [256, 512, 1024, 2048, 4096, 8192]
    formats = [('DXT1', 0.5), ('DXT5', 1.0)]
    
    best_match = None
    best_diff = float('inf')
    
    for w in sizes:
        for h in sizes:
            for fmt_name, bpp in formats:
                for mips in range(1, 12):
                    total = 0
                    cw, ch = w, h
                    for _ in range(mips):
                        total += max(1, int(cw * ch * bpp))
                        cw = max(1, cw // 2)
                        ch = max(1, ch // 2)
                    diff = abs(total - data_size)
                    if diff < data_size * 0.02 and diff < best_diff:
                        best_diff = diff
                        best_match = (w, h, fmt_name, mips, 0)  # offset=0
    
    if best_match:
        w, h, fmt, mips, off = best_match
        hdr = build_dds_header(w, h, fmt, mips)
        with open(output_path, 'wb') as f:
            f.write(b'DDS ')
            f.write(hdr)
            f.write(tfd_data[off:])
        return True
    return False

def batch_convert(root_dir, auto_mode=False):
    """Convert all TFD/DDS files"""
    total = 0
    success = 0
    simple_ok = 0
    auto_ok = 0
    skipped = 0
    
    for dirpath, dirs, files in os.walk(root_dir):
        for f in files:
            if not f.endswith('.tfd') and not (f.endswith('.dds') and not f.endswith('_real.dds')):
                continue
            tfd_path = os.path.join(dirpath, f)
            tfh_path = tfd_path.replace('.tfd', '.tfh').replace('.dds', '.tfh')
            
            if not os.path.exists(tfh_path):
                continue
            
            total += 1
            out_path = os.path.join(dirpath, os.path.splitext(f)[0] + '_real.dds')
            
            # Try TFH first
            with open(tfh_path, 'rb') as fh:
                tfh = fh.read()
            
            info = parse_simple_tfh(tfh)
            if info is not None:
                if convert_tfd(tfd_path, out_path):
                    success += 1
                    simple_ok += 1
                    if success % 100 == 0:
                        print(f"  [{success}] ...")
                continue
            
            # Try auto-detect for compressed TFH
            if auto_mode:
                with open(tfd_path, 'rb') as fh:
                    tfd = fh.read()
                if auto_detect_and_convert(tfd, out_path):
                    success += 1
                    auto_ok += 1
                    if success % 100 == 0:
                        print(f"  [{success}] (auto) ...")
                else:
                    skipped += 1
            else:
                skipped += 1
    
    print(f"\nResults: {total} texture pairs found")
    print(f"  Simple TFH: {simple_ok}")
    if auto_mode:
        print(f"  Auto-detect: {auto_ok}")
    print(f"  Skipped: {skipped}")
    print(f"  Total converted: {success}")
    print(f"  Output: *_real.dds files")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Convert Star Conflict DDSx→DDS')
    parser.add_argument('path', help='.tfd/.dds file or directory')
    parser.add_argument('--auto', action='store_true', help='Auto-detect for compressed TFH textures')
    args = parser.parse_args()
    
    if os.path.isdir(args.path):
        batch_convert(args.path, auto_mode=args.auto)
    else:
        out = args.path + '_real.dds' if args.path.endswith('.tfd') else args.path.replace('.dds', '_real.dds')
        if convert_tfd(args.path, out):
            print(f"Converted: {out}")
        else:
            print("Failed - compressed TFH, try --auto")
