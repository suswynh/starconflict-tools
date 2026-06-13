from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict U",
        ".mdl-msh760;.mdl-msh761;.mdl-msh762;.mdl-msh763;.mdl-msh764;.mdl-msh765;"
        ".mdl-msh766;.mdl-msh767;.mdl-msh768;.mdl-msh769;.mdl-msh770;.mdl-msh771;"
        ".mdl-msh772;.mdl-msh773;.mdl-msh774;.mdl-msh775;.mdl-msh776;.mdl-msh777;"
        ".mdl-msh778;.mdl-msh779;.mdl-msh780;.mdl-msh781;.mdl-msh782;.mdl-msh783;"
        ".mdl-msh784;.mdl-msh785;.mdl-msh786;.mdl-msh787;.mdl-msh788;.mdl-msh789;"
        ".mdl-msh790;.mdl-msh791;.mdl-msh792;.mdl-msh793;.mdl-msh794;.mdl-msh795;"
        ".mdl-msh796;.mdl-msh797;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1