"""
Star Conflict MSH → OBJ converter v3
Based on fmt_StarConflict_mdl-msh000.py (Noesis plugin) + original auto-detect.
Supports: version 0-3, VBytes 24/28/32/36, UV export.
"""
import struct, os, sys

def parse_msh_header(data):
    """
    基于 Noesis 脚本的格式解析。
    .mdl-msh000 ~ .mdl-msh009 格式:
      [0x00] version  (0/1/2/3)
      [0x04] flag
      [0x08] VBytes   (每顶点字节数: 24/28/32/36)
      [0x0C] VCount   (顶点数)
      [0x10] FCount   (面索引数)
      [0x14-0x43] ?   (未知/保留)
      [0x44] 顶点数据开始
    """
    if len(data) < 0x44 + 8:
        return None

    version = struct.unpack_from("<I", data, 0)[0]
    flag    = struct.unpack_from("<I", data, 4)[0]
    vbytes  = struct.unpack_from("<I", data, 8)[0]
    vcount  = struct.unpack_from("<I", data, 12)[0]
    fcount  = struct.unpack_from("<I", data, 16)[0]

    # 基本校验
    if version > 200:
        return None
    if vbytes not in (20, 24, 28, 32, 36, 40):
        return None
    if vcount < 3 or vcount > 500000:
        return None
    if fcount < 3 or fcount > 1000000:
        return None

    # 校验文件大小
    expected = 0x44 + vcount * vbytes + fcount * 2
    if abs(expected - len(data)) > 100:
        return None

    return {
        'version': version,
        'flag': flag,
        'vbytes': vbytes,
        'vcount': vcount,
        'fcount': fcount,
        'vert_off': 0x44,
        'idx_off': 0x44 + vcount * vbytes,
    }


def detect_format_legacy(data):
    """
    回退方案: 自动检测旧格式 (header=68, stride 自动推导)
    """
    if len(data) < 68 + 12:
        return None

    hdr = [struct.unpack_from("<I", data, i)[0] for i in range(0, 68, 4)]

    # 简单 MSH: hdr[0]==0, hdr[4] 是小整数
    if hdr[0] != 0:
        return None

    for hdr_idx, stride_list in [(2, [12, 24, 20]), (3, [36, 32, 28, 24, 12])]:
        vc = hdr[hdr_idx] if hdr_idx < len(hdr) else 0
        ic = hdr[4] if 4 < len(hdr) else 0

        if vc < 3 or vc > 200000 or ic < 3 or ic > 1000000:
            continue

        for stride in stride_list:
            predicted = 68 + vc * stride + ic * 2
            if abs(predicted - len(data)) < 100:
                return {
                    'version': 0,
                    'flag': 0,
                    'vbytes': stride,
                    'vcount': vc,
                    'fcount': ic,
                    'vert_off': 68,
                    'idx_off': 68 + vc * stride,
                }

    return None


def get_uv_offset(vbytes, flag):
    """获取 UV 坐标在顶点结构中的字节偏移"""
    if vbytes == 20:
        return 12   # pos@0(12B), UV@12(8B)
    elif vbytes == 24:
        return 16   # pos@0(12B), ?(4B), UV@16(8B)
    elif vbytes == 28:
        if flag in (0xE, 5):
            return 16   # pos@0(12B), ?(4B), UV@16(8B), ?(4B)
        elif flag == 0x11:
            return 20   # pos@0(12B), ?(8B), UV@20(8B)
        else:
            return 16   # 默认
    elif vbytes == 32:
        return 20   # pos@0(12B), ?(8B), UV@20(8B), ?(4B)
    elif vbytes == 36:
        return 20   # pos@0(12B), ?(8B), UV@20(8B), ?(8B)
    elif vbytes == 40:
        return 24   # pos@0(12B), ?(12B), UV@24(8B), ?(8B)
    return None


def parse_msh(data):
    """解析 MSH，返回 (vertices_xyz, vertices_uv, indices, format_info)"""
    fmt = parse_msh_header(data)
    if fmt is None:
        fmt = detect_format_legacy(data)
    if fmt is None:
        raise ValueError("Cannot detect MSH format")

    vc = fmt['vcount']
    ic = fmt['fcount']
    vb = fmt['vbytes']
    vo = fmt['vert_off']
    io = fmt['idx_off']

    uv_off = get_uv_offset(vb, fmt['flag'])

    print(f"  Format: v{fmt['version']} flag=0x{fmt['flag']:X} "
          f"{vc}verts×{vb}B {ic}indices header=0x{vo:X}")

    vertices = []
    uvs = []
    for i in range(vc):
        off = vo + i * vb
        # 修复前向轴：MSH 前向 -Z → +Z（与 Noesis v1.2 一致）
        x, y, z = struct.unpack_from("<fff", data, off)
        vertices.append((x, y, -z))
        if uv_off is not None:
            u, v = struct.unpack_from("<ff", data, off + uv_off)
            uvs.append((u, v))

    indices = list(struct.unpack_from(f"<{ic}H", data, io))

    return vertices, uvs, indices, fmt


def write_obj(vertices, uvs, indices, output_path, name="model"):
    """写出 Wavefront OBJ 文件 (含 UV)"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Star Conflict MSH → OBJ v3\n")
        f.write(f"# Model: {name}\n")
        f.write(f"# Vertices: {len(vertices)}  Triangles: {len(indices)//3}\n\n")

        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        f.write("\n")

        if uvs:
            for uv in uvs:
                f.write(f"vt {uv[0]:.6f} {1.0 - uv[1]:.6f}\n")
            f.write("\n")
            # 带 UV 的面
            for i in range(0, len(indices) - 2, 3):
                a, b, c = indices[i]+1, indices[i+1]+1, indices[i+2]+1
                f.write(f"f {a}/{a} {b}/{b} {c}/{c}\n")
        else:
            # 无 UV 的面
            for i in range(0, len(indices) - 2, 3):
                a, b, c = indices[i]+1, indices[i+1]+1, indices[i+2]+1
                f.write(f"f {a} {b} {c}\n")

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    has_uv = "+UV" if uvs else "noUV"
    print(f"  OBJ: {output_path} ({has_uv})")
    print(f"  Bounds: X[{min(xs):.3f},{max(xs):.3f}] "
          f"Y[{min(ys):.3f},{max(ys):.3f}] "
          f"Z[{min(zs):.3f},{max(zs):.3f}]")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Star Conflict MSH → OBJ v3')
    parser.add_argument('input', help='Input .mdl-mshXXX file')
    parser.add_argument('-o', '--output', help='Output .obj file')
    args = parser.parse_args()

    with open(args.input, 'rb') as f:
        data = f.read()

    try:
        vertices, uvs, indices, fmt = parse_msh(data)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    output = args.output or (args.input + '.obj')
    name = os.path.splitext(os.path.basename(args.input))[0]
    write_obj(vertices, uvs, indices, output, name)
