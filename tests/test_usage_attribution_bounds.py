"""Attribution bounds on the `usage` field.

A response that ran no model has no token counts of its own. If such a response is
given a `usage` block, it necessarily carries the *previous* request's numbers - the
same class of unverified claim this repo has already been burned by twice (the fixed
"100% PASS" template, then serving an untrained base under the Virtu model id).

Kept in its own file because scripts/workbuddy_virtu_bridge.py and
tests/test_bridge_usage.py are under concurrent edit by other sessions.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE = (ROOT / "scripts" / "workbuddy_virtu_bridge.py").read_text(encoding="utf-8")

# A completion body starts at `return {` / `resp = {` with the chat.completion marker.
ANY_COMPLETION = re.compile(r'\{\s*"id": [^,]+,\s*"object": "chat\.completion",')
ATTACHED = re.compile(r'(?:return|resp =|end_payload =) _attach_usage\(\{'
                      r'\s*"id": [^,]+,\s*"object": "chat\.completion"')
BACKEND_MARKER = re.compile(r"backend\.generate\(|run_exclusive\(")


def _enclosing_function(source, pos):
    """(start, end, name) of the def block containing ``pos``."""
    starts = [0] + [m.end() for m in re.finditer("\n", source)]
    line = max(i for i, s in enumerate(starts) if s <= pos)
    for i in range(line, -1, -1):
        m = re.match(r"(\s*)(?:async\s+)?def\s+(\w+)\s*\(", source[starts[i]:])
        if not m:
            continue
        indent = len(m.group(1))
        end = len(source)
        for s in starts[i + 1:]:
            m2 = re.match(r"(\s*)(?:async\s+)?(?:def|class)\s+", source[s:])
            if m2 and len(m2.group(1)) <= indent:
                end = s
                break
        return starts[i], end, m.group(2)
    return None


def _ran_backend(source, pos):
    """Did a backend call run *before* this payload, in its function or its caller?

    A fixed 2600-char lookback was too narrow: the chat route calls
    ``backend.generate`` inside ``do_POST`` and only then hands the text to
    ``_handle_json_response``, while the no-tool branch sits hundreds of lines
    below its generate call.  Ordering matters too: constant/engine branches
    that return *above* their function's generate call never ran a model, so a
    function-wide match would wrongly credit them.
    """
    fn = _enclosing_function(source, pos)
    if fn is None:
        return any(m.start() < pos for m in BACKEND_MARKER.finditer(source))
    markers = list(BACKEND_MARKER.finditer(source[fn[0]:fn[1]]))
    if any(fn[0] + m.start() < pos for m in markers):
        return True
    name = fn[2]
    for call in re.finditer(rf"\b{re.escape(name)}\s*\(", source):
        if fn[0] <= call.start() < fn[1]:
            continue
        caller = _enclosing_function(source, call.start())
        if caller and any(caller[0] + m.start() < call.start()
                          for m in BACKEND_MARKER.finditer(source[caller[0]:caller[1]])):
            return True
    return False


def completion_blocks(source=SOURCE):
    """Yield (start_line, attaches_usage, ran_backend) for each completion body."""
    attached_offsets = {m.start() for m in ATTACHED.finditer(source)}
    for match in ANY_COMPLETION.finditer(source):
        body_start = source.rfind("{", 0, match.start() + 1)
        attaches = any(abs(a - body_start) < 2 for a in attached_offsets) or \
            source[max(0, body_start - 20):body_start].rstrip().endswith("_attach_usage(")
        line = source[:match.start()].count("\n") + 1
        yield line, attaches, _ran_backend(source, match.start())


def scan_offenders(source=SOURCE):
    return [line for line, attaches, ran in completion_blocks(source) if attaches and not ran]


# A completion body with usage attached in a route that never calls the backend.
# This is the defect class the test must keep catching after the scan was made
# function-scope aware; if this stops failing, the gate has gone vacuous.
PLANTED_OFFENDER = '''
def _planted_route(self):
    return _attach_usage({
        "id": "chatcmpl-planted",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [],
    })
'''


class TestUsageAttributionBounds:
    def test_some_completions_are_recognised(self):
        """Guard against the scan silently matching nothing and passing vacuously."""
        assert len(list(completion_blocks())) >= 5, \
            "扫描不到 chat.completion 载荷，本测试等于没测"

    def test_routes_without_a_model_call_do_not_publish_usage(self):
        offenders = scan_offenders()
        assert not offenders, (
            f"这些载荷没有调用后端却挂了 usage（会发布上一次请求的计数）：行 {offenders}")

    def test_every_backend_call_site_has_a_usage_hook_available(self):
        """The mirror check: if a route really generated text, dropping usage is a
        regression for the eval harness, which reads usage to detect truncation."""
        generated = [line for line, _, ran in completion_blocks() if ran]
        attached = [line for line, attaches, _ in completion_blocks() if attaches]
        assert generated, "找不到任何真调用后端的 completion 载荷，服务链路已变形"
        assert len(attached) >= len(generated) - 1, (
            f"后端生成 {len(generated)} 处但只有 {len(attached)} 处挂 usage")

    def test_a_planted_offender_is_still_detected(self):
        """Falsification probe for the scope-aware scan."""
        offenders = scan_offenders(PLANTED_OFFENDER)
        assert offenders, "植入的无后端调用载荷没被识别，闸门已空转"
