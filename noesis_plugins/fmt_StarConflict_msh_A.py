# Star Conflict .mdl-msh000~037  (Noesis 最多加载 ~26 个此类插件)
# A~Z 覆盖 000~987, 988+ 用 msh_to_obj_v3.py 命令行
# KNOWN: VBytes=40 flag=0x10 (角色模型) UV偏移待修正, 不影响飞船/场景
from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict A",
        ".mdl-msh000;.mdl-msh001;.mdl-msh002;.mdl-msh003;.mdl-msh004;.mdl-msh005;"
        ".mdl-msh006;.mdl-msh007;.mdl-msh008;.mdl-msh009;.mdl-msh010;.mdl-msh011;"
        ".mdl-msh012;.mdl-msh013;.mdl-msh014;.mdl-msh015;.mdl-msh016;.mdl-msh017;"
        ".mdl-msh018;.mdl-msh019;.mdl-msh020;.mdl-msh021;.mdl-msh022;.mdl-msh023;"
        ".mdl-msh024;.mdl-msh025;.mdl-msh026;.mdl-msh027;.mdl-msh028;.mdl-msh029;"
        ".mdl-msh030;.mdl-msh031;.mdl-msh032;.mdl-msh033;.mdl-msh034;.mdl-msh035;"
        ".mdl-msh036;.mdl-msh037;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1