# -*- coding: utf-8 -*-
"""补充补丁：给 cadcam_step_reverse 增加 detail 参数并同步默认值。"""
import os

P = r"D:\Virtu模型\bridges\tool_calling_specs.py"
b = open(P, "rb").read()
NL = b"\r\r\n"

pairs = [
    ("最多返回的实体明细数，默认 12".encode("utf-8"),
     "最多返回的实体明细数，默认 6".encode("utf-8")),
    (b'                    "max_bodies": {' + NL +
     b'                        "type": "integer",' + NL +
     b'                        "description": "' + "最多返回的实体明细数，默认 6".encode("utf-8") + b'"' + NL +
     b'                    }' + NL +
     b'                },' + NL +
     b'                "required": []',
     b'                    "max_bodies": {' + NL +
     b'                        "type": "integer",' + NL +
     b'                        "description": "' + "最多返回的实体明细数，默认 6".encode("utf-8") + b'"' + NL +
     b'                    },' + NL +
     b'                    "detail": {' + NL +
     b'                        "type": "boolean",' + NL +
     b'                        "description": "' + "true=返回逐孔坐标等完整明细（体积较大）；默认 false 精简".encode("utf-8") + b'"' + NL +
     b'                    }' + NL +
     b'                },' + NL +
     b'                "required": []'),
    (b'            max_bodies=int(args.get("max_bodies", 12)),' + NL +
     b'            name_contains=args.get("name_contains", ""),' + NL,
     b'            max_bodies=int(args.get("max_bodies", 6)),' + NL +
     b'            name_contains=args.get("name_contains", ""),' + NL +
     b'            detail=bool(args.get("detail", False)),' + NL),
]
for old, new in pairs:
    if old not in b:
        print("MISS", old[:70])
        continue
    b = b.replace(old, new, 1)
    print("OK", old[:50])
open(P, "wb").write(b)
print("WRITTEN", len(b))
