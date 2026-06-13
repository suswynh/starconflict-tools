from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict Z",
        ".mdl-msh950;.mdl-msh951;.mdl-msh952;.mdl-msh953;.mdl-msh954;.mdl-msh955;"
        ".mdl-msh956;.mdl-msh957;.mdl-msh958;.mdl-msh959;.mdl-msh960;.mdl-msh961;"
        ".mdl-msh962;.mdl-msh963;.mdl-msh964;.mdl-msh965;.mdl-msh966;.mdl-msh967;"
        ".mdl-msh968;.mdl-msh969;.mdl-msh970;.mdl-msh971;.mdl-msh972;.mdl-msh973;"
        ".mdl-msh974;.mdl-msh975;.mdl-msh976;.mdl-msh977;.mdl-msh978;.mdl-msh979;"
        ".mdl-msh980;.mdl-msh981;.mdl-msh982;.mdl-msh983;.mdl-msh984;.mdl-msh985;"
        ".mdl-msh986;.mdl-msh987;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1