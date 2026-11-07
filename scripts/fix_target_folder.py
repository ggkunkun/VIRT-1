# -*- coding: utf-8 -*-
import os
import shutil

for name in os.listdir('e:\\'):
    p = os.path.join('e:\\', name)
    try:
        if os.path.isdir(p) and '00_UNIFIED_MASTER_TRAIN' in os.listdir(p):
            print("Found dataset folder:", repr(name))
            # Move all contents of this folder into the real 新建文件夹 (3)
            real_target = os.path.join('e:\\', '新建文件夹 (3)')
            for item in os.listdir(p):
                src_item = os.path.join(p, item)
                dst_item = os.path.join(real_target, item)
                print(f"Moving {item} -> {dst_item} ...")
                if os.path.exists(dst_item):
                    if os.path.isdir(dst_item):
                        shutil.rmtree(dst_item)
                    else:
                        os.remove(dst_item)
                shutil.move(src_item, dst_item)
            print("All items moved successfully into real 新建文件夹 (3)!")
    except Exception as e:
        pass
