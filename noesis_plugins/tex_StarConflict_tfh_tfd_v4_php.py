# Star Conflict TFH/TFD - v4: pure PHP TargemImage.php migration
# ================================================================
# 100% PHP logic: no bitstream, no fallback, no font detection.
# Use for comparison against v3 (hybrid) to evaluate parsing differences.
# ================================================================
from inc_noesis import *
import struct

# Noesis format constants -- exactly matching PHP's DDS output
FMT_NOESIS = {
    'RGBA': noesis.NOESISTEX_RGBA32,
    'DXT1': noesis.NOESISTEX_DXT1,
    'DXT3': noesis.NOESISTEX_DXT3,
    'DXT5': noesis.NOESISTEX_DXT5,
}


def registerNoesisTypes():
    handle = noesis.register("Star Conflict v4 (PHP)", ".tfh")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    return 1


def noepyCheckType(data):
    return 1


def noepyLoadRGBA(data, texList):
    """Pure PHP migration -- line-by-line equivalent of TargemImage::convert()."""
    tfhPath = rapi.getInputName()

    # -- PHP line 26-28: imageSize header --
    if len(data) < 8:
        print("ERROR: TFH too short (%d bytes)" % len(data))
        return 0

    imageSize = data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)
    _php_w_hint = (imageSize & 0xFFFFFF) // 16
    _php_h_hint = ((imageSize >> 24) & 0xFF) << 6

    # -- PHP line 30-32: mips byte --
    mips_byte = data[4]
    mipsCount  = mips_byte & 0x0F
    mipsInFile = (mips_byte & 0xF0) >> 4

    # -- PHP line 34-36: format, type, unknown2 --
    fmt_raw = data[5]
    fmt_code = fmt_raw & 0x0F
    type_byte  = data[6]
    unknown2   = data[7]

    if mipsCount == 0:
        print("ERROR: mipsCount=0")
        return 0

    # -- PHP line 41-48: mip table --
    expected_size = 8 + mipsCount * 12
    if len(data) < expected_size:
        print("ERROR: TFH too short for %d mips (need %d, have %d)" %
              (mipsCount, expected_size, len(data)))
        return 0

    pos = 8
    imageTable = []
    for i in range(mipsCount):
        off  = data[pos] | (data[pos+1] << 8) | (data[pos+2] << 16) | (data[pos+3] << 24)
        sz   = data[pos+4] | (data[pos+5] << 8) | (data[pos+6] << 16) | (data[pos+7] << 24)
        w    = data[pos+8] | (data[pos+9] << 8) | (data[pos+10] << 16) | (data[pos+11] << 24)
        imageTable.append({'offset': off, 'size': sz, 'width': w})
        pos += 12

    # -- PHP line 51: end() = last mip (assumed largest) --
    image = imageTable[-1]

    # -- PHP line 53-91: format switch --
    if fmt_code in (0x0, 0x5, 0x6):
        imgFormat = 'RGBA'
        imgWidth  = image['width'] // 4
        if image['width'] > 0:
            imgHeight = image['size'] // image['width']
        else:
            imgHeight = 0
    elif fmt_code in (0x7, 0xB):
        imgFormat = 'DXT1'
        imgWidth  = image['width'] // 2
        if image['width'] > 0:
            imgHeight = (4 * image['size']) // image['width']
        else:
            imgHeight = 0
    elif fmt_code in (0x9, 0xD):
        imgFormat = 'DXT3'
        imgWidth  = image['width'] // 4
        if image['width'] > 0:
            imgHeight = (4 * image['size']) // image['width']
        else:
            imgHeight = 0
    elif fmt_code in (0xA, 0xE):
        imgFormat = 'DXT5'
        imgWidth  = image['width'] // 4
        if image['width'] > 0:
            imgHeight = (4 * image['size']) // image['width']
        else:
            imgHeight = 0
    else:
        print("ERROR: unknown format 0x%02X (full=0x%02X) in %s" %
              (fmt_code, fmt_raw, tfhPath))
        return 0

    # -- Validation --
    if imgWidth <= 0 or imgHeight <= 0:
        print("ERROR: bad dimensions %dx%d (mip w=%d sz=%d) in %s" %
              (imgWidth, imgHeight, image['width'], image['size'], tfhPath))
        return 0

    # -- PHP line 94-104: data source --
    if mipsCount == mipsInFile:
        # Data embedded in TFH
        data_start = image['offset']
        data_end   = data_start + image['size']
        if data_end > len(data):
            print("ERROR: embedded data out of bounds (off=%d sz=%d len=%d)" %
                  (data_start, image['size'], len(data)))
            return 0
        pixel_data = data[data_start:data_end]
    else:
        # Data in separate .tfd file
        tfd_path = rapi.getExtensionlessName(tfhPath) + ".tfd"
        try:
            tfd_raw = rapi.loadIntoByteArray(tfd_path)
        except:
            try:
                with open(tfd_path, 'rb') as f:
                    tfd_raw = f.read()
            except:
                print("ERROR: cannot open TFD: %s" % tfd_path)
                return 0
        data_start = image['offset']
        data_end   = data_start + image['size']
        if data_end > len(tfd_raw):
            print("ERROR: TFD data out of bounds (off=%d sz=%d tfd_len=%d)" %
                  (data_start, image['size'], len(tfd_raw)))
            return 0
        pixel_data = tfd_raw[data_start:data_end]

    # -- PHP line 109: write DDS header + data --
    # For Noesis we pass raw compressed data directly -- Noesis handles decoding
    texFmt = FMT_NOESIS[imgFormat]
    print("v4[PHP] %dx%d fmt=%s(0x%02X) mips=%d/%d off=%d sz=%d src=%s" %
          (imgWidth, imgHeight, imgFormat, fmt_code, mipsCount, mipsInFile,
           image['offset'], image['size'], 'tfh' if mipsCount == mipsInFile else 'tfd'))

    # Data byte order: [B][G][R][A] -> Noesis RGBA32 expects [R][G][B][A]
    if imgFormat == 'RGBA':
        arr = bytearray(pixel_data)
        for i in range(0, len(arr), 4):
            arr[i], arr[i+2] = arr[i+2], arr[i]  # swap B <-> R
        pixel_data = bytes(arr)

    texList.append(NoeTexture(tfhPath, imgWidth, imgHeight, pixel_data, texFmt))
    return 1
