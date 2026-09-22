# -*- coding: utf-8 -*-
"""run_h3lint_diff.py — 差分验证：Node 原版 h3lint.js vs Python 移植版。

用法::

    python tools/run_h3lint_diff.py

流程：
    1. 读 tools/h3lint_cases.json（语料，由 tools/build_h3lint_cases.py 生成）；
    2. 调 node tools/h3lint_diff.mjs 跑 JS 原版 → tools/h3lint_js_results.json；
    3. 用 wushu_bridge.lint.h3lint 跑同一批语料；
    4. 逐条比对 score / grade / items 的 id 集合，写 tools/h3lint_diff_report.md。

验收红线（见报告末尾「验收」段）：
    * |Δscore| ≤ 2
    * grade 一致率 ≥ 90%
    * error 级 items 的 id 集合完全一致
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
CASES = TOOLS / "h3lint_cases.json"
JS_OUT = TOOLS / "h3lint_js_results.json"
REPORT = TOOLS / "h3lint_diff_report.md"
sys.path.insert(0, str(ROOT))

from wushu_bridge.lint import h3lint  # noqa: E402


def ids_of(items, level=None):
    return sorted({i["id"] for i in items if level is None or i["level"] == level})


def run_js():
    mjs = TOOLS / "h3lint_diff.mjs"
    p = subprocess.run([  # noqa: S603
        "node", str(mjs), str(CASES), str(JS_OUT)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit("node 差分脚本失败：\nSTDOUT:\n%s\nSTDERR:\n%s" % (p.stdout, p.stderr))
    print(p.stdout.strip())
    return json.loads(JS_OUT.read_text(encoding="utf-8"))


def main():
    jsw = run_js()
    js = {c["id"]: c for c in jsw["cases"]}
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]

    rows = []
    for c in cases:
        cid = c["id"]
        py = h3lint.check(c["text"], c["opts"] or {})
        j = js[cid]
        py_ids, js_ids = ids_of(py["items"]), ids_of(j["items"])
        py_err, js_err = ids_of(py["items"], "error"), ids_of(j["items"], "error")
        # 文本报告比对：report()/diagnoseReport() 的正文包含 msg/hint/at，能验证到字段内容级
        py_rep, js_rep = h3lint.report(py), j["report"]
        py_drep, js_drep = h3lint.diagnose_report(py), j["diagnoseReport"]
        rows.append({
            "id": cid, "note": c["note"],
            "js_score": j["score"], "py_score": py["score"],
            "d_score": abs(j["score"] - py["score"]),
            "js_grade": j["grade"], "py_grade": py["grade"],
            "grade_ok": j["grade"] == py["grade"],
            "err_ok": py_err == js_err,
            "js_err": js_err, "py_err": py_err,
            "only_js": sorted(set(js_ids) - set(py_ids)),
            "only_py": sorted(set(py_ids) - set(js_ids)),
            "js_ids": js_ids, "py_ids": py_ids,
            "stats_ok": j["stats"] == py["stats"],
            "js_stats": j["stats"], "py_stats": py["stats"],
            "report_ok": py_rep == js_rep,
            "diag_ok": py_drep == js_drep,
            "py_report": py_rep, "js_report": js_rep,
        })

    n = len(rows)
    score_ok = sum(1 for r in rows if r["d_score"] <= 2)
    grade_ok = sum(1 for r in rows if r["grade_ok"])
    err_ok = sum(1 for r in rows if r["err_ok"])
    ids_ok = sum(1 for r in rows if not r["only_js"] and not r["only_py"])
    stats_ok = sum(1 for r in rows if r["stats_ok"])
    report_ok = sum(1 for r in rows if r["report_ok"])
    diag_ok = sum(1 for r in rows if r["diag_ok"])
    max_d = max(r["d_score"] for r in rows)

    lines = []
    A = lines.append
    A("# h3lint 差分验证报告：JS 原版 vs Python 移植版\n")
    A("- JS 源：`%s\\h3lint.js`（%s，Node %s）" % (jsw["source"], jsw["h3lintVersion"], jsw["node"]))
    A("- JS 依赖：`%s\\sim3d\\combat-logic.js`（%s，已随移植内置到 `wushu_bridge/lint/_combat_logic.py`）"
      % (jsw["source"], jsw["fightLogicVersion"]))
    A("- Python：`wushu_bridge/lint/h3lint.py`（VERSION=%s）" % h3lint.VERSION)
    A("- 语料：`tools/h3lint_cases.json`，%d 条（`python tools/build_h3lint_cases.py` 生成）" % n)
    A("- JS 侧导出键：`%s`\n" % "`, `".join(jsw["exportedKeys"]))

    A("## 总览\n")
    A("| 指标 | 结果 | 验收线 | 判定 |")
    A("|---|---|---|---|")
    A("| 用例数 | %d | ≥ 30 | %s |" % (n, "PASS" if n >= 30 else "FAIL"))
    A("| score 最大绝对差 | %d | ≤ 2 | %s |" % (max_d, "PASS" if max_d <= 2 else "FAIL"))
    A("| score 差值 ≤2 的用例 | %d/%d | 全部 | %s |" % (score_ok, n, "PASS" if score_ok == n else "FAIL"))
    A("| grade 一致率 | %.1f%% (%d/%d) | ≥ 90%% | %s |"
      % (grade_ok / n * 100, grade_ok, n, "PASS" if grade_ok / n >= 0.9 else "FAIL"))
    A("| error 级 id 集合完全一致 | %d/%d | 全部 | %s |" % (err_ok, n, "PASS" if err_ok == n else "FAIL"))
    A("| 全部 id 集合完全一致 | %d/%d | 参考项 | %s |" % (ids_ok, n, "PASS" if ids_ok == n else "见下表"))
    A("| stats 完全一致 | %d/%d | 参考项 | %s |" % (stats_ok, n, "PASS" if stats_ok == n else "见下表"))
    A("| report() 文本完全一致（含 msg/hint/at） | %d/%d | 参考项 | %s |"
      % (report_ok, n, "PASS" if report_ok == n else "见下表"))
    A("| diagnose_report() 文本完全一致 | %d/%d | 参考项 | %s |"
      % (diag_ok, n, "PASS" if diag_ok == n else "见下表"))
    A("")

    bad = [r for r in rows if r["d_score"] > 2 or not r["grade_ok"] or not r["err_ok"]
           or r["only_js"] or r["only_py"] or not r["stats_ok"] or not r["report_ok"] or not r["diag_ok"]]
    A("## 逐条结果\n")
    A("| 用例 | 说明 | JS | Py | Δ | JS grade | Py grade | error 集合 | id 差异 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        diff = ""
        if r["only_js"]:
            diff += "仅JS:" + ",".join(r["only_js"]) + " "
        if r["only_py"]:
            diff += "仅Py:" + ",".join(r["only_py"]) + " "
        A("| `%s` | %s | %d | %d | %d | %s | %s | %s | %s |"
          % (r["id"], r["note"], r["js_score"], r["py_score"], r["d_score"],
             r["js_grade"], r["py_grade"], "一致" if r["err_ok"] else "**不一致**",
             diff.strip() or "—"))
    A("")

    if bad:
        A("## 差异明细\n")
        for r in bad:
            A("### `%s` — %s" % (r["id"], r["note"]))
            A("- JS: score=%d grade=%s items=%s" % (r["js_score"], r["js_grade"], ", ".join(r["js_ids"]) or "（无）"))
            A("- Py: score=%d grade=%s items=%s" % (r["py_score"], r["py_grade"], ", ".join(r["py_ids"]) or "（无）"))
            if r["only_js"]:
                A("- 仅 JS 命中：%s" % ", ".join("`%s`" % x for x in r["only_js"]))
            if r["only_py"]:
                A("- 仅 Py 命中：%s" % ", ".join("`%s`" % x for x in r["only_py"]))
            if not r["stats_ok"]:
                A("- JS stats: `%s`" % json.dumps(r["js_stats"], ensure_ascii=False))
                A("- Py stats: `%s`" % json.dumps(r["py_stats"], ensure_ascii=False))
            if not r["report_ok"]:
                A("- report() 文本差异：\n\n```\n[JS]\n%s\n\n[Py]\n%s\n```" % (r["js_report"], r["py_report"]))
            if not r["diag_ok"]:
                A("- diagnose_report() 文本不一致")
            A("")
    else:
        A("## 差异明细\n\n无：全部 %d 条用例的 score 差、grade、items id 集合与 stats 完全一致。\n" % n)

    A("## 验收\n")
    ok = (n >= 30 and max_d <= 2 and score_ok == n and grade_ok / n >= 0.9 and err_ok == n)
    A("- score 最大绝对差 **%d**（≤2）" % max_d)
    A("- grade 一致率 **%.1f%%**（≥90%%）" % (grade_ok / n * 100))
    A("- error 级 id 集合一致 **%d/%d**" % (err_ok, n))
    A("- 附：全部 id 集合一致 %d/%d，stats 一致 %d/%d，report() 文本一致 %d/%d，diagnose_report() 一致 %d/%d"
      % (ids_ok, n, stats_ok, n, report_ok, n, diag_ok, n))
    A("- **结论：%s**" % ("全部达标" if ok else "未达标，见「差异明细」"))

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[py] %d cases, max Δscore=%d, grade %.1f%%, error-set %d/%d, all-id %d/%d, stats %d/%d, report %d/%d, diag %d/%d"
          % (n, max_d, grade_ok / n * 100, err_ok, n, ids_ok, n, stats_ok, n, report_ok, n, diag_ok, n))
    print("[py] report -> %s" % REPORT)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
