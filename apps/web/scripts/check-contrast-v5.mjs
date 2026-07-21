#!/usr/bin/env node
/**
 * Command Workspace v5 — WCAG AA contrast gate (PR 1, foundation).
 *
 * Companion to check-contrast.mjs (which gates globals.css). This gate
 * parses the `.wsx5` custom-property block in
 * components/workspace/v5/motion.css — the shipped source of truth — and
 * re-verifies the audited pairs from the accepted evidence package
 * (design-handoffs/incoming/2026-07-20-command-workspace-v5-cinematic/
 * EVIDENCE.md §6). Exits non-zero on any failure so it can run in CI.
 *
 * Thresholds: 4.5:1 body/small text, 3.0:1 large text (≥24px or 18.66px
 * bold) and UI component boundaries.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cssPath = join(__dirname, "..", "components", "workspace", "v5", "motion.css");
const css = readFileSync(cssPath, "utf8");

const AA_NORMAL = 4.5;
const AA_LARGE = 3.0;

const block = css.match(/\.wsx5\s*\{([\s\S]*?)\n\}/);
if (!block) {
    console.error("check-contrast-v5: could not find the .wsx5 token block");
    process.exit(1);
}
const vars = {};
for (const m of block[1].matchAll(/--wsx5-([\w-]+):\s*([^;]+);/g)) {
    vars[m[1]] = m[2].trim();
}

function parseColor(value) {
    const hex = value.match(/^#([0-9a-f]{6})$/i);
    if (hex) {
        const n = parseInt(hex[1], 16);
        return { rgb: [(n >> 16) & 255, (n >> 8) & 255, n & 255], a: 1 };
    }
    const rgba = value.match(/^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)$/);
    if (rgba) {
        return { rgb: [Number(rgba[1]), Number(rgba[2]), Number(rgba[3])], a: Number(rgba[4]) };
    }
    throw new Error(`Unsupported color value: ${value}`);
}
function token(name) {
    if (!(name in vars)) throw new Error(`Missing --wsx5-${name} in motion.css`);
    return parseColor(vars[name]);
}
/** Composite an (possibly translucent) fg over an opaque bg. */
function composite(fg, bg) {
    return fg.rgb.map((c, i) => c * fg.a + bg.rgb[i] * (1 - fg.a));
}
function relLuminance([r, g, b]) {
    const lin = (c) => {
        const s = c / 255;
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function ratio(fgName, bgName) {
    const bg = token(bgName);
    if (bg.a !== 1) throw new Error(`Background --wsx5-${bgName} must be opaque`);
    const fg = composite(token(fgName), bg);
    const l1 = relLuminance(fg);
    const l2 = relLuminance(bg.rgb);
    const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
    return (hi + 0.05) / (lo + 0.05);
}

/** [fg, bg, min, label] — the audited pairs for the applied artifact palette. */
const pairs = [
    ["ink", "paper", AA_NORMAL, "primary ink on paper"],
    ["ink70", "paper", AA_NORMAL, "body secondary on paper"],
    ["ink55", "paper", AA_NORMAL, "micro/meta text on paper"],
    ["ink55", "panel", AA_NORMAL, "micro/meta text on panel"],
    ["ink55", "raise", AA_NORMAL, "micro/meta text on raised surface"],
    ["lightInk", "deepPanel", AA_NORMAL, "primary light ink on deep panel"],
    ["lightInk70", "deepPanel", AA_NORMAL, "secondary light ink on deep panel"],
    ["lightInk58", "deepPanel2", AA_NORMAL, "smallest light text on lightest deep bg"],
    ["lightInk50", "deepPanel", AA_NORMAL, "micro caps on deep panel"],
    ["terraText", "paper", AA_NORMAL, "sun accent text on paper"],
    ["coralText", "paper", AA_NORMAL, "applications accent text on paper"],
    ["amberText", "paper", AA_NORMAL, "documents accent text on paper"],
    ["goldText", "paper", AA_NORMAL, "search accent text on paper"],
    ["mossText", "paper", AA_NORMAL, "learning accent text on paper"],
    ["logText", "paper", AA_NORMAL, "activity accent text on paper"],
    ["electricText", "paper", AA_NORMAL, "interview accent text on paper"],
    ["goldTextL", "paper", AA_LARGE, "gold large numerals on paper"],
    ["coralTextL", "paper", AA_LARGE, "coral large numerals on paper"],
    ["terra", "paper", AA_LARGE, "sun decorative/large on paper"],
    ["electric", "paper", AA_LARGE, "info UI accent on paper"],
    ["onEmber", "emberBtnEnd", AA_NORMAL, "button label on sun-button gradient (worst stop)"],
];

let failures = 0;
for (const [fg, bg, min, label] of pairs) {
    const r = ratio(fg, bg);
    const ok = r >= min;
    if (!ok) failures += 1;
    console.log(`${ok ? "PASS" : "FAIL"}  ${r.toFixed(2).padStart(5)}  (min ${min})  ${label}`);
}
if (failures > 0) {
    console.error(`\ncheck-contrast-v5: ${failures} pair(s) below WCAG AA`);
    process.exit(1);
}
console.log("\ncheck-contrast-v5: all pairs pass WCAG AA");
