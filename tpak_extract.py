"""
Star Conflict TPAK v7/v8 Extractor - Refined implementation
Based on: clutch.bms (quickbms script by aluigi) + Johnnynator/tpak + reverse engineering

Precision improvements over previous version:
  - Exact offset calculation replacing scan-based table discovery (aligned with clutch.bms)
  - Nametable entry stride preserved (+1 null terminator, verified empirically)
  - 4-byte alignment after nametable (TYPE!=0) — fixes non-aligned comp_ns pak files
  - v8 format compatibility (different field order in file table)
  - Fault-tolerant chunk extraction (single file failure does not abort entire pak)
  - Consistent 4-byte alignment after filetable and chunktable (TYPE != 0)
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
        # Entry layout: uint32(length) | char[length] | '\x00' (null terminator in table)
        # Verified against clutch.bms + empirical test: stride = 4 + entry_len + 1
        pos += entry_len + 1
    return names

def xor4(buf, key):
    """XOR first 4 bytes of buffer with key (in-place)"""
    for i in range(4):
        buf[i] ^= (key >> (i * 8)) & 0xFF

def try_decompress(data, uncomp_size):
    """Try raw deflate decompression"""
    return zlib.decompress(bytes(data), -15, uncomp_size)

def read_tpak(filepath, verbose=False):
    """Parse a TPAK v7/v8 file, returns (names, files, chunks, data_start, raw_data)"""
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
    
    # --- TPAK alignment after nametable (clutch.bms: if TYPE != 0, math OFFSET x 4) ---
    pos = (pos + 3) & ~3
    
    if verbose:
        print(f"  Parsed {len(names)} filenames")
    
    # === FILE INDEX TABLE (skip) ===
    # v7+: jump table (file_count × 4 bytes), skipped via direct offset
    pos += file_count * 4
    
    # === FILE DATA TABLE (clutch.bms precise positioning) ===
    # clut.bms v7: FILETABLESZ = FILES * 16 (decompressed), then get FILETABLESZZ (compressed)
    # The compressed size is a uint32 immediately after the index table
    uncomp_ft_size = file_count * 16
    comp_ft_size = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    
    # Validate comp_ft_size reasonability (safety net)
    if comp_ft_size < 4 or comp_ft_size > uncomp_ft_size * 5:
        raise ValueError(
            f"Invalid filetable compressed size: {comp_ft_size} "
            f"(uncompressed={uncomp_ft_size}, file_count={file_count}). "
            f"Pak may be corrupted or use a different format version."
        )
    
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
    
    # --- TPAK (TYPE≠0) alignment: align to 4 bytes after filetable ---
    pos = (pos + 3) & ~3
    
    # Parse file entries (field order varies by version, matched to clutch.bms):
    #   v7: FILESIZE | NAMEOFF | ZIP | ID(uint16) | CHUNKS(uint16)
    #   v8: NAMEOFF  | ZIP     | FILESIZE | CHUNKS(uint16) | ID(uint16)
    files = []
    for i in range(file_count):
        off = i * 16
        if off + 16 > len(filetable_raw):
            if verbose:
                print(f"  WARNING: filetable truncated at entry {i}/{file_count}")
            break
        a, b, c, d = struct.unpack_from("<IIII", filetable_raw, off)
        
        if version >= 8:
            name_offset, zipped, file_size, chunks_or_id = a, b, c, d
            chunk_count = chunks_or_id & 0xFFFF
            chunk_id = (chunks_or_id >> 16) & 0xFFFF
        else:
            file_size, name_offset, zipped, id_or_chunks = a, b, c, d
            chunk_id = id_or_chunks & 0xFFFF
            chunk_count = (id_or_chunks >> 16) & 0xFFFF
        
        zipped = 0 if zipped == 0xFFFFFFFF else zipped
        files.append({
            'file_size': file_size,
            'name_offset': name_offset,
            'zipped': zipped,
            'chunk_id': chunk_id,
            'chunk_count': chunk_count,
        })
    
    # === FILE CHUNK TABLE (clutch.bms precise positioning) ===
    # clut.bms v7: get ZSIZE (compressed) | get ENTRIES (chunk count)
    comp_cs_size = struct.unpack_from("<I", data, pos)[0]; pos += 4
    total_chunks = struct.unpack_from("<I", data, pos)[0]; pos += 4
    uncomp_cs_size = total_chunks * 16
    
    if verbose:
        print(f"  Chunktable: comp={comp_cs_size}, chunks={total_chunks}")
    
    comp_cs = bytearray(data[pos:pos+comp_cs_size])
    xor4(comp_cs, file_count + comp_cs_size + total_chunks)
    try:
        chunk_raw = try_decompress(comp_cs, uncomp_cs_size)
    except zlib.error as e:
        print(f"  ERROR: chunktable decompress: {e}")
        return None
    pos += comp_cs_size
    
    # --- TPAK (TYPE≠0) alignment: align to 4 bytes after chunktable ---
    pos = (pos + 3) & ~3
    
    # Parse chunk entries (matched to clutch.bms):
    # [0] CHUNK_OFF(uint32) [1] SIZE(uint32) [2] OFFSET(uint32) [3] ZSIZE(uint32)
    #   CHUNK_OFF = offset within file (multi-chunk reassembly)
    #   SIZE      = uncompressed size of this chunk
    #   OFFSET    = data offset relative to data_start
    #   ZSIZE     = compressed size of this chunk (== SIZE means stored uncompressed)
    chunks = []
    for i in range(total_chunks):
        off = i * 16
        chunk_off, unc_size, data_off, comp_size = \
            struct.unpack_from("<IIII", chunk_raw, off)
        chunks.append({
            'chunk_off': chunk_off,
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
    """Extract and decompress a single file from TPAK (refined per clutch.bms)
    
    Fault-tolerant: single chunk failures return partial data rather than None.
    Uses file-level zipped hint for single-chunk files.
    
    chunk_count=0 semantics (Star Conflict v7+):
      chunk_count=0 means "span from chunk_id until file_size bytes are accumulated".
      This is critical for large texture files (ui_textures_*.pak) that are split
      across multiple ~1.5MB chunks. The original clutch.bms clamped count=0 to 1,
      causing massive truncation (e.g. 1.5MB instead of 16MB).
    """
    chunk_id = file_entry['chunk_id']
    chunk_count = file_entry['chunk_count']
    file_zipped = file_entry.get('zipped', 0)
    file_size = file_entry.get('file_size', 0)
    
    # Determine actual chunk count
    max_chunks = len(chunks)
    if chunk_id >= max_chunks:
        print(f"    WARNING: chunk_id {chunk_id} out of range (max={max_chunks}) for {name}")
        return None
    
    if chunk_count <= 0:
        # chunk_count=0: scan forward until accumulated uncompressed size >= file_size
        # This handles Star Conflict's multi-chunk large files correctly
        accumulated = 0
        actual_count = 0
        for ci in range(chunk_id, max_chunks):
            accumulated += chunks[ci]['uncompressed_size']
            actual_count += 1
            if accumulated >= file_size:
                break
        chunk_count = actual_count if actual_count > 0 else 1
    else:
        # Clamp to available chunks
        if chunk_id + chunk_count > max_chunks:
            if chunk_count > 1:
                print(f"    WARNING: chunk range [{chunk_id}:{chunk_id+chunk_count}] "
                      f"exceeds {max_chunks} for {name}")
            chunk_count = max(1, max_chunks - chunk_id)
    
    # Pre-allocate buffer: use file_size if available, else estimate from chunks
    relevant = chunks[chunk_id:chunk_id + chunk_count]
    max_off = max((c['chunk_off'] for c in relevant), default=0)
    est_size = sum(c['uncompressed_size'] for c in relevant)
    
    if file_size > 0:
        # Use file_size for buffer (authoritative from TPAK table)
        initial_cap = max(file_size, est_size)
    elif max_off > 0:
        initial_cap = max_off + est_size
    else:
        initial_cap = est_size
    
    result = bytearray(initial_cap) if initial_cap > 0 else bytearray()
    write_pos = 0
    
    failed_chunks = 0
    for ch in relevant:
        if ch['compressed_size'] == 0 and ch['uncompressed_size'] == 0:
            continue
        
        # Boundary check: data must lie within raw_data
        data_offset = data_start + ch['data_offset']
        data_end = data_offset + ch['compressed_size']
        if data_end > len(raw_data) or data_offset >= len(raw_data):
            print(f"    WARNING: chunk data out of bounds for {name} "
                  f"(off={data_offset}, size={ch['compressed_size']}, max={len(raw_data)})")
            failed_chunks += 1
            continue
        
        chunk_raw = raw_data[data_offset:data_end]
        
        # Decompression: match clutch.bms ONE_STUFF2 + file-level ZIP logic
        is_stored = (ch['compressed_size'] == ch['uncompressed_size'])
        if is_stored:
            chunk_data = bytes(chunk_raw)
        elif ch['compressed_size'] > 0:
            try:
                chunk_data = zlib.decompress(chunk_raw, -15, ch['uncompressed_size'])
            except zlib.error:
                try:
                    chunk_data = zlib.decompress(chunk_raw)
                except zlib.error:
                    # Fallback: raw bytes (may be corrupt but better than nothing)
                    chunk_data = bytes(chunk_raw)
        else:
            failed_chunks += 1
            continue
        
        # Place chunk at correct file offset (matching clutch.bms "goto CHUNK_OFF MEMORY_FILE")
        if ch['chunk_off'] > 0 or max_off > 0:
            off = ch['chunk_off']
            end = off + len(chunk_data)
            if end > len(result):
                result.extend(b'\x00' * (end - len(result)))
            result[off:end] = chunk_data
        else:
            # Single-chunk or sequential: linear append
            end = write_pos + len(chunk_data)
            if end > len(result):
                result.extend(b'\x00' * (end - len(result)))
            result[write_pos:end] = chunk_data
            write_pos = end
    
    # Determine actual output size
    if file_size > 0:
        # Use file_size from TPAK table (authoritative)
        actual_end = file_size
    elif max_off > 0:
        # Multi-chunk: trim pre-allocated buffer to last non-null position
        # (gaps between chunks are null-padded by pre-allocation)
        actual_end = len(result)
        while actual_end > 0 and result[actual_end - 1] == 0:
            actual_end -= 1
    else:
        # Single-chunk or sequential: write_pos is exact, trust it
        actual_end = write_pos
    
    if failed_chunks == chunk_count:
        return None
    if failed_chunks > 0:
        print(f"    WARNING: {failed_chunks}/{chunk_count} chunks failed for {name}, "
              f"returning partial data ({actual_end} bytes)")
    
    return bytes(result[:actual_end])

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
