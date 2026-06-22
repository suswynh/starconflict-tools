import subprocess, os, sys

noesis = r'D:\starconflict upcak\NOESIS\Noesis64chs.exe'
input_f = r'D:\starconflict upcak\quickbms_unpacksource\models\weapons\missiles\guided_missile.mdl-msh000'
odir = r'D:\starconflict upcak\fbx_output'
os.makedirs(odir, exist_ok=True)

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
                       cwd=r'D:\starconflict upcak\NOESIS')
    print(f"rc={r.returncode} out={r.stdout[:200]!r} err={r.stderr[:200]!r}")
    print(f"output exists: {os.path.exists(output_f)}")
    if os.path.exists(output_f):
        print(f"size: {os.path.getsize(output_f)} bytes")
