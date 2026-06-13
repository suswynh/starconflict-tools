from inc_noesis import *

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
    bs.readByte()
    width = bs.readUByte()
    print(width, ":width")
    height = bs.readUShort()
    print(height, ":height")
    imgHeight = height // width
    mips = bs.readBits(4)
    print(mips, ":mips")
    bs.readBits(4)
    imgFmt = bs.readByte() 
    print(hex(imgFmt), ":imgFmt")
    bs.read("B" * 2)
    tfdFile = rapi.getExtensionlessName(rapi.getInputName()) + ".tfd"
    if imgFmt == 0xe:
        imgWidth = width // 2
    elif "_glow" in tfdFile:
        imgWidth = width * 2
    else:
        imgWidth = width
    print(imgWidth, "x", imgHeight)
    print(tfdFile, ":tfd file")
    bs2 = NoeBitStream(rapi.loadIntoByteArray(tfdFile))
    #DXT5
    if imgFmt == 0xa or imgFmt == 0xe:
        datasize = imgWidth * imgHeight
        texFmt = noesis.NOESISTEX_DXT5
    #DXT1 
    elif imgFmt == 0xb or imgFmt == 0x7:
        datasize = imgWidth * imgHeight // 2
        texFmt = noesis.NOESISTEX_DXT1
    print(hex(datasize), ":datasize")
    bs2.seek(0, NOESEEK_ABS)        
    data = bs2.readBytes(datasize)      
    texList.append(NoeTexture(rapi.getInputName(), imgWidth, imgHeight, data, texFmt))
    return 1