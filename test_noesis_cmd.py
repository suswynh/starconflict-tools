import subprocess, os, sys
from pathlib import Path

# ── 路径配置（支持环境变量覆盖） ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOESIS_DIR = Path(os.environ.get("NOESIS_DIR", PROJECT_ROOT / "NOESIS"))
FBX_OUTPUT = Path(os.environ.get("FBX_OUTPUT", PROJECT_ROOT / "fbx_output"))

noesis = str(NOESIS_DIR / "Noesis64chs.exe")
odir = str(FBX_OUTPUT)
os.makedirs(odir, exist_ok=True)

# 测试输入文件（默认示例，可通过命令行参数覆盖）
_default_input = str(PROJECT_ROOT / "quickbms_unpacksource" / "models" / "weapons" / "missiles" / "guided_missile.mdl-msh000")
input_f = sys.argv[1] if len(sys.argv) > 1 else _default_input

tests = [
    (['?cmode', input_f, odir + r'\t1.fbx'], 'chs ?cmode fbx'),
    (['?cmode', input_f, odir + r'\t2.obj'], 'chs ?cmode obj'),
    (['?cmode', input_f, odir + r'\t3.fbx', '-fbxnewexport'], 'chs ?cmode fbx+flag'),
]

for args, desc in tests:
    output_f = args[2]
    print(f"\n=== {desc} ===")
    print(f"CMD: {[noesis] + args}")
    r = subprocess.run([noesis] + args, capture_output=True, text=True, timeout=30,
                       cwd=str(NOESIS_DIR))
    print(f"rc={r.returncode} out={r.stdout[:200]!r} err={r.stderr[:200]!r}")
    print(f"output exists: {os.path.exists(output_f)}")
    if os.path.exists(output_f):
        print(f"size: {os.path.getsize(output_f)} bytes")
