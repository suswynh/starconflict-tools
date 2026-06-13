from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict T",
        ".mdl-msh722;.mdl-msh723;.mdl-msh724;.mdl-msh725;.mdl-msh726;.mdl-msh727;"
        ".mdl-msh728;.mdl-msh729;.mdl-msh730;.mdl-msh731;.mdl-msh732;.mdl-msh733;"
        ".mdl-msh734;.mdl-msh735;.mdl-msh736;.mdl-msh737;.mdl-msh738;.mdl-msh739;"
        ".mdl-msh740;.mdl-msh741;.mdl-msh742;.mdl-msh743;.mdl-msh744;.mdl-msh745;"
        ".mdl-msh746;.mdl-msh747;.mdl-msh748;.mdl-msh749;.mdl-msh750;.mdl-msh751;"
        ".mdl-msh752;.mdl-msh753;.mdl-msh754;.mdl-msh755;.mdl-msh756;.mdl-msh757;"
        ".mdl-msh758;.mdl-msh759;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1