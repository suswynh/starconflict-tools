from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict F",
        ".mdl-msh190;.mdl-msh191;.mdl-msh192;.mdl-msh193;.mdl-msh194;.mdl-msh195;"
        ".mdl-msh196;.mdl-msh197;.mdl-msh198;.mdl-msh199;.mdl-msh200;.mdl-msh201;"
        ".mdl-msh202;.mdl-msh203;.mdl-msh204;.mdl-msh205;.mdl-msh206;.mdl-msh207;"
        ".mdl-msh208;.mdl-msh209;.mdl-msh210;.mdl-msh211;.mdl-msh212;.mdl-msh213;"
        ".mdl-msh214;.mdl-msh215;.mdl-msh216;.mdl-msh217;.mdl-msh218;.mdl-msh219;"
        ".mdl-msh220;.mdl-msh221;.mdl-msh222;.mdl-msh223;.mdl-msh224;.mdl-msh225;"
        ".mdl-msh226;.mdl-msh227;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1