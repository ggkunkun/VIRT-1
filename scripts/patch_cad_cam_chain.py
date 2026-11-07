# -*- coding: utf-8 -*-
"""Patch cad_cam_agent_chain.py with ProcessMemoryReclaimer and --execute memory-safe option."""

import os

target_path = r"d:\Virtu模型\cad_cam_agent_chain.py"
with open(target_path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Add import
import_marker = "if ROOT not in sys.path:\n    sys.path.insert(0, ROOT)\n"
new_import = import_marker + "\nfrom virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer\n"
text = text.replace(import_marker, new_import, 1)

# 2. Add reclaimer in __init__
init_marker = "self.artifacts = []  # [{key, tool, role, file, rel, method, depends_on, handoff, launch}]\n        self._load_engine()\n"
new_init = init_marker + "        self.reclaimer = ProcessMemoryReclaimer(log_path=os.path.join(self.out_dir, 'memory_reclamation.json'))\n"
text = text.replace(init_marker, new_init, 1)

# 3. Add execute parameter in run()
run_marker = "def run(self):"
new_run = "def run(self, execute=False, memory_safe=True):"
text = text.replace(run_marker, new_run, 1)

# 4. Add execute hook in run() before return
exec_hook = """
        if execute:
            print("\\n>>> 激活真实工业软件阶段式执行（内存安全保活机制）...")
            import agent_chain_executor
            agent_chain_executor.run_chain(self.wish, out_root=self.out_root, memory_safe=memory_safe)
"""
ret_marker = "        return self.out_dir\n"
text = text.replace(ret_marker, exec_hook + ret_marker, 1)

# 5. Add --execute to main()
arg_marker = "ap.add_argument(\"--out\", default=None, help=\"工程包输出根目录（默认 runs/cad_cam_chain）\")\n"
new_arg = arg_marker + "    ap.add_argument(\"--execute\", action=\"store_true\", help=\"按流水线调用原生工业软件执行并每步释放内存\")\n"
text = text.replace(arg_marker, new_arg, 1)

chain_run_marker = "chain.run()\n"
new_chain_run = "chain.run(execute=args.execute)\n"
text = text.replace(chain_run_marker, new_chain_run, 1)

with open(target_path, "w", encoding="utf-8", newline="\r\n") as f:
    f.write(text)
print("SUCCESS: cad_cam_agent_chain.py patched successfully.")
