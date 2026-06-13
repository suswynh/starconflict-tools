from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict D",
        ".mdl-msh114;.mdl-msh115;.mdl-msh116;.mdl-msh117;.mdl-msh118;.mdl-msh119;"
        ".mdl-msh120;.mdl-msh121;.mdl-msh122;.mdl-msh123;.mdl-msh124;.mdl-msh125;"
        ".mdl-msh126;.mdl-msh127;.mdl-msh128;.mdl-msh129;.mdl-msh130;.mdl-msh131;"
        ".mdl-msh132;.mdl-msh133;.mdl-msh134;.mdl-msh135;.mdl-msh136;.mdl-msh137;"
        ".mdl-msh138;.mdl-msh139;.mdl-msh140;.mdl-msh141;.mdl-msh142;.mdl-msh143;"
        ".mdl-msh144;.mdl-msh145;.mdl-msh146;.mdl-msh147;.mdl-msh148;.mdl-msh149;"
        ".mdl-msh150;.mdl-msh151;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1