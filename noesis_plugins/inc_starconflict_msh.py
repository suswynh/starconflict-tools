# Star Conflict .mdl-mshXXX shared loader
# Used by fmt_StarConflict_msh_A~Z.py to avoid duplicating identical logic 26 times.
# v1.2.1 (2026-07-11): Fixed VBytes=40 flag=0x13/0x10 and VBytes=32 flag=0x0F UV1 offsets.
#
# v1.2 (2026-06): Fix front axis — MSH models face -Z, negate Z to face +Z (Maya/FBX compatible).
#   Z negation also flips winding direction, so TRIWINDBACKWARD is not needed.
#
# LSP / static analysis: 此文件依赖 Noesis 原生二进制模块 (noesis, rapi)，
# 仅在 Noesis 运行时可用。不要期望 IDE 的红波浪线能在此目录正常工作。
# 验证方法: 打开 Noesis → Alt+T,R 重载插件 → 拖入 .mdl-mshXXX 文件查看。
from inc_noesis import *

def load_msh(data, mdlList):
    ctx = rapi.rpgCreateContext()

    # 修复左右镜像（见下方 VBuf 修改处）
    rapi.setPreviewOption("setAngOfs","0 290 130")

    bs = NoeBitStream(data)
    version = bs.readUInt()
    print(version, ":version")
    if version <= 200:
        flag = bs.readUInt()
        print(hex(flag), ":flag")
        VBytes = bs.readUInt()
        print(VBytes, ":vbytes")
        VCount = bs.readUInt()
        print(hex(VCount), ":vertex count")
        FCount = bs.readUInt()
        print(hex(FCount), ":face count")
        bs.seek(0x44, NOESEEK_ABS)
        print(hex(bs.tell()), ":here1")

        # 修复前向轴：MSH 模型前向为 -Z，取反后前向为 +Z（适配 Maya/FBX）。
        # Z 取反同步翻转卷绕方向，因此无需 TRIWINDBACKWARD。
        import struct
        VBuf = bytearray(bs.readBytes(VCount * VBytes))
        for vi in range(VCount):
            off = vi * VBytes
            z = struct.unpack_from('<f', VBuf, off + 8)[0]
            struct.pack_into('<f', VBuf, off + 8, -z)
        VBuf = bytes(VBuf)
        print(hex(bs.tell()), ":here2")
        if VBytes == 20:
            rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
            rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 12)
        elif VBytes == 24:
            rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
            rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 16)
        elif VBytes == 28:
            if flag == 0xe:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 16)
            elif flag == 5 or flag == 0x11:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 20)  # flag=5 UV at 20 (verified: pvp_omega skybox)
            else:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 16)
        elif VBytes == 32:
            if flag == 0x0F:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 16)
            else:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 20)
        elif VBytes == 40:
            if flag == 0x13:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 20)
            elif flag == 0x10:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 16)
            else:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 24)
        else:
            # fallback: at least bind position
            rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
        IBuf = bs.readBytes(FCount * 2)
        print(hex(bs.tell()), ":here3")
        rapi.rpgCommitTriangles(IBuf, noesis.RPGEODATA_USHORT, FCount, noesis.RPGEO_TRIANGLE, 1)
        mdlList.append(rapi.rpgConstructModel())
        rapi.rpgClearBufferBinds()
        return 1
