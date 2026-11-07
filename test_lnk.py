p = r"C:\Users\Public\Desktop\SOLIDWORKS 2021.lnk"
data = open(p, "rb").read()
for enc in ("utf-16-le", "ascii", "latin-1"):
    t = data.decode(enc, "ignore")
    for kw in ("SLDWORKS.exe", "SOLIDWORKS (2)", "SOLIDWORKS", "D:\\SOLIDWORKS", "/r", "/m"):
        if kw.lower() in t.lower():
            idx = t.lower().find(kw.lower())
            print("[%s] %r context: %r" % (enc, kw, t[max(0, idx - 40):idx + 60]))
