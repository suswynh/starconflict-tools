from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict N",
        ".mdl-msh494;.mdl-msh495;.mdl-msh496;.mdl-msh497;.mdl-msh498;.mdl-msh499;"
        ".mdl-msh500;.mdl-msh501;.mdl-msh502;.mdl-msh503;.mdl-msh504;.mdl-msh505;"
        ".mdl-msh506;.mdl-msh507;.mdl-msh508;.mdl-msh509;.mdl-msh510;.mdl-msh511;"
        ".mdl-msh512;.mdl-msh513;.mdl-msh514;.mdl-msh515;.mdl-msh516;.mdl-msh517;"
        ".mdl-msh518;.mdl-msh519;.mdl-msh520;.mdl-msh521;.mdl-msh522;.mdl-msh523;"
        ".mdl-msh524;.mdl-msh525;.mdl-msh526;.mdl-msh527;.mdl-msh528;.mdl-msh529;"
        ".mdl-msh530;.mdl-msh531;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1