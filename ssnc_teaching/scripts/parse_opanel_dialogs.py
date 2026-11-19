# -*- coding: utf-8 -*-
"""Parse SSCNC op-panel dialog templates (DLGTEMPLATEEX) from sscnc.exe resources.
Extracts every child control: id, class, rect, title, style -> JSON evidence."""
import pefile, struct, json

EXE = r'E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\FANUC\FANUC0iM\sscnc.exe'
OUT = r'D:\Virtu模型\ssnc_teaching\evidence\opanel_dialog_templates.json'

ORD_NAMES = {0x0080: 'Button', 0x0081: 'Edit', 0x0082: 'Static', 0x0083: 'ListBox',
             0x0084: 'ScrollBar', 0x0085: 'ComboBox'}


def get_dlg(img, pe, dlgid):
    for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if t.id != 5:
            continue
        for e in t.directory.entries:
            if e.id != dlgid:
                continue
            for lang in e.directory.entries:
                rva = lang.data.struct.OffsetToData
                size = lang.data.struct.Size
                return img[rva:rva + size]
    return None


def rd_str(d, o):
    """DLG sz_or_ord: 0xFFFF+ord16, or NUL-terminated UTF-16."""
    if struct.unpack('<H', d[o:o + 2])[0] == 0xFFFF:
        return ('ord', struct.unpack('<H', d[o + 2:o + 4])[0]), o + 4
    p = o
    while True:
        p = d.index(b'\x00\x00', p)
        if (p - o) % 2 == 0:
            break
        p += 1
    return ('str', d[o:p].decode('utf-16-le', 'ignore')), p + 2


def parse_items(d, start, n):
    o = start
    items = []
    for i in range(n):
        helpID, exS, st = struct.unpack('<III', d[o:o + 12])
        x, y, cx, cy, cid = struct.unpack('<hhhhI', d[o + 12:o + 24])
        wc, o = rd_str(d, o + 24)   # windowClass at item+24
        tt, o = rd_str(d, o)        # title follows
        extra = struct.unpack('<H', d[o:o + 2])[0]
        o += 2 + extra * 2
        while o % 4:
            o += 1
        cls = ORD_NAMES.get(wc[1], 'ord:%04x' % wc[1]) if wc[0] == 'ord' else wc[1]
        txt = tt[1] if tt[0] == 'str' else 'ord:%d' % tt[1]
        items.append({'id': cid, 'class': cls, 'text': txt,
                      'rect_dialog_units': [x, y, cx, cy], 'style': hex(st)})
    return items, o


def find_item_start(d):
    """First DLGITEMTEMPLATEEX: scan for ffff+known-class-ordinal; id 4B before marker-4."""
    for o in range(30, 220):
        if d[o:o + 2] == b'\xff\xff' and struct.unpack('<H', d[o + 2:o + 4])[0] in ORD_NAMES:
            cid = struct.unpack('<I', d[o - 8:o - 4])[0]
            if 9000 <= cid <= 9999:
                return o - 28  # class field at item+24 => marker at +24, item start = marker-24... see below
    return None


def main():
    pe = pefile.PE(EXE)
    img = pe.get_memory_mapped_image()
    out = {}
    for did in (797, 803, 804):
        d = get_dlg(img, pe, did)
        if not d:
            continue
        cItems = struct.unpack('<H', d[14:16])[0]
        # locate first item manually: class sz_or_ord 'ffff'+ord sits at item+24;
        # id (4B) at item+20. marker pos m => item start = m-24.
        start = None
        for m in range(30, 220):
            if d[m:m + 2] == b'\xff\xff' and struct.unpack('<H', d[m + 2:m + 4])[0] in ORD_NAMES:
                cid = struct.unpack('<I', d[m - 4:m])[0]
                if 9000 <= cid <= 9999:
                    start = m - 24
                    break
        if start is None:
            print('dlg', did, 'no item start found')
            continue
        try:
            items, end = parse_items(d, start, cItems)
            print('dlg', did, 'items', len(items), 'end', end, 'size', len(d))
            out[str(did)] = items
        except Exception as e:
            print('dlg', did, 'parse fail:', repr(e))
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
