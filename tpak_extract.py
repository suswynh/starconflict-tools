"""
Star Conflict TPAK v7 Extractor - Verified implementation
Based on: Johnnynator/tpak + reverse engineering
"""
import struct
import zlib
import os
import sys

def decode_nametable(nametable, file_count):
    """XOR decode filename table entries"""
    names = []
    pos = 0
    for i in range(file_count):
        if pos + 4 > len(nametable):
            break
        entry_len = struct.unpack_from("<I", nametable, pos)[0]
        pos += 4
        if entry_len <= 0 or entry_len > 4096 or pos + entry_len > len(nametable):
            break
        
        name_bytes = bytearray(nametable[pos:pos+entry_len])
        mask = (entry_len % 5) + i
        for j in range(entry_len):
            name_bytes[j] ^= (((j + entry_len) * 2) + mask) & 0xFF
        
        name = name_bytes.decode('ascii', errors='replace').rstrip('\x00')
        name = name.replace('\\', '/')
        names.append(name)
        # C: nametable += sizeof(uint32_t) + sizeof(char)*entry->length + 1
        pos += entry_len + 1
    return names

def xor4(buf, key):
    """XOR first 4 bytes of buffer with key (in-place)"""
    for i in range(4):
        buf[i] ^= (key >> (i * 8)) & 0xFF

def try_decompress(data, uncomp_size):
    """Try raw deflate decompression"""
    return zlib.decompress(bytes(data), -15, uncomp_size)

def scan_valid_int32(data, start, length, min_val=1, max_val=100*1024*1024):
    """Find the first valid-looking int32 in a range, checking ALL byte offsets"""
    for off in range(start, start + length):
        if off + 4 > len(data):
            break
        val = struct.unpack_from("<I", data, off)[0]
        if min_val <= val <= max_val:
            return off
    return start

def read_tpak(filepath, verbose=False):
    """Parse a TPAK v7 file, returns (names, files, chunks, data_start, raw_data)"""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    pos = 0
    
    # === HEADER ===
    magic = data[pos:pos+4]
    if magic != b'TPAK':
        raise ValueError(f"Invalid magic: {magic}")
    pos += 4
    
    version = struct.unpack_from("<I", data, pos)[0]
    if version != 7 and verbose:
        print(f"  Warning: version {version}, expected 7")
    pos += 4
    pos += 4  # flags
    
    file_count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    pos += 4  # reserved (0xFFFFFFE3)
    
    uncomp_ns = struct.unpack_from("<I", data, pos)[0]; pos += 4
    comp_ns = struct.unpack_from("<I", data, pos)[0]; pos += 4
    
    if verbose:
        print(f"  Version={version}, files={file_count}, nametable: {comp_ns}->{uncomp_ns}")
    
    # === NAMETABLE ===
    comp_nt = bytearray(data[pos:pos+comp_ns])
    xor4(comp_nt, file_count)
    try:
        nametable = try_decompress(comp_nt, uncomp_ns)
    except zlib.error as e:
        print(f"  ERROR: nametable decompress failed: {e}")
        return None
    names = decode_nametable(nametable, file_count)
    pos += comp_ns
    
    if verbose:
        print(f"  Parsed {len(names)} filenames")
    
    # === FILE INDEX TABLE (skip) ===
    # Index table may have variable structure; skip based on known length
    # but also support scanning if offset is wrong
    idx_start = pos
    idx_size = file_count * 4
    
    # Try direct skip first
    pos += idx_size
    
    # === FILE DATA TABLE ===
    # Scan for valid comp_ft_size (should be smaller than uncompressed)
    uncomp_ft_size = file_count * 16
    # Scan forward up to 256 bytes to find the real filetable header
    found = False
    for scan_off in range(pos, min(pos + 256, len(data) - 4)):
        test_size = struct.unpack_from("<I", data, scan_off)[0]
        # comp_ft_size should be: less than uncompressed, and reasonable
        if 10 <= test_size <= uncomp_ft_size * 3:
            # Also validate that next bytes could be compressed data
            # (not all zeros, not matching index table patterns)
            next_bytes = data[scan_off+4:scan_off+12]
            if next_bytes.count(0) < 4:  # Not all zeros
                # Try to decompress
                test_data = bytearray(data[scan_off+4:scan_off+4+test_size])
                xor4(test_data, file_count + test_size)
                try:
                    try_decompress(test_data, uncomp_ft_size)
                    # Success! This is the filetable
                    if scan_off != pos and verbose:
                        print(f"  Filetable offset adjusted by {scan_off - pos} bytes")
                    comp_ft_size = test_size
                    pos = scan_off + 4
                    found = True
                    break
                except:
                    pass
    else:
        pos = idx_start + idx_size  # Reset
    
    if not found:
        # Fallback: use scan_valid_int32 with wider range
        ft_start = scan_valid_int32(data, pos, 512, 10, uncomp_ft_size * 5)
        comp_ft_size = struct.unpack_from("<I", data, ft_start)[0]
        if ft_start != pos and verbose:
            print(f"  Filetable padding: {ft_start - pos} bytes")
        pos = ft_start + 4
    uncomp_ft_size = file_count * 16
    
    if verbose:
        print(f"  Filetable: comp={comp_ft_size}, uncomp={uncomp_ft_size}")
    
    comp_ft = bytearray(data[pos:pos+comp_ft_size])
    xor4(comp_ft, file_count + comp_ft_size)
    try:
        filetable_raw = try_decompress(comp_ft, uncomp_ft_size)
    except zlib.error as e:
        print(f"  ERROR: filetable decompress: {e}")
        return None
    pos += comp_ft_size
    
    # Parse file entries: {file_size, name_offset, chunk_count, chunk_index}
    files = []
    for i in range(file_count):
        off = i * 16
        file_size, name_offset, chunk_count, chunk_index = \
            struct.unpack_from("<iiii", filetable_raw, off)
        files.append({
            'file_size': file_size,
            'name_offset': name_offset,
            'chunk_count': chunk_count,
            'chunk_index': chunk_index,
        })
    
    # === FILE CHUNK TABLE ===
    # Align to 4 bytes
    pos = (pos + 3) & ~3
    
    comp_cs_size = struct.unpack_from("<I", data, pos)[0]; pos += 4
    total_chunks = struct.unpack_from("<I", data, pos)[0]; pos += 4
    
    if verbose:
        print(f"  Chunktable: comp={comp_cs_size}, chunks={total_chunks}")
    
    comp_cs = bytearray(data[pos:pos+comp_cs_size])
    xor4(comp_cs, file_count + comp_cs_size + total_chunks)
    uncomp_cs_size = total_chunks * 16
    try:
        chunk_raw = try_decompress(comp_cs, uncomp_cs_size)
    except zlib.error as e:
        print(f"  ERROR: chunktable decompress: {e}")
        return None
    pos += comp_cs_size
    
    # Parse chunk entries: {unkwn, uncompressed_size, data_offset, compressed_size}
    chunks = []
    for i in range(total_chunks):
        off = i * 16
        unkwn, unc_size, data_off, comp_size = \
            struct.unpack_from("<iiii", chunk_raw, off)
        chunks.append({
            'unkwn': unkwn,
            'uncompressed_size': unc_size,
            'data_offset': data_off,
            'compressed_size': comp_size,
        })
    
    data_start = pos
    
    if verbose:
        total_data = sum(f['file_size'] for f in files if f['file_size'] > 0)
        print(f"  Data starts @0x{data_start:04X}, total files: {len(names)}, {total_data:,} bytes")
    
    return names, files, chunks, data_start, data

def extract_file(raw_data, chunks, file_entry, data_start, name):
    """Extract and decompress a single file from TPAK"""
    chunk_idx = file_entry['chunk_index']
    chunk_count = file_entry['chunk_count']
    
    if chunk_idx + chunk_count > len(chunks):
        if chunk_count > 0:
            print(f"    WARNING: chunk index out of range for {name}")
        return None
    
    result = bytearray()
    for i in range(max(1, chunk_count)):  # At least 1 chunk
        ch = chunks[chunk_idx + i]
        chunk_data = raw_data[data_start + ch['data_offset']:
                              data_start + ch['data_offset'] + ch['compressed_size']]
        
        if ch['compressed_size'] == 0 and ch['uncompressed_size'] == 0:
            break  # End marker
            
        if ch['compressed_size'] == ch['uncompressed_size']:
            result.extend(chunk_data)
        elif ch['compressed_size'] > 0:
            try:
                decomp = zlib.decompress(chunk_data, -15, ch['uncompressed_size'])
                result.extend(decomp)
            except zlib.error:
                try:
                    decomp = zlib.decompress(chunk_data)
                    result.extend(decomp)
                except zlib.error:
                    result.extend(chunk_data)  # Store as-is
    
    return bytes(result)

def extract_all(pak_path, output_dir, file_types=None):
    """Extract all files from a TPAK archive"""
    basename = os.path.splitext(os.path.basename(pak_path))[0]
    pak_out_dir = os.path.join(output_dir, basename)
    
    print(f"Processing: {os.path.basename(pak_path)}")
    result = read_tpak(pak_path, verbose=True)
    if result is None:
        return False
    
    names, files, chunks, data_start, raw_data = result
    os.makedirs(pak_out_dir, exist_ok=True)
    
    success = 0
    failed = 0
    
    for i, (name, fe) in enumerate(zip(names, files)):
        if file_types:
            ext = os.path.splitext(name)[1].lower()
            if ext not in file_types:
                continue
        
        try:
            file_data = extract_file(raw_data, chunks, fe, data_start, name)
            if file_data is None:
                print(f"  [{i}] FAILED: {name}")
                failed += 1
                continue
            
            out_path = os.path.join(pak_out_dir, name)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'wb') as f:
                f.write(file_data)
            
            if (i + 1) % 100 == 0:
                print(f"  [{i+1}/{len(names)}] ...")
            success += 1
        except Exception as e:
            print(f"  [{i}] ERROR {name}: {e}")
            failed += 1
    
    print(f"  Done: {success} extracted, {failed} failed")
    return True

def list_files(pak_path):
    """List all files in a TPAK archive"""
    print(f"Listing: {os.path.basename(pak_path)}")
    result = read_tpak(pak_path, verbose=True)
    if result is None:
        return
    
    names, files, chunks, data_start, raw_data = result
    
    total_size = 0
    for i, (name, fe) in enumerate(zip(names, files)):
        size = fe['file_size']
        total_size += max(0, size)
        ci = f" [{fe['chunk_count']}c]" if fe['chunk_count'] > 1 else ""
        print(f"  [{i:4d}] {size:>10d}{ci}  {name}")
    
    print(f"\n  Total: {len(names)} files, {total_size:,} bytes uncompressed")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Star Conflict TPAK v7 Extractor')
    parser.add_argument('path', help='Path to .pak file or data directory')
    parser.add_argument('-o', '--output', default='./extracted', help='Output directory')
    parser.add_argument('-l', '--list', action='store_true', help='List files only')
    parser.add_argument('-t', '--type', help='Filter by extension (e.g. .dds,.tga)')
    
    args = parser.parse_args()
    
    file_types = None
    if args.type:
        file_types = set(args.type.lower().split(','))
    
    if os.path.isdir(args.path):
        pak_files = sorted([f for f in os.listdir(args.path) if f.endswith('.pak')])
        print(f"Found {len(pak_files)} .pak files")
        for p in pak_files:
            print(f"\n{'='*60}")
            try:
                if args.list:
                    list_files(os.path.join(args.path, p))
                else:
                    extract_all(os.path.join(args.path, p), args.output, file_types)
            except Exception as e:
                print(f"  ERROR: {e}")
    else:
        if args.list:
            list_files(args.path)
        else:
            extract_all(args.path, args.output, file_types)
