# -*- coding: utf-8 -*-
path = r"bridges\tool_calling_specs.py"
raw = open(path, "r", encoding="utf-8").read()

# Normalize double newlines if any, or work with raw text
# Let's find "return {"status": "error", "message": f"Unknown tool name: {tool_name}"}"
needle = 'return {"status": "error", "message": f"Unknown tool name: {tool_name}"}'
assert needle in raw, "needle not found"

step_reverse_code = """
    elif tool_name == "cadcam_step_reverse":
        act = args.get("action", "analyze")
        step_p = args.get("step_path") or args.get("file_path") or args.get("path", "")
        out_sldprt = args.get("out_sldprt_path") or args.get("output_path")
        if act == "list":
            assets_dir = os.path.join(_ROOT, "assets")
            found = []
            filter_sub = args.get("name_contains", "").lower()
            for r, _, fnames in os.walk(assets_dir):
                for fn in fnames:
                    if fn.lower().endswith((".step", ".stp")) and (not filter_sub or filter_sub in fn.lower()):
                        full_p = os.path.join(r, fn)
                        found.append({"name": fn, "path": full_p, "size_bytes": os.path.getsize(full_p)})
            return {"status": "success", "action": "list", "step_files": found}

        return orch.step_reverse(
            step_path=step_p,
            action=act,
            out_sldprt_path=out_sldprt,
        )

    """

raw = raw.replace(needle, step_reverse_code + needle)

# Add aliases
alias_needle = '"cad.parse_wish_intent": ("cadcam_run_full_chain",'
assert alias_needle in raw, "alias_needle not found"

# Find the closing brace of cad.parse_wish_intent entry
idx = raw.find(alias_needle)
end_idx = raw.find("}),", idx) + 3

alias_addon = """
        "reverse_step_model": ("cadcam_step_reverse", {
            "action": args.get("action", "analyze"),
            "step_path": args.get("step_path", args.get("path", "")),
            "out_sldprt_path": args.get("out_sldprt_path", args.get("output_path", "")),
        }),
        "step_reverse": ("cadcam_step_reverse", {
            "action": args.get("action", "analyze"),
            "step_path": args.get("step_path", args.get("path", "")),
            "out_sldprt_path": args.get("out_sldprt_path", args.get("output_path", "")),
        }),
        "cadcam_reverse_engineering": ("cadcam_step_reverse", {
            "action": args.get("action", "analyze"),
            "step_path": args.get("step_path", args.get("path", "")),
            "out_sldprt_path": args.get("out_sldprt_path", args.get("output_path", "")),
        }),"""

raw = raw[:end_idx] + alias_addon + raw[end_idx:]

# Path allowed
p_needle = "if not path_allowed(val, _ROOT):"
assert p_needle in raw, "p_needle not found"
p_repl = """allowed = path_allowed(val, _ROOT)
            if not allowed and pk == "step_path":
                import tempfile
                desktop = os.path.expanduser(r"~\\Desktop")
                allowed = path_allowed(val, desktop) or path_allowed(val, tempfile.gettempdir())
            if not allowed:"""
raw = raw.replace(p_needle, p_repl, 1)

open(path, "w", encoding="utf-8").write(raw)
print("SUCCESSFULLY APPLIED ALL PATCHES TO tool_calling_specs.py!")
