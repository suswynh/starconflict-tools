from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict R",
        ".mdl-msh646;.mdl-msh647;.mdl-msh648;.mdl-msh649;.mdl-msh650;.mdl-msh651;"
        ".mdl-msh652;.mdl-msh653;.mdl-msh654;.mdl-msh655;.mdl-msh656;.mdl-msh657;"
        ".mdl-msh658;.mdl-msh659;.mdl-msh660;.mdl-msh661;.mdl-msh662;.mdl-msh663;"
        ".mdl-msh664;.mdl-msh665;.mdl-msh666;.mdl-msh667;.mdl-msh668;.mdl-msh669;"
        ".mdl-msh670;.mdl-msh671;.mdl-msh672;.mdl-msh673;.mdl-msh674;.mdl-msh675;"
        ".mdl-msh676;.mdl-msh677;.mdl-msh678;.mdl-msh679;.mdl-msh680;.mdl-msh681;"
        ".mdl-msh682;.mdl-msh683;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1