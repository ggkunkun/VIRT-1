# -*- coding: utf-8 -*-
"""Scan SSCNC Controlor DLLs for dialog templates whose BUTTONS carry mode labels."""
import pefile, struct, json, os, sys, io, glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BINDIR = r'E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\common\Bin'
OUT = r'D:\Virtu模型\ssnc_teaching\evidence\controlor_panel_scan.json'
ORD = {0x80: 'Button', 0x81: 'Edit', 0x82: 'Static', 0x83: 'ListBox',
       0x84: 'ScrollBar', 0x85: 'ComboBox'}
MODE = {'AUTO', 'EDIT', 'MDI', 'JOG', 'DNC', 'REF', 'TEACH', 'INC', 'HANDLE'}


def get_dlls():
    return sorted(glob.glob(os.path.join(BINDIR, '*ontrol*.dll')) +
                  glob.glob(os.path.join(BINDIR, 'Std*.dll')))


def rd_str(d, o):
    if struct.unpack('<H', d[o:o + 2])[0] == 0xFFFF:
        return ('ord', struct.unpack('<H', d[o + 2:o + 4])[0]), o + 4
    p = o
    while True:
        p = d.index(b'\x00\x00', p)
        if (p - o) % 2 == 0:
            break
        p += 1
    return ('str', d[o:p].decode('utf-16-le', 'ignore')), p + 2


def parse_dialog(d):
    """Return list of (id,class,text,rect) or None."""
    if len(d) < 40:
        return None
    start = None
    for m in range(26, min(400, len(d) - 8)):
        if d[m:m + 2] == b'\xff\xff' and struct.unpack('<H', d[m + 2:m + 4])[0] in ORD:
            cid = struct.unpack('<I', d[m - 4:m])[0]
            if cid < 0x80000000:
                start = m - 24
                break
    if start is None:
        return None
    o = start
    items = []
    while o < len(d) - 30 and len(items) < 400:
        try:
            x, y, cx, cy, cid = struct.unpack('<hhhhI', d[o + 12:o + 24])
            wc, o2 = rd_str(d, o + 24)
            tt, o3 = rd_str(d, o2)
            extra = struct.unpack('<H', d[o3:o3 + 2])[0]
            o = o3 + 2 + extra * 2
            while o % 4:
                o += 1
            cls = ORD.get(wc[1], '?') if wc[0] == 'ord' else 'str'
            txt = tt[1] if tt[0] == 'str' else ''
            items.append((cid, cls, txt, [x, y, cx, cy]))
        except Exception:
            break
    return items


def main():
    results = {}
    for path in get_dlls():
        name = os.path.basename(path)
        try:
            pe = pefile.PE(path, fast_load=True)
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
            img = pe.get_memory_mapped_image()
        except Exception as e:
            print(name, 'ERR', e)
            continue
        if not hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
            pe.close()
            continue
        dlgs = []
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
                        d = img[rva:rva + size]
                    except Exception:
                        continue
                    items = parse_dialog(d)
                    if not items:
                        continue
                    btns = [i for i in items if i[1] == 'Button']
                    modebtns = [i for i in btns
                                if i[2].strip() in MODE or
                                any(w in i[2] for w in ('AUTO', 'EDIT', 'MDI', 'JOG'))]
                    if len(btns) >= 15 or modebtns:
                        dlgs.append({
                            'dlg': e.id, 'n_items': len(items),
                            'n_buttons': len(btns),
                            'mode_buttons': [
                                {'id': i[0], 'text': i[2], 'rect': i[3]}
                                for i in modebtns],
                            'button_texts': [i[2] for i in btns][:60],
                        })
        if dlgs:
            results[name] = dlgs
            print(name, '->', [(x['dlg'], x['n_buttons'],
                                [m['text'] for m in x['mode_buttons']][:8])
                               for x in dlgs])
        pe.close()
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
