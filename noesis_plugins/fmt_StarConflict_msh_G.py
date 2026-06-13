from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict G",
        ".mdl-msh228;.mdl-msh229;.mdl-msh230;.mdl-msh231;.mdl-msh232;.mdl-msh233;"
        ".mdl-msh234;.mdl-msh235;.mdl-msh236;.mdl-msh237;.mdl-msh238;.mdl-msh239;"
        ".mdl-msh240;.mdl-msh241;.mdl-msh242;.mdl-msh243;.mdl-msh244;.mdl-msh245;"
        ".mdl-msh246;.mdl-msh247;.mdl-msh248;.mdl-msh249;.mdl-msh250;.mdl-msh251;"
        ".mdl-msh252;.mdl-msh253;.mdl-msh254;.mdl-msh255;.mdl-msh256;.mdl-msh257;"
        ".mdl-msh258;.mdl-msh259;.mdl-msh260;.mdl-msh261;.mdl-msh262;.mdl-msh263;"
        ".mdl-msh264;.mdl-msh265;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1