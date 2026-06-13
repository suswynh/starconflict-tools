from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict X",
        ".mdl-msh874;.mdl-msh875;.mdl-msh876;.mdl-msh877;.mdl-msh878;.mdl-msh879;"
        ".mdl-msh880;.mdl-msh881;.mdl-msh882;.mdl-msh883;.mdl-msh884;.mdl-msh885;"
        ".mdl-msh886;.mdl-msh887;.mdl-msh888;.mdl-msh889;.mdl-msh890;.mdl-msh891;"
        ".mdl-msh892;.mdl-msh893;.mdl-msh894;.mdl-msh895;.mdl-msh896;.mdl-msh897;"
        ".mdl-msh898;.mdl-msh899;.mdl-msh900;.mdl-msh901;.mdl-msh902;.mdl-msh903;"
        ".mdl-msh904;.mdl-msh905;.mdl-msh906;.mdl-msh907;.mdl-msh908;.mdl-msh909;"
        ".mdl-msh910;.mdl-msh911;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1