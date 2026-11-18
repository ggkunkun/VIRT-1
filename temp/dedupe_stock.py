import re
import shutil

for p in [r"E:\vericut_impeller_run\proj.vcproject", r"E:\vericut_impeller_run\OP3.vcproject"]:
    shutil.copy2(p, p + ".bak_stockdup")
    t = open(p, encoding="utf-8").read()
    pat = re.compile(r"\s*<Cylinder Radius=\"25\" Height=\"30\"[\s\S]*?</Cylinder>")
    n = len(pat.findall(t))
    t2 = pat.sub("", t, count=1)
    open(p, "w", encoding="utf-8").write(t2)
    print(p.split("\\")[-1], "removed=", n, "remaining_Cylinder=", len(re.findall(r"<Cylinder ", t2)))
