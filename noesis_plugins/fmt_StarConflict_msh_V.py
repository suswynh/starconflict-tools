from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict V",
        ".mdl-msh798;.mdl-msh799;.mdl-msh800;.mdl-msh801;.mdl-msh802;.mdl-msh803;"
        ".mdl-msh804;.mdl-msh805;.mdl-msh806;.mdl-msh807;.mdl-msh808;.mdl-msh809;"
        ".mdl-msh810;.mdl-msh811;.mdl-msh812;.mdl-msh813;.mdl-msh814;.mdl-msh815;"
        ".mdl-msh816;.mdl-msh817;.mdl-msh818;.mdl-msh819;.mdl-msh820;.mdl-msh821;"
        ".mdl-msh822;.mdl-msh823;.mdl-msh824;.mdl-msh825;.mdl-msh826;.mdl-msh827;"
        ".mdl-msh828;.mdl-msh829;.mdl-msh830;.mdl-msh831;.mdl-msh832;.mdl-msh833;"
        ".mdl-msh834;.mdl-msh835;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1