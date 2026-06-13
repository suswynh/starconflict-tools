from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict B",
        ".mdl-msh038;.mdl-msh039;.mdl-msh040;.mdl-msh041;.mdl-msh042;.mdl-msh043;"
        ".mdl-msh044;.mdl-msh045;.mdl-msh046;.mdl-msh047;.mdl-msh048;.mdl-msh049;"
        ".mdl-msh050;.mdl-msh051;.mdl-msh052;.mdl-msh053;.mdl-msh054;.mdl-msh055;"
        ".mdl-msh056;.mdl-msh057;.mdl-msh058;.mdl-msh059;.mdl-msh060;.mdl-msh061;"
        ".mdl-msh062;.mdl-msh063;.mdl-msh064;.mdl-msh065;.mdl-msh066;.mdl-msh067;"
        ".mdl-msh068;.mdl-msh069;.mdl-msh070;.mdl-msh071;.mdl-msh072;.mdl-msh073;"
        ".mdl-msh074;.mdl-msh075;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1