from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict W",
        ".mdl-msh836;.mdl-msh837;.mdl-msh838;.mdl-msh839;.mdl-msh840;.mdl-msh841;"
        ".mdl-msh842;.mdl-msh843;.mdl-msh844;.mdl-msh845;.mdl-msh846;.mdl-msh847;"
        ".mdl-msh848;.mdl-msh849;.mdl-msh850;.mdl-msh851;.mdl-msh852;.mdl-msh853;"
        ".mdl-msh854;.mdl-msh855;.mdl-msh856;.mdl-msh857;.mdl-msh858;.mdl-msh859;"
        ".mdl-msh860;.mdl-msh861;.mdl-msh862;.mdl-msh863;.mdl-msh864;.mdl-msh865;"
        ".mdl-msh866;.mdl-msh867;.mdl-msh868;.mdl-msh869;.mdl-msh870;.mdl-msh871;"
        ".mdl-msh872;.mdl-msh873;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1