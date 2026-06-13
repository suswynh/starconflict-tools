from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict Y",
        ".mdl-msh912;.mdl-msh913;.mdl-msh914;.mdl-msh915;.mdl-msh916;.mdl-msh917;"
        ".mdl-msh918;.mdl-msh919;.mdl-msh920;.mdl-msh921;.mdl-msh922;.mdl-msh923;"
        ".mdl-msh924;.mdl-msh925;.mdl-msh926;.mdl-msh927;.mdl-msh928;.mdl-msh929;"
        ".mdl-msh930;.mdl-msh931;.mdl-msh932;.mdl-msh933;.mdl-msh934;.mdl-msh935;"
        ".mdl-msh936;.mdl-msh937;.mdl-msh938;.mdl-msh939;.mdl-msh940;.mdl-msh941;"
        ".mdl-msh942;.mdl-msh943;.mdl-msh944;.mdl-msh945;.mdl-msh946;.mdl-msh947;"
        ".mdl-msh948;.mdl-msh949;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1