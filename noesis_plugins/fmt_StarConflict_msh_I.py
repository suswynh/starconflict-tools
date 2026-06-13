from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict I",
        ".mdl-msh304;.mdl-msh305;.mdl-msh306;.mdl-msh307;.mdl-msh308;.mdl-msh309;"
        ".mdl-msh310;.mdl-msh311;.mdl-msh312;.mdl-msh313;.mdl-msh314;.mdl-msh315;"
        ".mdl-msh316;.mdl-msh317;.mdl-msh318;.mdl-msh319;.mdl-msh320;.mdl-msh321;"
        ".mdl-msh322;.mdl-msh323;.mdl-msh324;.mdl-msh325;.mdl-msh326;.mdl-msh327;"
        ".mdl-msh328;.mdl-msh329;.mdl-msh330;.mdl-msh331;.mdl-msh332;.mdl-msh333;"
        ".mdl-msh334;.mdl-msh335;.mdl-msh336;.mdl-msh337;.mdl-msh338;.mdl-msh339;"
        ".mdl-msh340;.mdl-msh341;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1