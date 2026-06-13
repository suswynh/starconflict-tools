from inc_noesis import *
from inc_starconflict_msh import load_msh

def registerNoesisTypes():
    handle = noesis.register("Star Conflict K",
        ".mdl-msh380;.mdl-msh381;.mdl-msh382;.mdl-msh383;.mdl-msh384;.mdl-msh385;"
        ".mdl-msh386;.mdl-msh387;.mdl-msh388;.mdl-msh389;.mdl-msh390;.mdl-msh391;"
        ".mdl-msh392;.mdl-msh393;.mdl-msh394;.mdl-msh395;.mdl-msh396;.mdl-msh397;"
        ".mdl-msh398;.mdl-msh399;.mdl-msh400;.mdl-msh401;.mdl-msh402;.mdl-msh403;"
        ".mdl-msh404;.mdl-msh405;.mdl-msh406;.mdl-msh407;.mdl-msh408;.mdl-msh409;"
        ".mdl-msh410;.mdl-msh411;.mdl-msh412;.mdl-msh413;.mdl-msh414;.mdl-msh415;"
        ".mdl-msh416;.mdl-msh417;")
    noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
    noesis.setHandlerLoadModel(handle, load_msh)
    return 1