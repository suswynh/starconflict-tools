from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict E",
        ".mdl-msh152;.mdl-msh153;.mdl-msh154;.mdl-msh155;.mdl-msh156;.mdl-msh157;"
        ".mdl-msh158;.mdl-msh159;.mdl-msh160;.mdl-msh161;.mdl-msh162;.mdl-msh163;"
        ".mdl-msh164;.mdl-msh165;.mdl-msh166;.mdl-msh167;.mdl-msh168;.mdl-msh169;"
        ".mdl-msh170;.mdl-msh171;.mdl-msh172;.mdl-msh173;.mdl-msh174;.mdl-msh175;"
        ".mdl-msh176;.mdl-msh177;.mdl-msh178;.mdl-msh179;.mdl-msh180;.mdl-msh181;"
        ".mdl-msh182;.mdl-msh183;.mdl-msh184;.mdl-msh185;.mdl-msh186;.mdl-msh187;"
        ".mdl-msh188;.mdl-msh189;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1