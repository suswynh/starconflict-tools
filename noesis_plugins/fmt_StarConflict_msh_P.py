from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict P",
        ".mdl-msh570;.mdl-msh571;.mdl-msh572;.mdl-msh573;.mdl-msh574;.mdl-msh575;"
        ".mdl-msh576;.mdl-msh577;.mdl-msh578;.mdl-msh579;.mdl-msh580;.mdl-msh581;"
        ".mdl-msh582;.mdl-msh583;.mdl-msh584;.mdl-msh585;.mdl-msh586;.mdl-msh587;"
        ".mdl-msh588;.mdl-msh589;.mdl-msh590;.mdl-msh591;.mdl-msh592;.mdl-msh593;"
        ".mdl-msh594;.mdl-msh595;.mdl-msh596;.mdl-msh597;.mdl-msh598;.mdl-msh599;"
        ".mdl-msh600;.mdl-msh601;.mdl-msh602;.mdl-msh603;.mdl-msh604;.mdl-msh605;"
        ".mdl-msh606;.mdl-msh607;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1