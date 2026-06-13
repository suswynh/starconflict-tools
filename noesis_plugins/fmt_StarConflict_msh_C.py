from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict C",
        ".mdl-msh076;.mdl-msh077;.mdl-msh078;.mdl-msh079;.mdl-msh080;.mdl-msh081;"
        ".mdl-msh082;.mdl-msh083;.mdl-msh084;.mdl-msh085;.mdl-msh086;.mdl-msh087;"
        ".mdl-msh088;.mdl-msh089;.mdl-msh090;.mdl-msh091;.mdl-msh092;.mdl-msh093;"
        ".mdl-msh094;.mdl-msh095;.mdl-msh096;.mdl-msh097;.mdl-msh098;.mdl-msh099;"
        ".mdl-msh100;.mdl-msh101;.mdl-msh102;.mdl-msh103;.mdl-msh104;.mdl-msh105;"
        ".mdl-msh106;.mdl-msh107;.mdl-msh108;.mdl-msh109;.mdl-msh110;.mdl-msh111;"
        ".mdl-msh112;.mdl-msh113;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1