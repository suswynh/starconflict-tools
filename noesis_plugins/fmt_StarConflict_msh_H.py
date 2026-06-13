from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict H",
        ".mdl-msh266;.mdl-msh267;.mdl-msh268;.mdl-msh269;.mdl-msh270;.mdl-msh271;"
        ".mdl-msh272;.mdl-msh273;.mdl-msh274;.mdl-msh275;.mdl-msh276;.mdl-msh277;"
        ".mdl-msh278;.mdl-msh279;.mdl-msh280;.mdl-msh281;.mdl-msh282;.mdl-msh283;"
        ".mdl-msh284;.mdl-msh285;.mdl-msh286;.mdl-msh287;.mdl-msh288;.mdl-msh289;"
        ".mdl-msh290;.mdl-msh291;.mdl-msh292;.mdl-msh293;.mdl-msh294;.mdl-msh295;"
        ".mdl-msh296;.mdl-msh297;.mdl-msh298;.mdl-msh299;.mdl-msh300;.mdl-msh301;"
        ".mdl-msh302;.mdl-msh303;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1