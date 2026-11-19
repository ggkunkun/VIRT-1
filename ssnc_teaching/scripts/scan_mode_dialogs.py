# -*- coding: utf-8 -*-
"""Scan all SSCNC controller exes for dialog templates exposing mode selection
as plain BUTTON controls (AUTO/EDIT/MDI/JOG...), i.e. BM_CLICK-able.
Reports exe -> dialog ids -> mode button ids."""
import pefile, struct, json, os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r'E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC'
OUT = r'D:\Virtu模型\ssnc_teaching\evidence\mode_button_panels.json'

MODE_WORDS = ['AUTO', 'EDIT', 'MDI', 'JOG', 'DNC', 'REF']

def dialogs(pe, img):
    """yield (dlg_id, bytes) for resource type 5."""
    if not hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
        return
    for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if t.id != 5:
            continue
        for e in t.directory.entries:
            if not e.directory:
                continue
            for lang in e.directory.entries:
                try:
                    rva = lang.data.struct.OffsetToData
                    size = lang.data.struct.Size
                    yield e.id, img[rva:rva + size]
                except Exception:
                    pass

def utf16_hits(d):
    return {w: (w.encode('utf-16-le') in d) for w in MODE_WORDS}

def main():
    results = {}
    exes = []
    for dirpath, dirs, files in os.walk(ROOT):
        for f in files:
            if f.lower().endswith('.exe') and f.lower() not in ('uninst.exe',):
                exes.append(os.path.join(dirpath, f))
    print('exes:', len(exes))
    for path in sorted(exes):
        try:
            pe = pefile.PE(path, fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
            img = pe.get_memory_mapped_image()
        except Exception as e:
            continue
        rel = os.path.relpath(path, ROOT)
        for did, d in dialogs(pe, img):
            hits = utf16_hits(d)
            n = sum(hits.values())
            if n >= 3:
                results.setdefault(rel, []).append({'dlg': did, 'hits': hits, 'size': len(d)})
        pe.close()
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    for rel, ds in results.items():
        print(rel, '->', [(x['dlg'], [k for k, v in x['hits'].items() if v]) for x in ds][:10])

if __name__ == '__main__':
    main()
