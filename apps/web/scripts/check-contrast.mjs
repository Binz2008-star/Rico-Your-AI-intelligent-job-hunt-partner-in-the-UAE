#!/usr/bin/env node
/**
 * Rico Site v2 — WCAG AA contrast gate.
 *
 * Verifies the semantic token palette (defined as RGB-channel CSS variables in
 * app/globals.css) meets WCAG 2.1 AA for both the dark (`:root`) and light
 * (`.light`) themes. This is the gate that prevents light mode from shipping with
 * the broken contrast that caused the earlier revert.
 *
 * Checked pairs (foreground on background):
 *   - text-primary / text-secondary / text-tertiary on the canvas (--bg)
 *   - text-primary / text-secondary on the elevated surface (--surface-elevated)
 *   - magenta + cyan accents on the canvas (used for links/labels/UI accents)
 *
 * Thresholds: 4.5:1 for body text (AA normal), 3:1 for large text / UI accents.
 *
 * Parses globals.css directly (no runtime deps) so the source of truth is the
 * actual shipped stylesheet, not a duplicated table. Exits non-zero on any
 * failure so it can run in CI.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cssPath = join(__dirname, "..", "app", "globals.css");
const css = readFileSync(cssPath, "utf8");

const AA_NORMAL = 4.5; // body text
const AA_LARGE = 3.0; // large text / UI components

/** Extract a `--token: r g b;` channel triple from a given selector block. */
function parseTheme(selector) {
    // Grab the first { ... } block following the selector.
    const re = new RegExp(`${selector.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&")}\\s*\\{([^}]*)\\}`);
    const block = css.match(re);
    if (!block) throw new Error(`Could not find selector block for "${selector}"`);
    const body = block[1];
    const tokens = {};
    const tokenRe = /--([\w-]+):\s*(\d+)\s+(\d+)\s+(\d+)\s*;/g;
    let m;
    while ((m = tokenRe.exec(body)) !== null) {
        tokens[m[1]] = [Number(m[2]), Number(m[3]), Number(m[4])];
    }
    return tokens;
}

function relLuminance([r, g, b]) {
    const lin = (c) => {
        const s = c / 255;
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrastRatio(fg, bg) {
    const l1 = relLuminance(fg);
    const l2 = relLuminance(bg);
    const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
    return (hi + 0.05) / (lo + 0.05);
}

const dark = parseTheme(":root");
const light = parseTheme(".light");

/** [foregroundToken, backgroundToken, minRatio, label] */
const pairs = [
    ["text-primary", "bg", AA_NORMAL, "primary text on canvas"],
    ["text-secondary", "bg", AA_NORMAL, "secondary text on canvas"],
    ["text-tertiary", "bg", AA_LARGE, "tertiary text on canvas (large/UI)"],
    ["text-primary", "surface-elevated", AA_NORMAL, "primary text on elevated surface"],
    ["text-secondary", "surface-elevated", AA_NORMAL, "secondary text on elevated surface"],
    ["magenta", "bg", AA_LARGE, "magenta accent on canvas (UI/large)"],
    ["cyan", "bg", AA_LARGE, "cyan accent on canvas (UI/large)"],
];

let failures = 0;
for (const [themeName, theme] of [["dark", dark], ["light", light]]) {
    console.log(`\n${themeName.toUpperCase()} theme`);
    for (const [fgTok, bgTok, min, label] of pairs) {
        const fg = theme[fgTok];
        const bg = theme[bgTok];
        if (!fg || !bg) {
            console.log(`  ✗ ${label}: missing token (${fgTok} or ${bgTok})`);
            failures++;
            continue;
        }
        const ratio = contrastRatio(fg, bg);
        const ok = ratio >= min;
        if (!ok) failures++;
        console.log(
            `  ${ok ? "✓" : "✗"} ${label}: ${ratio.toFixed(2)}:1 (min ${min}:1)`
        );
    }
}

if (failures > 0) {
    console.error(`\n✗ Contrast gate FAILED: ${failures} pair(s) below WCAG AA.`);
    process.exit(1);
}
console.log("\n✓ Contrast gate passed: all token pairs meet WCAG AA in both themes.");
