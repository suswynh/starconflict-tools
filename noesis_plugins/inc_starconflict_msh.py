# Star Conflict .mdl-mshXXX shared loader
# Used by fmt_StarConflict_msh_A~Z.py to avoid duplicating identical logic 26 times.
# KNOWN: VBytes=40 flag=0x10 (character models) UV offset needs fixing, does not affect ships/scenes.
#
# LSP / static analysis: 此文件依赖 Noesis 原生二进制模块 (noesis, rapi)，
# 仅在 Noesis 运行时可用。不要期望 IDE 的红波浪线能在此目录正常工作。
# 验证方法: 打开 Noesis → Alt+T,R 重载插件 → 拖入 .mdl-mshXXX 文件查看。
from inc_noesis import *

def load_msh(data, mdlList):
    ctx = rapi.rpgCreateContext()
    rapi.rpgSetOption(noesis.RPGOPT_TRIWINDBACKWARD, 1)
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
        VBuf = bs.readBytes(VCount * VBytes)
        print(hex(bs.tell()), ":here2")
        if VBytes == 20:
            rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
            rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 12)
        elif VBytes == 24:
            rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
            rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 16)
        elif VBytes == 28:
            if flag == 0xe or flag == 5:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 16)
            elif flag == 0x11:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 20)
            else:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 16)
        elif VBytes == 32:
            rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
            rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 20)
        elif VBytes == 40:
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
