from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict L",
        ".mdl-msh418;.mdl-msh419;.mdl-msh420;.mdl-msh421;.mdl-msh422;.mdl-msh423;"
        ".mdl-msh424;.mdl-msh425;.mdl-msh426;.mdl-msh427;.mdl-msh428;.mdl-msh429;"
        ".mdl-msh430;.mdl-msh431;.mdl-msh432;.mdl-msh433;.mdl-msh434;.mdl-msh435;"
        ".mdl-msh436;.mdl-msh437;.mdl-msh438;.mdl-msh439;.mdl-msh440;.mdl-msh441;"
        ".mdl-msh442;.mdl-msh443;.mdl-msh444;.mdl-msh445;.mdl-msh446;.mdl-msh447;"
        ".mdl-msh448;.mdl-msh449;.mdl-msh450;.mdl-msh451;.mdl-msh452;.mdl-msh453;"
        ".mdl-msh454;.mdl-msh455;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1