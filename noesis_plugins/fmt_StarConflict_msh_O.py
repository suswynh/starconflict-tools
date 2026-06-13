from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict O",
        ".mdl-msh532;.mdl-msh533;.mdl-msh534;.mdl-msh535;.mdl-msh536;.mdl-msh537;"
        ".mdl-msh538;.mdl-msh539;.mdl-msh540;.mdl-msh541;.mdl-msh542;.mdl-msh543;"
        ".mdl-msh544;.mdl-msh545;.mdl-msh546;.mdl-msh547;.mdl-msh548;.mdl-msh549;"
        ".mdl-msh550;.mdl-msh551;.mdl-msh552;.mdl-msh553;.mdl-msh554;.mdl-msh555;"
        ".mdl-msh556;.mdl-msh557;.mdl-msh558;.mdl-msh559;.mdl-msh560;.mdl-msh561;"
        ".mdl-msh562;.mdl-msh563;.mdl-msh564;.mdl-msh565;.mdl-msh566;.mdl-msh567;"
        ".mdl-msh568;.mdl-msh569;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1