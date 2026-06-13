from inc_noesis import *
import math

def registerNoesisTypes():
    handle = noesis.register("Star Conflict", ".tfh")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    #noesis.logPopup()
    return 1

def noepyCheckType(data):
    return 1
    
def noepyLoadRGBA(data, texList):
    bs = NoeBitStream(data)
    bs.readBits(4)
    imgWidth = bs.readBits(12)
    imgHeight = bs.readUShort() // 4
    mips = bs.readBits(4)
    bs.readBits(4)
    imgFmt = bs.readBits(4)
    bs.readBits(4)    
    print(hex(imgFmt), ":imgFmt")
    bs.read("B" * 2)
    tfdFile = rapi.getExtensionlessName(rapi.getInputName()) + ".tfd"
    print(imgWidth, "x", imgHeight)
    print(tfdFile, ":tfd file")
    bs2 = NoeBitStream(rapi.loadIntoByteArray(tfdFile))
    bs.seek((mips * 12) - 12, NOESEEK_REL)
    mainMipOffset = bs.readUInt()
    datasize = bs.readUInt()
    imgSize = bs.readUInt()
    bs2.seek(mainMipOffset, NOESEEK_ABS)        
    #DXT1 
    if imgFmt == 0xb or imgFmt == 0x7:
        texFmt = noesis.NOESISTEX_DXT1
    #DXT3
    elif imgFmt == 0xd or imgFmt == 0x9:
        texFmt = noesis.NOESISTEX_DXT3
    #DXT5
    elif imgFmt == 0xa:
        texFmt = noesis.NOESISTEX_DXT5
    #DXT5
    elif imgFmt == 0xe and imgWidth == 0:
        imgWidth = int(math.sqrt(datasize))
        imgHeight = imgWidth
        texFmt = noesis.NOESISTEX_DXT5
    #DXT5
    elif imgFmt == 0xe and imgWidth != 0:
        texFmt = noesis.NOESISTEX_DXT5
    print(hex(datasize), ":datasize")
    data = bs2.readBytes(datasize)      
    texList.append(NoeTexture(rapi.getInputName(), imgWidth, imgHeight, data, texFmt))
    return 1