/* ============================================================================
 * h3lint_diff.mjs — 用 Node 原版 h3lint.js 跑差分测试语料，输出 JS 侧结果。
 * ----------------------------------------------------------------------------
 * 用法：
 *   node tools/h3lint_diff.mjs <cases.json> <out.json>
 *
 * 为什么要复制：h3lint.js 第 16 行会 require("./sim3d/combat-logic.js")（相对它自己所在
 * 目录解析）。E:\wushulong 下严格只读，本脚本把这两个文件**只读复制**到
 * tools/.h3lint_js_tmp/ 再 require，绝不写回源目录。
 * ========================================================================== */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const SRC_DIR = 'E:\\wushulong\\H3武斗模拟器-v9.12';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const TMP = path.join(HERE, '.h3lint_js_tmp');

const [casesPath, outPath] = process.argv.slice(2);
if (!casesPath || !outPath) {
  console.error('usage: node h3lint_diff.mjs <cases.json> <out.json>');
  process.exit(2);
}

// ── 1. 只读复制 JS 原版到临时目录（不碰 E:\wushulong）────────────────────────
fs.mkdirSync(path.join(TMP, 'sim3d'), { recursive: true });
for (const rel of ['h3lint.js', path.join('sim3d', 'combat-logic.js')]) {
  const src = path.join(SRC_DIR, rel);
  const dst = path.join(TMP, rel);
  fs.copyFileSync(src, dst);           // 只读源文件，只写临时目录
}

const require = createRequire(import.meta.url);
const H3LINT = require(path.join(TMP, 'h3lint.js'));
const FLpath = path.join(TMP, 'sim3d', 'combat-logic.js');
const FIGHT_LOGIC = require(FLpath);

const cases = JSON.parse(fs.readFileSync(casesPath, 'utf8')).cases;
const results = cases.map((c) => {
  const res = H3LINT.check(c.text, c.opts || {});
  const dims = H3LINT.diagnose(res);
  return {
    id: c.id,
    version: res.version,
    mode: res.mode,
    score: res.score,
    grade: res.grade,
    stats: res.stats,
    items: res.items,
    diagnose: { verdict: dims.verdict, worst: dims.worst, groups: dims.groups.map((g) => ({ key: g.key, level: g.level, count: g.count })) },
    report: H3LINT.report(res),
    diagnoseReport: H3LINT.diagnoseReport(res),
  };
});

fs.writeFileSync(outPath, JSON.stringify({
  source: SRC_DIR,
  h3lintVersion: H3LINT.VERSION,
  fightLogicVersion: FIGHT_LOGIC.VERSION,
  node: process.version,
  exportedKeys: Object.keys(H3LINT).sort(),
  cases: results,
}, null, 2), 'utf8');

console.log(`[js] h3lint ${H3LINT.VERSION} / fight-logic ${FIGHT_LOGIC.VERSION} / node ${process.version}`);
console.log(`[js] ${results.length} cases -> ${outPath}`);
