"""
Star Conflict MSH → OBJ converter v2
Supports both simple (stride=24) and skinned (stride=36+) mesh formats.
Auto-detects stride from vertex/index counts in header.
"""
import struct, os, sys
from collections import Counter

def detect_format(data):
    """Detect MSH format and return (header_size, vert_count, idx_count, stride)"""
    if len(data) < 68:
        return None
    
    hdr = [struct.unpack_from("<I", data, i)[0] for i in range(0, 68, 4)]
    
    if hdr[0] != 0:
        return None  # Not a simple MSH
    
    # Cube1m: hdr[2]=24(vc), hdr[4]=36(ic), stride=24
    # Destroyerring: hdr[3]=31619(vc), hdr[4]=92301(ic), stride=36
    # The pattern: find which header field is vertex count by matching with file size
    
    candidates = [(2, 24), (3, 12), (4, 16)]  # (hdr_index, stride offset)
    
    for hdr_idx, stride_base in [(2, 12), (3, 12), (4, 16)]:
        vc = hdr[hdr_idx] if hdr_idx < len(hdr) else 0
        ic = hdr[4] if 4 < len(hdr) else 0  # Usually hdr[4] = index count
        
        if vc < 3 or vc > 200000 or ic < 3:
            continue
        
        for stride in range(12, 64, 4):
            predicted = 68 + vc * stride + ic * 2
            if abs(predicted - len(data)) < 100:
                return 68, vc, ic, stride
    
    return None

def parse_msh(data):
    """Parse MSH file, returns (vertices, indices)"""
    fmt = detect_format(data)
    if fmt is None:
        raise ValueError("Cannot detect MSH format - may be compressed")
    
    HDR, VC, IC, STRIDE = fmt
    print(f"  Format: {VC} verts × {STRIDE}B, {IC} indices, header={HDR}B")
    
    vertices = []
    for i in range(VC):
        off = HDR + i * STRIDE
        x, y, z = struct.unpack_from("<fff", data, off)
        vertices.append((x, y, z))
    
    idx_start = HDR + VC * STRIDE
    indices = struct.unpack_from(f"<{IC}H", data, idx_start)
    
    return vertices, list(indices)

def write_obj(vertices, indices, output_path, name="model"):
    with open(output_path, "w") as f:
        f.write(f"# Star Conflict MSH → OBJ\n# Model: {name}\n")
        f.write(f"# Vertices: {len(vertices)}, Triangles: {len(indices)//3}\n\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        f.write("\n")
        for i in range(0, len(indices)-2, 3):
            f.write(f"f {indices[i]+1} {indices[i+1]+1} {indices[i+2]+1}\n")
    
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    print(f"  OBJ: {output_path}")
    print(f"  Bounds: X[{min(xs):.3f},{max(xs):.3f}] Y[{min(ys):.3f},{max(ys):.3f}] Z[{min(zs):.3f},{max(zs):.3f}]")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help=".mdl-msh file")
    parser.add_argument("-o", "--output", help="Output OBJ")
    args = parser.parse_args()
    
    with open(args.input, "rb") as f:
        data = f.read()
    
    verts, idxs = parse_msh(data)
    out = args.output or args.input + ".obj"
    write_obj(verts, idxs, out, os.path.basename(args.input))
