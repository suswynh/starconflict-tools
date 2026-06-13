from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict Q",
        ".mdl-msh608;.mdl-msh609;.mdl-msh610;.mdl-msh611;.mdl-msh612;.mdl-msh613;"
        ".mdl-msh614;.mdl-msh615;.mdl-msh616;.mdl-msh617;.mdl-msh618;.mdl-msh619;"
        ".mdl-msh620;.mdl-msh621;.mdl-msh622;.mdl-msh623;.mdl-msh624;.mdl-msh625;"
        ".mdl-msh626;.mdl-msh627;.mdl-msh628;.mdl-msh629;.mdl-msh630;.mdl-msh631;"
        ".mdl-msh632;.mdl-msh633;.mdl-msh634;.mdl-msh635;.mdl-msh636;.mdl-msh637;"
        ".mdl-msh638;.mdl-msh639;.mdl-msh640;.mdl-msh641;.mdl-msh642;.mdl-msh643;"
        ".mdl-msh644;.mdl-msh645;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1