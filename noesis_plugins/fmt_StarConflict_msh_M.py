from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict M",
        ".mdl-msh456;.mdl-msh457;.mdl-msh458;.mdl-msh459;.mdl-msh460;.mdl-msh461;"
        ".mdl-msh462;.mdl-msh463;.mdl-msh464;.mdl-msh465;.mdl-msh466;.mdl-msh467;"
        ".mdl-msh468;.mdl-msh469;.mdl-msh470;.mdl-msh471;.mdl-msh472;.mdl-msh473;"
        ".mdl-msh474;.mdl-msh475;.mdl-msh476;.mdl-msh477;.mdl-msh478;.mdl-msh479;"
        ".mdl-msh480;.mdl-msh481;.mdl-msh482;.mdl-msh483;.mdl-msh484;.mdl-msh485;"
        ".mdl-msh486;.mdl-msh487;.mdl-msh488;.mdl-msh489;.mdl-msh490;.mdl-msh491;"
        ".mdl-msh492;.mdl-msh493;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1