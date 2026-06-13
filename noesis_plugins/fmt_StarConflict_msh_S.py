from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict S",
        ".mdl-msh684;.mdl-msh685;.mdl-msh686;.mdl-msh687;.mdl-msh688;.mdl-msh689;"
        ".mdl-msh690;.mdl-msh691;.mdl-msh692;.mdl-msh693;.mdl-msh694;.mdl-msh695;"
        ".mdl-msh696;.mdl-msh697;.mdl-msh698;.mdl-msh699;.mdl-msh700;.mdl-msh701;"
        ".mdl-msh702;.mdl-msh703;.mdl-msh704;.mdl-msh705;.mdl-msh706;.mdl-msh707;"
        ".mdl-msh708;.mdl-msh709;.mdl-msh710;.mdl-msh711;.mdl-msh712;.mdl-msh713;"
        ".mdl-msh714;.mdl-msh715;.mdl-msh716;.mdl-msh717;.mdl-msh718;.mdl-msh719;"
        ".mdl-msh720;.mdl-msh721;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1