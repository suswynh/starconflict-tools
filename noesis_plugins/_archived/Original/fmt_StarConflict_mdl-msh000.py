from inc_noesis import *

def registerNoesisTypes():
    handle = noesis.register("Star Conflict", ".mdl-msh000;.mdl-msh001;.mdl-msh002;.mdl-msh003;.mdl-msh004;.mdl-msh005;.mdl-msh006;.mdl-msh007;.mdl-msh008;.mdl-msh009")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, noepyLoadModel)
    #noesis.logPopup()
    return 1

def noepyLoadModel(data, mdlList):
    ctx = rapi.rpgCreateContext()
    rapi.rpgSetOption(noesis.RPGOPT_TRIWINDBACKWARD, 1)  #flip normals
    rapi.setPreviewOption("setAngOfs","0 290 130")       #sets the default preview angle        
    bs = NoeBitStream(data)
    version = bs.readUInt()
    print(version, ":version")
    if version == 0 or version == 1 or version == 2 or version == 3:
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
        if VBytes == 24:
            rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
            rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 16)
        elif VBytes == 28:
            if flag == 0xe:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 16)
            elif flag == 0x11:
                rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
                rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 20)
        elif VBytes == 32:
            rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
            rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 20)
        elif VBytes == 36:
            rapi.rpgBindPositionBufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 0)
            rapi.rpgBindUV1BufferOfs(VBuf, noesis.RPGEODATA_FLOAT, VBytes, 20)
        IBuf = bs.readBytes(FCount * 2)  
        print(hex(bs.tell()), ":here3")
        rapi.rpgCommitTriangles(IBuf, noesis.RPGEODATA_USHORT, FCount, noesis.RPGEO_TRIANGLE, 1)
        mdlList.append(rapi.rpgConstructModel())
        rapi.rpgClearBufferBinds()
        return 1
   