from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict J",
        ".mdl-msh342;.mdl-msh343;.mdl-msh344;.mdl-msh345;.mdl-msh346;.mdl-msh347;"
        ".mdl-msh348;.mdl-msh349;.mdl-msh350;.mdl-msh351;.mdl-msh352;.mdl-msh353;"
        ".mdl-msh354;.mdl-msh355;.mdl-msh356;.mdl-msh357;.mdl-msh358;.mdl-msh359;"
        ".mdl-msh360;.mdl-msh361;.mdl-msh362;.mdl-msh363;.mdl-msh364;.mdl-msh365;"
        ".mdl-msh366;.mdl-msh367;.mdl-msh368;.mdl-msh369;.mdl-msh370;.mdl-msh371;"
        ".mdl-msh372;.mdl-msh373;.mdl-msh374;.mdl-msh375;.mdl-msh376;.mdl-msh377;"
        ".mdl-msh378;.mdl-msh379;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1