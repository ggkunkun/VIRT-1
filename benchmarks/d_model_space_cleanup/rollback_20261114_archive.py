import os, shutil, _winapi
PAIRS = [('D:\\Virtu模型\\checkpoints\\_deploy_vericut96\\merged_hf', 'E:\\moved_from_D\\checkpoints\\_deploy_vericut96\\merged_hf'), ('D:\\Virtu模型\\checkpoints\\impeller_fixed_merged', 'E:\\moved_from_D\\checkpoints\\impeller_fixed_merged')]
for src, dst in PAIRS:
    if os.path.isdir(src):
        st = os.stat(src, follow_symlinks=False)
        if getattr(st, 'st_file_attributes', 0) & 0x400:
            os.rmdir(src)
    if os.path.isdir(dst) and os.path.isdir(src) is False:
        shutil.copytree(dst, src)
        print('restored', src)
