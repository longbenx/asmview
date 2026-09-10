#!/usr/bin/env python3
# Left pane: asm or raw bytes. Right pane: listing with branch arrows.
# Default arch: x86-32.

import argparse
import html
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>asmview</title>
<style>
  html,body{height:100%;margin:0;background:#1e1e1e;color:#d4d4d4;
    font:13px/1.45 ui-monospace,Consolas,Menlo,monospace;
    display:flex;flex-direction:column}
  header{padding:8px 12px;background:#252526;border-bottom:1px solid #333;
    display:flex;gap:14px;align-items:center;flex-wrap:wrap;flex:0 0 auto}
  select,input,button{background:#3c3c3c;color:#ddd;border:1px solid #555;padding:3px 8px;cursor:pointer}
  input[type=text]{width:7em}
  input#bad{width:10em}
  input#framereg{width:4.5em}
  button.on{background:#0e639c;border-color:#1177bb}
  main{display:grid;grid-template-columns:280px 6px 1fr;flex:1;min-height:0}
  main.with-frame{grid-template-columns:280px 6px 1fr 6px 320px}
  main.dragging{user-select:none;cursor:col-resize}
  main.dragging-h{user-select:none;cursor:row-resize}
  textarea{width:100%;height:100%;box-sizing:border-box;border:0;resize:none;
    background:#1e1e1e;color:#d4d4d4;padding:12px;outline:none;font:inherit}
  #out{background:#181818;color:#9cdcfe;white-space:pre;margin:0;padding:12px;
    overflow:auto;height:100%;box-sizing:border-box;min-width:0}
  #src{min-width:0}
  .split{background:#333;flex:0 0 auto}
  .split.v{cursor:col-resize;width:6px}
  .split.h{cursor:row-resize;height:6px}
  .split:hover,.split.on{background:#0e639c}
  #splitR{display:none}
  main.with-frame #splitR{display:block}
  #toolwrap{display:none;flex-direction:column;min-height:0;min-width:0;background:#1b1b1b}
  main.with-frame #toolwrap{display:flex}
  #tooltabs{display:flex;gap:0;flex:0 0 auto;background:#252526;border-bottom:1px solid #333}
  #tooltabs button{flex:1;border:0;border-bottom:2px solid transparent;border-radius:0;padding:7px 8px}
  #tooltabs button.on{background:#1b1b1b;border-bottom-color:#0e639c;color:#fff}
  #framewrap,#strwrap{display:none;flex-direction:column;flex:1;min-height:0;min-width:0}
  #framewrap.show,#strwrap.show{display:flex}
  #framebar,#strbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:6px 10px;
    border-bottom:1px solid #333;background:#252526;flex:0 0 auto}
  #framein,#strin{flex:0 0 38%;min-height:5em;border:0;padding:10px;
    background:#1e1e1e;color:#d4d4d4;font:inherit;outline:none}
  #frameout,#strout{flex:1;margin:0;padding:10px 12px;overflow:auto;color:#ce9178;min-height:4em}
  input#stroff{width:4.5em}
  #strbar label.chk{display:flex;gap:4px;align-items:center;color:#bbb}
  #strout .blk{margin:0 0 12px}
  #strout .blk h4{margin:0 0 4px;color:#9cdcfe;font-size:12px;font-weight:600}
  #strout pre.blkbody{margin:0;white-space:pre-wrap;color:#ce9178}
  #strout .hint{color:#808080}
  #frameout table,#strout table{border-collapse:collapse;width:max-content;max-width:100%;font:inherit;margin:0 0 14px}
  #frameout th,#frameout td,#strout th,#strout td{border:1px solid #3a3a3a;padding:4px 10px;text-align:left;vertical-align:middle;white-space:nowrap}
  #frameout td.fr-note{white-space:normal}
  #frameout th,#strout th{color:#9cdcfe;background:#2d2d2d;font-weight:600}
  #frameout tbody tr:nth-child(even),#strout tbody tr:nth-child(even){background:#222}
  #frameout tr.pivot td{background:#2d2a1e}
  #frameout td.fr-sz{text-align:right}
  #frameout .acc{margin:2px 0 6px;color:#808080;font-size:12px}
  .ok{color:#6a9955}.err{color:#f14c4c}
  .bad{color:#1e1e1e;background:#f14c4c;border-radius:2px;padding:0 1px;font-weight:700}
  .jmp{color:#c586c0}
  .call{color:#dcdcaa}
  .jcc{color:#569cd6}
  .gutter{color:#4ec994}
  .addr{color:#608b4e}
  .dumps{color:#6d6d6d}
  .dst{color:#d7ba7d}
  .fr-sz{color:#6a9955}
  .fr-bp{color:#dcdcaa}
  .fr-off{color:#ce9178}
  .fr-name{color:#9cdcfe}
  .fr-note{color:#6a9955}
</style>
</head>
<body>
<header>
  <strong>asmview</strong>
  <label>arch
    <select id="arch">
      <option value="x86-32" selected>x86-32</option>
      <option value="x86-64">x86-64</option>
    </select>
  </label>
  <label>mode
    <select id="mode">
      <option value="auto" selected>auto</option>
      <option value="asm">asm -&gt; bytes</option>
      <option value="bytes">bytes -&gt; asm</option>
    </select>
  </label>
  <label>base
    <input id="base" type="text" value="0" title="listing origin"/>
  </label>
  <label>bad
    <input id="bad" type="text" value="00,0a,0d" title="bytes to highlight"/>
  </label>
  <button id="copybyte" type="button">copy .byte</button>
  <button id="framebtn" type="button" title="slot offset map">frame</button>
  <button id="strbtn" type="button" title="string ↔ push / mov / byte set">string</button>
  <span id="status" class="ok">ready</span>
</header>
<main>
  <textarea id="src" spellcheck="false" placeholder="; asm, strings, or raw bytes&#10;xor eax, eax&#10;.string &quot;cmd.exe&quot;&#10;&#10;; comma list ok: 89,e5,6a,0,c2,4,0"></textarea>
  <div class="split v" id="splitL" title="drag"></div>
  <pre id="out"></pre>
  <div class="split v" id="splitR" title="drag"></div>
  <div id="toolwrap">
  <div id="tooltabs">
    <button id="tabframe" type="button">Frame</button>
    <button id="tabstr" type="button">String</button>
  </div>
  <div id="framewrap">
    <div id="framebar">
      <label>reg <input id="framereg" type="text" value="ebp" title="frame base: ebp esi esp rax..."/></label>
      <button id="copyframe" type="button">copy report</button>
    </div>
    <textarea id="framein" spellcheck="false" placeholder="size  name  note&#10;blank line or the reg name = pivot&#10;4 ret  saved EIP&#10;4 arg0 first argument&#10;ebp&#10;4 tmp  hash scratch">4 ret  saved EIP
4 arg0 first argument
ebp
4 tmp  hash scratch
4 hash ROR13 result
8 si   STARTUPINFO
8 pi   PROCESS_INFORMATION</textarea>
    <div class="split h" id="splitF" title="drag"></div>
    <div id="frameout"></div>
  </div>
  <div id="strwrap">
    <div id="strbar">
      <label>reg <input id="strreg" type="text" value="ebp" title="mov [reg+off], imm" style="width:4.5em"/></label>
      <label>off <input id="stroff" type="text" value="0" title="first mov offset"/></label>
      <label class="chk"><input id="strnul" type="checkbox" checked/> nul</label>
      <button id="copystr" type="button">copy report</button>
    </div>
    <textarea id="strin" spellcheck="false" placeholder="shell32.dll&#10;cmd.exe&#10;&#10;push 0x006C6C64&#10;push 0x2E32336C&#10;push 0x6C656873&#10;&#10;mov [ebp+0x4], 0x6C656873&#10;mov [ebp+0x8], 0x2E32336C&#10;mov [ebp+0xC], 0x006C6C64&#10;&#10;{0x73,0x68,0x65,0x6C,0x6C,0x33,0x32,0x2E,0x64,0x6C,0x6C,0x00}"></textarea>
    <div class="split h" id="splitS" title="drag"></div>
    <div id="strout"></div>
  </div>
  </div>
</main>
<script>
const src = document.getElementById('src');
const out = document.getElementById('out');
const arch = document.getElementById('arch');
const mode = document.getElementById('mode');
const base = document.getElementById('base');
const bad = document.getElementById('bad');
const status = document.getElementById('status');
const copybyte = document.getElementById('copybyte');
const framebtn = document.getElementById('framebtn');
const framein = document.getElementById('framein');
const frameout = document.getElementById('frameout');
const framereg = document.getElementById('framereg');
const copyframe = document.getElementById('copyframe');
const strbtn = document.getElementById('strbtn');
const strin = document.getElementById('strin');
const strout = document.getElementById('strout');
const strreg = document.getElementById('strreg');
const stroff = document.getElementById('stroff');
const strnul = document.getElementById('strnul');
const copystr = document.getElementById('copystr');
const mainel = document.querySelector('main');
const splitL = document.getElementById('splitL');
const splitR = document.getElementById('splitR');
const splitF = document.getElementById('splitF');
const splitS = document.getElementById('splitS');
const framewrap = document.getElementById('framewrap');
const strwrap = document.getElementById('strwrap');
const toolwrap = document.getElementById('toolwrap');
const tabframe = document.getElementById('tabframe');
const tabstr = document.getElementById('tabstr');
let lastByte = '';
let lastFrameReport = '';
let lastStrReport = '';
let t = null;
let srcW = 280, frameW = 320, frameInH = 0;

function loadLayout() {
  try {
    const s = JSON.parse(localStorage.getItem('asmview.layout') || '{}');
    if (s.srcW) srcW = s.srcW;
    if (s.frameW) frameW = s.frameW;
    if (s.frameInH) frameInH = s.frameInH;
  } catch (e) {}
}
function saveLayout() {
  try {
    localStorage.setItem('asmview.layout', JSON.stringify({srcW, frameW, frameInH}));
  } catch (e) {}
}
function applyLayout() {
  const show = mainel.classList.contains('with-frame');
  mainel.style.gridTemplateColumns = show
    ? (srcW + 'px 6px 1fr 6px ' + frameW + 'px')
    : (srcW + 'px 6px 1fr');
  if (frameInH > 0) {
    framein.style.flex = '0 0 ' + frameInH + 'px';
    if (strin) strin.style.flex = '0 0 ' + frameInH + 'px';
  }
}
function bindDrag(el, kind) {
  el.addEventListener('mousedown', e => {
    e.preventDefault();
    el.classList.add('on');
    const startX = e.clientX, startY = e.clientY;
    const startSrc = srcW, startFr = frameW;
    const boxEl = kind === 'hs' ? strwrap : framewrap;
    const inEl = kind === 'hs' ? strin : framein;
    const startH = inEl.getBoundingClientRect().height;
    mainel.classList.add((kind === 'h' || kind === 'hs') ? 'dragging-h' : 'dragging');
    const move = ev => {
      const max = mainel.clientWidth;
      if (kind === 'src') {
        srcW = Math.min(Math.max(140, startSrc + ev.clientX - startX), max - 220);
      } else if (kind === 'frame') {
        frameW = Math.min(Math.max(180, startFr - (ev.clientX - startX)), max - 260);
      } else {
        const box = boxEl.getBoundingClientRect();
        frameInH = Math.min(Math.max(80, startH + ev.clientY - startY), box.height - 120);
      }
      applyLayout();
    };
    const up = () => {
      el.classList.remove('on');
      mainel.classList.remove('dragging', 'dragging-h');
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      saveLayout();
    };
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  });
}
loadLayout();
applyLayout();
bindDrag(splitL, 'src');
bindDrag(splitR, 'frame');
bindDrag(splitF, 'h');
bindDrag(splitS, 'hs');
window.addEventListener('resize', applyLayout);

function esc(s) {
  return String(s).replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
}
function fmtDisp(n) {
  const a = Math.abs(n);
  if (a === 0) return '0';
  if (a < 10) return String(a);
  return '0x' + a.toString(16);
}
function parseSize(tok) {
  if (!tok) return null;
  let t = tok.trim().toLowerCase();
  if (/^\d+$/.test(t)) return parseInt(t, 10);
  if (/^0x[0-9a-f]+$/.test(t)) return parseInt(t, 16);
  if (/^[0-9a-f]+h$/.test(t)) return parseInt(t.slice(0, -1), 16);
  return null;
}
function frameExpr(bp, off) {
  if (off === 0) return bp;
  return bp + (off > 0 ? ' + ' : ' - ') + fmtDisp(off);
}
function splitNameNote(rest) {
  rest = (rest || '').trim();
  if (!rest) return {name: '', note: ''};
  const sc = rest.indexOf(';');
  let body = rest, note = '';
  if (sc >= 0) {
    body = rest.slice(0, sc).trim();
    note = rest.slice(sc + 1).trim();
  }
  const m = body.match(/^(\S+)\s+(.*)$/);
  if (m) return {name: m[1], note: (note ? m[2] + ' ' + note : m[2]).trim()};
  return {name: body, note};
}
function baseReg() {
  const v = (framereg.value || '').trim();
  return v || (arch.value === 'x86-64' ? 'rbp' : 'ebp');
}
function ptrWidth() {
  const r = baseReg().toLowerCase();
  if (/^(r|e)?(ax|bx|cx|dx|si|di|bp|sp)$/.test(r) && r[0] !== 'r') return 4;
  if (/^r(ax|bx|cx|dx|si|di|bp|sp|8|9|1[0-5])$/.test(r)) return 8;
  return arch.value === 'x86-64' ? 8 : 4;
}
function accessHint(bp, off, sz) {
  const expr = off === 0 ? bp : (bp + (off > 0 ? '+' : '-') + fmtDisp(Math.abs(off)));
  if (sz === 1) return 'byte ptr [' + expr + ']';
  if (sz === 2) return 'word ptr [' + expr + ']';
  if (sz === 8) return 'qword ptr [' + expr + ']';
  return 'dword ptr [' + expr + ']';
}
function renderFrame() {
  const bp = baseReg();
  const rawLines = framein.value.replace(/\r/g, '').split('\n');
  const above = [];
  const below = [];
  let side = 'auto';
  for (const raw of rawLines) {
    let line = raw.trim();
    if (!line) {
      if (side === 'auto' && above.length) side = 'below';
      continue;
    }
    const low = line.toLowerCase();
    if (low === bp.toLowerCase() || low === 'pivot' || /^[-]{2,}$/.test(line) || /^[=]{2,}$/.test(line)) {
      side = 'below';
      continue;
    }
    let sign = null;
    if (line[0] === '+' || line[0] === '-') {
      sign = line[0];
      line = line.slice(1).trim();
    }
    const m = line.match(/^(\S+)(?:\s+(.*))?$/);
    if (!m) continue;
    const sz = parseSize(m[1]);
    if (!sz || sz < 1) continue;
    const nn = splitNameNote(m[2] || '');
    const rec = {sz, name: nn.name, note: nn.note};
    if (sign === '+') above.push(rec);
    else if (sign === '-') below.push(rec);
    else if (side === 'below') below.push(rec);
    else above.push(rec);
  }
  const ptr = ptrWidth();
  let off = ptr;
  const aboveFix = [];
  for (let i = above.length - 1; i >= 0; i--) {
    const rec = above[i];
    aboveFix.push({sz: rec.sz, name: rec.name, note: rec.note, off});
    off += rec.sz;
  }
  aboveFix.reverse();
  off = 0;
  const belowRows = [];
  for (const rec of below) {
    off += rec.sz;
    belowRows.push({sz: rec.sz, name: rec.name, note: rec.note, off: -off});
  }
  const rows = [];
  const push = (sz, expr, name, note, kind, offv) => {
    rows.push({sz, expr, name: name || '', note: note || '', kind, off: offv || 0});
  };
  for (const r of aboveFix) push(r.sz, frameExpr(bp, r.off), r.name, r.note, 'above', r.off);
  push('', bp, '', 'frame pointer', 'pivot', 0);
  for (const r of belowRows) push(r.sz, frameExpr(bp, r.off), r.name, r.note, 'below', r.off);
  if (!aboveFix.length && !belowRows.length) {
    frameout.textContent = 'size  name  note — blank / ' + bp + ' = pivot';
    lastFrameReport = '';
    return;
  }
  let html = '<table><thead><tr><th>Size</th><th>Offset</th><th>Name</th><th>Notes</th></tr></thead><tbody>';
  for (const r of rows) {
    const cls = r.kind === 'pivot' ? ' class="pivot"' : '';
    html += '<tr' + cls + '><td class="fr-sz">' + esc(r.sz) + '</td><td class="fr-off">'
      + esc(r.expr) + '</td><td class="fr-name">' + esc(r.name) + '</td><td class="fr-note">'
      + esc(r.note) + '</td></tr>';
  }
  html += '</tbody></table>';
  html += '<div class="acc">Access</div><table><thead><tr><th>Operand</th><th>Name</th><th>Notes</th></tr></thead><tbody>';
  for (const r of rows) {
    if (r.kind === 'pivot' || !r.sz) continue;
    html += '<tr><td class="fr-off">' + esc(accessHint(bp, r.off, r.sz)) + '</td><td class="fr-name">'
      + esc(r.name) + '</td><td class="fr-note">' + esc(r.note) + '</td></tr>';
  }
  html += '</tbody></table>';
  frameout.innerHTML = html;

  const md = [];
  md.push(bp + ' stack frame');
  md.push('');
  md.push('| Size | Offset | Name | Notes |');
  md.push('| ---: | --- | --- | --- |');
  for (const r of rows) {
    md.push('| ' + (r.sz || '') + ' | ' + r.expr + ' | ' + r.name + ' | ' + r.note + ' |');
  }
  md.push('');
  md.push('| Operand | Name | Notes |');
  md.push('| --- | --- | --- |');
  for (const r of rows) {
    if (r.kind === 'pivot' || !r.sz) continue;
    md.push('| `' + accessHint(bp, r.off, r.sz) + '` | ' + r.name + ' | ' + r.note + ' |');
  }
  md.push('');
  md.push('Access');
  for (const r of rows) {
    if (r.kind === 'pivot' || !r.sz) continue;
    const label = [r.name, r.note].filter(Boolean).join(' — ');
    md.push('  ' + accessHint(bp, r.off, r.sz) + (label ? '    ; ' + label : ''));
  }
  lastFrameReport = md.join('\n');
}
function parseImm(tok) {
  if (!tok) return null;
  let t = String(tok).trim().toLowerCase();
  if (/^0x[0-9a-f]+$/.test(t)) return parseInt(t, 16);
  if (/^[0-9a-f]+h$/.test(t)) return parseInt(t.slice(0, -1), 16);
  if (/^\d+$/.test(t)) return parseInt(t, 10);
  return null;
}
function bytesFromImm(v, width) {
  const out = [];
  for (let i = 0; i < width; i++) out.push((v >>> (8 * i)) & 0xff);
  return out;
}
function immFromBytes(bs) {
  let v = 0;
  for (let i = 0; i < bs.length; i++) v |= (bs[i] & 0xff) << (8 * i);
  return v >>> 0;
}
function fmtImm(v, width) {
  const n = width * 2;
  return '0x' + (v >>> 0).toString(16).toUpperCase().padStart(n, '0');
}
function fmtMemOff(off) {
  if (off === 0) return '';
  return (off > 0 ? '+' : '-') + '0x' + Math.abs(off).toString(16).toUpperCase();
}
function printable(bytes) {
  let s = '';
  for (const b of bytes) {
    if (b === 0) s += '\\0';
    else if (b === 9) s += '\\t';
    else if (b === 10) s += '\\n';
    else if (b === 13) s += '\\r';
    else if (b >= 0x20 && b < 0x7f) s += String.fromCharCode(b);
    else s += '\\x' + b.toString(16).padStart(2, '0');
  }
  return s;
}
function asciiPreview(bytes) {
  const cut = [];
  for (const b of bytes) {
    if (b === 0) break;
    cut.push(b);
  }
  return printable(cut.length ? cut : bytes.filter(b => b !== 0));
}
function decodeEscapes(s) {
  const out = [];
  for (let i = 0; i < s.length; i++) {
    if (s[i] === '\\' && i + 1 < s.length) {
      const n = s[i + 1];
      if (n === 'x' && i + 3 < s.length && /[0-9A-Fa-f]{2}/.test(s.slice(i + 2, i + 4))) {
        out.push(parseInt(s.slice(i + 2, i + 4), 16));
        i += 3;
        continue;
      }
      const map = {n: 10, t: 9, r: 13, '0': 0, '\\': 92, '"': 34, "'": 39};
      if (n in map) { out.push(map[n]); i += 1; continue; }
    }
    out.push(s.charCodeAt(i) & 0xff);
  }
  return out;
}
function stripQuotes(s) {
  s = s.trim();
  if (s.length >= 2 && ((s[0] === '"' && s[s.length - 1] === '"') || (s[0] === "'" && s[s.length - 1] === "'")))
    return s.slice(1, -1);
  return s;
}
function parseByteSet(text) {
  const t = text.trim();
  const brace = t.match(/^\{([^}]*)\}$/);
  if (brace) {
    const toks = brace[1].split(/[\s,;]+/).filter(Boolean);
    if (!toks.length) return null;
    const vals = [];
    for (const tok of toks) {
      const v = parseImm(tok);
      if (v === null || v < 0 || v > 255) return null;
      vals.push(v);
    }
    return vals;
  }
  const xs = [...t.matchAll(/\\x([0-9A-Fa-f]{2})/g)].map(m => parseInt(m[1], 16));
  if (xs.length >= 2 && t.replace(/\\x[0-9A-Fa-f]{2}/g, '').replace(/[\s,;_"'b]/g, '') === '')
    return xs;
  const csv = t.split(/[\s,;]+/).filter(Boolean);
  if (csv.length >= 4 && csv.every(tok => /^(?:0x)?[0-9A-Fa-f]{1,2}h?$/.test(tok)))
    return csv.map(tok => parseImm(tok));
  return null;
}
function parseEncoded(text) {
  const raw = text.replace(/\r/g, '');
  const body = raw.replace(/[;#].*$/gm, '');
  const pushes = [];
  const pushRe = /\bpush\s+(?:dword\s+(?:ptr\s+)?)?((?:0x[0-9A-Fa-f]+|[0-9A-Fa-f]+h|\d+))/gi;
  let m;
  while ((m = pushRe.exec(body))) pushes.push(parseImm(m[1]));
  const movs = [];
  const movRe = /\bmov\s*(?:dword\s+ptr\s*)?\[\s*([A-Za-z]+)\s*(?:([+-])\s*((?:0x[0-9A-Fa-f]+|[0-9A-Fa-f]+h|\d+)))?\s*\]\s*,\s*((?:0x[0-9A-Fa-f]+|[0-9A-Fa-f]+h|\d+))/gi;
  while ((m = movRe.exec(body))) {
    const offTok = m[3] || '0';
    let off = parseImm(offTok) || 0;
    if (m[2] === '-') off = -off;
    movs.push({reg: m[1], off, val: parseImm(m[4]) >>> 0});
  }
  if (movs.length) {
    movs.sort((a, b) => a.off - b.off);
    const bytes = [];
    for (const rec of movs) bytes.push(...bytesFromImm(rec.val, 4));
    return {kind: 'mov', bytes, reg: movs[0].reg, off: movs[0].off};
  }
  if (pushes.length) {
    const bytes = [];
    for (let i = pushes.length - 1; i >= 0; i--) bytes.push(...bytesFromImm(pushes[i] >>> 0, 4));
    return {kind: 'push', bytes};
  }
  const set = parseByteSet(body);
  if (set) return {kind: 'bytes', bytes: set};
  return null;
}
function chunkDwords(bytes) {
  const pad = bytes.slice();
  while (pad.length % 4) pad.push(0);
  const words = [];
  for (let i = 0; i < pad.length; i += 4) {
    const slice = pad.slice(i, i + 4);
    words.push({off: i, bytes: slice, val: immFromBytes(slice)});
  }
  return {pad, words};
}
function renderStr() {
  const text = (strin.value || '').replace(/\r/g, '');
  if (!text.trim()) {
    strout.innerHTML = '<span class="hint">string / push / mov / byte set</span>';
    lastStrReport = '';
    return;
  }
  const decoded = parseEncoded(text);
  let bytes, kind;
  if (decoded) {
    bytes = decoded.bytes.slice();
    kind = decoded.kind;
  } else {
    let lit = text;
    const lines = text.split('\n').map(l => l.replace(/;.*$/, '')).filter(l => l.trim());
    if (lines.length === 1) lit = stripQuotes(lines[0]);
    else if (lines.every(l => !/\b(push|mov)\b/i.test(l))) lit = lines.map(stripQuotes).join('');
    bytes = decodeEscapes(lit);
    if (strnul.checked && (bytes.length === 0 || bytes[bytes.length - 1] !== 0)) bytes.push(0);
    kind = 'string';
  }
  const kindName = ({string:'string', push:'push', mov:'mov', bytes:'bytes'}[kind] || kind);
  const bp = ((strreg.value || '').trim() || 'ebp');
  let startOff = parseSize((stroff.value || '0').trim());
  if (startOff === null) startOff = 0;
  if (decoded && decoded.off != null && String(stroff.value).trim() === '0' && decoded.off !== 0)
    startOff = decoded.off;
  const packed = chunkDwords(bytes);
  const pushLines = packed.words.slice().reverse().map(w =>
    '    push ' + fmtImm(w.val, 4) + '    # ' + printable(w.bytes));
  const movLines = packed.words.map(w => {
    const expr = bp + fmtMemOff(startOff + w.off);
    return '    mov dword ptr [' + expr + '], ' + fmtImm(w.val, 4) + '    # ' + printable(w.bytes);
  });
  const hexSp = bytes.map(b => b.toString(16).padStart(2, '0')).join(' ');
  const escX = bytes.map(b => '\\x' + b.toString(16).padStart(2, '0')).join('');
  const setHex = '{' + bytes.map(b => '0x' + b.toString(16).toUpperCase().padStart(2, '0')).join(',') + '}';
  const setDec = '{' + bytes.map(b => String(b)).join(',') + '}';
  const preview = asciiPreview(bytes);
  const blocks = [
    ['string', preview + '    ; ' + kindName + '  ' + bytes.length + ' bytes'],
    ['push', pushLines.join('\n')],
    ['mov', movLines.join('\n')],
    ['bytes', setDec + '\n' + setHex],
    ['esc', escX],
    ['hex', hexSp]
  ];
  let html = '';
  for (const [title, body] of blocks) {
    html += '<div class="blk"><h4>' + esc(title) + '</h4><pre class="blkbody">' + esc(body) + '</pre></div>';
  }
  strout.innerHTML = html;
  lastStrReport = blocks.map(([t, b]) => t + '\n' + b).join('\n\n');
}
async function convert() {
  const body = JSON.stringify({
    src: src.value, arch: arch.value, mode: mode.value,
    base: base.value, bad: bad.value
  });
  try {
    const r = await fetch('/asm', {method:'POST', headers:{'Content-Type':'application/json'}, body});
    const j = await r.json();
    if (j.error) { status.className='err'; status.textContent=j.error; out.textContent=''; return; }
    status.className='ok';
    const nbad = j.nbad || 0;
    status.textContent = (j.kind || 'ok') + '  ' + j.nbytes + ' bytes' + (nbad ? ('  ' + nbad + ' bad') : '');
    out.innerHTML = j.listing_html || '';
    lastByte = j.byte_line || '';
  } catch (e) {
    status.className='err'; status.textContent=String(e);
  }
}
copybyte.addEventListener('click', async () => {
  if (!lastByte) return;
  try { await navigator.clipboard.writeText(lastByte); status.textContent = 'copied .byte'; }
  catch (e) { status.className='err'; status.textContent=String(e); }
});
function schedule() { clearTimeout(t); t = setTimeout(convert, 140); }
src.addEventListener('input', schedule);
arch.addEventListener('change', () => { convert(); renderFrame(); });
mode.addEventListener('change', convert);
base.addEventListener('input', schedule);
bad.addEventListener('input', schedule);
framein.addEventListener('input', renderFrame);
framereg.addEventListener('input', renderFrame);
strin.addEventListener('input', renderStr);
strreg.addEventListener('input', renderStr);
stroff.addEventListener('input', renderStr);
strnul.addEventListener('change', renderStr);
copyframe.addEventListener('click', async () => {
  if (!lastFrameReport) return;
  try { await navigator.clipboard.writeText(lastFrameReport); status.textContent = 'copied frame report'; }
  catch (e) { status.className = 'err'; status.textContent = String(e); }
});
copystr.addEventListener('click', async () => {
  if (!lastStrReport) return;
  try { await navigator.clipboard.writeText(lastStrReport); status.textContent = 'copied str report'; }
  catch (e) { status.className = 'err'; status.textContent = String(e); }
});
function showTool(which, toggle) {
  const cur = framewrap.classList.contains('show') ? 'frame'
    : strwrap.classList.contains('show') ? 'str' : '';
  const next = (toggle && cur === which) ? '' : which;
  framewrap.classList.toggle('show', next === 'frame');
  strwrap.classList.toggle('show', next === 'str');
  framebtn.classList.toggle('on', next === 'frame');
  strbtn.classList.toggle('on', next === 'str');
  tabframe.classList.toggle('on', next === 'frame');
  tabstr.classList.toggle('on', next === 'str');
  mainel.classList.toggle('with-frame', !!next);
  applyLayout();
  if (next === 'frame') renderFrame();
  if (next === 'str') renderStr();
}
framebtn.addEventListener('click', () => showTool('frame', true));
strbtn.addEventListener('click', () => showTool('str', true));
tabframe.addEventListener('click', () => showTool('frame', false));
tabstr.addEventListener('click', () => showTool('str', false));
renderFrame();
renderStr();
convert();
</script>
</body>
</html>
"""

ASM_HINT = re.compile(
    r"\b(mov|xor|or|and|add|sub|push|pop|call|jmp|ret|nop|lea|cmp|test|"
    r"inc|dec|xchg|int|loop|j[n]?[abglseocpsz]+|syscall|leave|enter|"
    r"imul|mul|div|idiv|shl|shr|sal|sar|rol|ror|clc|stc|cld|std|"
    r"section|global|bits|org|\.string|\.ascii|\.asciz|\.byte)\b",
    re.I,
)
BYTE_DIR = re.compile(r"^\s*\.(?:byte|ascii|asciz|string)\b|^\s*d[bwdq]\b", re.I)
HEX_PAIR = re.compile(r"[0-9A-Fa-f]{2}")
HEX_TOK = re.compile(r"^(?:0x)?([0-9A-Fa-f]{1,2})h?$", re.I)


def _strip_comments(text):
    out = []
    for line in text.splitlines():
        if ";" in line:
            line = line[: line.index(";")]
        if "//" in line:
            line = line[: line.index("//")]
        out.append(line)
    return "\n".join(out)


def parse_bad(text):
    """00,0a,0d or 0 0a \\x00 → set of ints."""
    if not text or not str(text).strip():
        return {0x00, 0x0A, 0x0D}
    vals = set()
    for tok in re.split(r"[\s,|]+", str(text).strip()):
        if not tok:
            continue
        t = tok.lower()
        if t.startswith("\\x"):
            t = t[2:]
        if t.startswith("0x"):
            t = t[2:]
        if t.endswith("h"):
            t = t[:-1]
        try:
            v = int(t, 16)
        except ValueError:
            continue
        if 0 <= v <= 255:
            vals.add(v)
    return vals or {0x00, 0x0A, 0x0D}


def parse_separated_bytes(text):
    """89,e5,6a,0,c2,4,0  → include single-digit tokens as 00..0f."""
    body = _strip_comments(text)
    body = body.replace("\\x", " ").replace("\\X", " ")
    raw_toks = re.split(r"[\s,|_]+", body.strip())
    toks = [t for t in raw_toks if t]
    if len(toks) < 2:
        return None
    vals = []
    for t in toks:
        t = t.strip().strip(";")
        m = HEX_TOK.fullmatch(t)
        if not m:
            return None
        vals.append(int(m.group(1), 16))
    return bytes(vals) if vals else None


def parse_bytes(text):
    """Parse 31c0, \\x31\\xc0, 0x31 0xc0, 89,e5,4,0, .byte 0x31,0xc0."""
    text = _strip_comments(text)

    def take_esc(s):
        found = list(re.finditer(r"\\x([0-9A-Fa-f]{2})", s, re.I))
        if not found:
            return None
        return bytes(int(m.group(1), 16) for m in found)

    # comma/space list first so "c2,4,0" is 3 bytes, not stripped to "c240"
    sep = parse_separated_bytes(text)
    if sep is not None:
        return sep

    esc = take_esc(text)
    if esc and len(esc) >= 1 and text.count("\\x") >= 1:
        return esc

    nums = []
    for m in re.finditer(
        r"(?:0x([0-9A-Fa-f]{1,2})|([0-9A-Fa-f]{2})h)\b", text, re.I
    ):
        nums.append(int(m.group(1) or m.group(2), 16))
    dotted = bool(re.search(r"\.(?:byte|ascii)|^\s*d[bwdq]\b", text, re.I | re.M))
    if nums and (dotted or "0x" in text.lower() or re.search(r"[0-9A-Fa-f]{2}h\b", text, re.I)):
        if len(nums) >= 1 and not ASM_HINT.search(text):
            return bytes(nums)
        if dotted and nums:
            return bytes(nums)

    compact = re.sub(r"[\s,|_:\-]+", "", text)
    compact = re.sub(r"^0x", "", compact, flags=re.I)
    if compact and re.fullmatch(r"[0-9A-Fa-f]+", compact) and len(compact) % 2 == 0:
        if len(compact) >= 2 and not ASM_HINT.search(text):
            return bytes.fromhex(compact)

    pairs = HEX_PAIR.findall(re.sub(r"[^0-9A-Fa-f\s,]", " ", text))
    if pairs and not ASM_HINT.search(text) and len(pairs) >= 1:
        return bytes(int(p, 16) for p in pairs)
    return None


STRING_DIR = re.compile(
    r"""^\s*(?:\.(?:string|ascii|asciz|byte)|d[bwdq])\s+""",
    re.I | re.M,
)


def looks_like_bytes(text):
    body = _strip_comments(text)
    if STRING_DIR.search(body):
        return False
    raw = parse_bytes(text)
    if not raw:
        return False
    if ASM_HINT.search(body) and not BYTE_DIR.search(body):
        if "\\x" in body or re.fullmatch(r"[\s0-9A-Fa-fxh,\\]+", body.strip(), re.I):
            return True
        return False
    return True


def branch_target(insn):
    # Capstone: CS_OP_REG=1, CS_OP_IMM=2. type==1 made `call eax` look like a target.
    m = insn.mnemonic.lower()
    if not (m.startswith("j") or m in ("call", "loop", "loope", "loopne")):
        return None
    for op in insn.operands:
        if int(op.type) == 2 and hasattr(op, "imm"):
            return int(op.imm)
    return None


def _xfer_class(tx):
    m = (tx.split() or [""])[0].lower()
    if m == "call":
        return "call"
    if m == "jmp" or m.startswith("loop"):
        return "jmp"
    if m.startswith("j"):
        return "jcc"
    return ""


def _color_hex(hb, bad):
    """hb is packed hex like 6a00 → '6a <span class=bad>00</span>'."""
    parts = []
    raw = bytes.fromhex(hb) if hb else b""
    for b in raw:
        cell = "%02x" % b
        if b in bad:
            parts.append('<span class="bad">%s</span>' % cell)
        else:
            parts.append(cell)
    return " ".join(parts)


def _lane_glyph(i, lane):
    """3-char cell for row i in a dest-merged lane. Gutter sits left of the insn."""
    lo, hi, dst, srcs = lane["lo"], lane["hi"], lane["dst"], lane["srcs"]
    if i < lo or i > hi:
        return "   "
    is_src = i in srcs
    is_dst = i == dst
    if is_dst and is_src:
        return "◄► "
    if is_dst:
        above = lo < dst
        below = hi > dst
        if above and below:
            return "├─►"
        if above:
            return "└─►"
        return "┌─►"
    if is_src:
        if i == lo:
            return "┌──"
        if i == hi:
            return "└──"
        return "├──"
    return "│  "


def draw_listing(insns, raw, origin, bad=None):
    """insns: list of (addr, size, hexbytes, text, target_or_None)."""
    bad = bad or {0x00, 0x0A, 0x0D}
    idx_of = {row[0]: i for i, row in enumerate(insns)}

    by_dst = {}
    external = {}
    for i, (_addr, _sz, _hb, _tx, tgt) in enumerate(insns):
        if tgt is None:
            continue
        if tgt in idx_of:
            by_dst.setdefault(idx_of[tgt], []).append(i)
        else:
            external[i] = tgt

    lanes = []
    for dst, srcs in by_dst.items():
        points = srcs + [dst]
        lanes.append({
            "dst": dst,
            "srcs": set(srcs),
            "lo": min(points),
            "hi": max(points),
            "col": 0,
        })

    # Longest span first → outer (left) columns; short jumps hug the text.
    lanes.sort(key=lambda x: (x["hi"] - x["lo"], x["lo"]), reverse=True)
    taken = []
    ncols = 0
    for ln in lanes:
        used = {t["col"] for t in taken if not (t["hi"] < ln["lo"] or t["lo"] > ln["hi"])}
        col = 0
        while col in used:
            col += 1
        ln["col"] = col
        ncols = max(ncols, col + 1)
        taken.append(ln)
    ncols = min(ncols, 12)
    slot = 4  # 3-char glyph + gap; never write blanks (shared cols would erase)
    width = ncols * slot
    hexw = max((len(row[2]) // 2) * 3 - 1 for row in insns) if insns else 18
    hexw = max(hexw, 18)

    lines = []
    html_lines = []
    nbad = 0
    for i, (addr, _sz, hb, tx, tgt) in enumerate(insns):
        rawb = bytes.fromhex(hb) if hb else b""
        nbad += sum(1 for b in rawb if b in bad)
        gutter = [" "] * width
        for ln in lanes:
            c = ln["col"]
            if c >= ncols:
                continue
            glyph = _lane_glyph(i, ln)
            if not glyph.strip():
                continue
            x = c * slot
            gutter[x : x + 3] = list(glyph[:3])
        g = "".join(gutter)
        extra = ""
        if i in external:
            extra = "  → %04x" % (external[i] & 0xFFFFFFFF,)
        hx_plain = " ".join("%02x" % b for b in rawb)
        hx_plain = "%-*s" % (hexw, hx_plain)
        g_field = (g + "  ") if width else ""
        lines.append("%04x  %s  %s%s%s" % (addr, hx_plain, g_field, tx, extra))

        hx_html = _color_hex(hb, bad)
        pad = max(hexw - (len(rawb) * 3 - 1 if rawb else 0), 0)
        cls = _xfer_class(tx)
        is_dst = any(ln["dst"] == i for ln in lanes)
        tx_html = html.escape(tx + extra)
        if cls:
            tx_html = '<span class="%s">%s</span>' % (cls, tx_html)
        elif is_dst:
            tx_html = '<span class="dst">%s</span>' % tx_html
        g_html = ('<span class="gutter">%s</span>  ' % html.escape(g)) if width else ""
        html_lines.append(
            '<span class="addr">%04x</span>  %s%s  %s%s'
            % (addr, hx_html, " " * pad, g_html, tx_html)
        )
    return lines, html_lines, nbad


def engines(arch):
    from capstone import CS_ARCH_X86, CS_MODE_32, CS_MODE_64, Cs
    from keystone import KS_ARCH_X86, KS_MODE_32, KS_MODE_64, Ks

    bits32 = arch != "x86-64"
    ks = Ks(KS_ARCH_X86, KS_MODE_32 if bits32 else KS_MODE_64)
    cs = Cs(CS_ARCH_X86, CS_MODE_32 if bits32 else CS_MODE_64)
    cs.detail = True
    return ks, cs


def disassemble_raw(raw, cs, origin):
    insns = []
    off = 0
    for insn in cs.disasm(raw, origin):
        hb = raw[insn.address - origin : insn.address - origin + insn.size].hex()
        tx = ("%s %s" % (insn.mnemonic, insn.op_str)).strip()
        insns.append((insn.address, insn.size, hb, tx, branch_target(insn)))
        off = insn.address - origin + insn.size
    if off < len(raw):
        rest = raw[off:]
        insns.append((origin + off, len(rest), rest.hex(), ".byte " + ", ".join("0x%02x" % b for b in rest), None))
    return insns


def dumps(raw):
    hx = raw.hex()
    esc = "\\x" + "\\x".join("%02x" % b for b in raw)
    csv = ", ".join("0x%02x" % b for b in raw)
    byte_line = ".byte " + csv
    return [
        "",
        "; dumps",
        byte_line,
        "db " + csv,
        hx,
        esc,
        csv,
    ], byte_line


_SKIP = re.compile(r"^\s*(bits|use16|use32|use64|section|segment|global|extern)\b", re.I)
_LABEL = re.compile(r"^([A-Za-z_@.?][\w@.?$]*)\s*:\s*(.*)$")
_DATA = re.compile(r"^\s*(\.(?:string|asciz|ascii|byte)|d[bwdq])\s+(.*)$", re.I)
_NUM = re.compile(r"(?:0x[0-9A-Fa-f]+|[0-9A-Fa-f]+h|\d+)", re.I)


def _unescape(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1]
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "x" and i + 3 < len(s):
                out.append(int(s[i + 2 : i + 4], 16))
                i += 4
                continue
            out.append({"n": 10, "t": 9, "r": 13, "0": 0, "\\": 92, '"': 34, "'": 39}.get(n, ord(n)))
            i += 2
            continue
        out.append(ord(s[i]))
        i += 1
    return bytes(out)


def _parse_nums(rest):
    out = []
    i = 0
    while i < len(rest):
        c = rest[i]
        if c in " \t,":
            i += 1
            continue
        if c in "\"'":
            q = c
            j = i + 1
            buf = []
            while j < len(rest):
                if rest[j] == "\\" and j + 1 < len(rest):
                    buf.append(rest[j : j + 2])
                    j += 2
                    continue
                if rest[j] == q:
                    break
                buf.append(rest[j])
                j += 1
            out.append(("str", _unescape(q + "".join(buf) + q)))
            i = j + 1
            continue
        m = _NUM.match(rest, i)
        if m:
            tok = m.group(0)
            if tok.lower().endswith("h"):
                out.append(("num", int(tok[:-1], 16)))
            else:
                out.append(("num", int(tok, 0)))
            i = m.end()
            continue
        i += 1
    return out


def encode_data(kind, rest):
    kind = kind.lower()
    items = _parse_nums(rest)
    raw = bytearray()
    width = {"db": 1, ".byte": 1, "dw": 2, ".word": 2, "dd": 4, "dq": 8}.get(kind, 1)
    nul = kind in (".string", ".asciz")
    if kind in (".string", ".ascii", ".asciz"):
        width = 1
    for typ, val in items:
        if typ == "str":
            raw.extend(val)
        else:
            raw.extend(int(val).to_bytes(width, "little", signed=val < 0))
    if nul:
        raw.append(0)
    return bytes(raw)


_XFER = re.compile(r"^(call|jmp|j[a-z]+|loopn?e?)\s+([A-Za-z_@.?][\w@.?$]*)$", re.I)


def assemble_intel(src, ks, origin):
    """Same text as ks = Ks(KS_ARCH_X86, KS_MODE_32); extra directives are expanded."""
    from keystone import KsError

    items = []

    def split_comment(line):
        if ";" in line:
            return line[: line.index(";")].strip()
        return line.strip()

    for line in src.splitlines():
        code = split_comment(line)
        if not code:
            continue
        extra = None
        m = _LABEL.match(code)
        if m:
            extra = ("label", m.group(1))
            code = m.group(2).strip()
            items.append(extra)
        if not code:
            continue
        if _SKIP.match(code):
            continue
        dm = _DATA.match(code)
        if dm:
            items.append(("data", encode_data(dm.group(1), dm.group(2))))
            continue
        items.append(("asm", code))

    def guess_len(text):
        # Conservative near encodings so forward labels only shrink on later passes.
        xm = _XFER.match(text)
        if xm:
            op = xm.group(1).lower()
            if op == "call":
                return 5
            if op == "jmp" or op.startswith("loop"):
                return 5
            return 6
        try:
            enc, _n = ks.asm(text, 0)
            return len(bytes(enc)) if enc is not None else 5
        except KsError:
            return 5

    def layout(lab):
        labels = dict(lab)
        out = bytearray()
        placed = {}
        pc = origin
        for kind, val in items:
            if kind == "label":
                placed[val] = pc
                continue
            if kind == "data":
                out.extend(val)
                pc += len(val)
                continue
            text = val
            xm = _XFER.match(text)
            if xm and xm.group(2) in labels:
                text = "%s 0x%x" % (xm.group(1), labels[xm.group(2)])
            try:
                enc, _n = ks.asm(text, pc)
            except KsError as e:
                raise ValueError("%s: %s" % (text, e))
            if enc is None:
                raise ValueError("Invalid mnemonic: %s" % text)
            blob = bytes(enc)
            out.extend(blob)
            pc += len(blob)
        return bytes(out), placed

    labels = {}
    pc = origin
    for kind, val in items:
        if kind == "label":
            labels[val] = pc
        elif kind == "data":
            pc += len(val)
        else:
            pc += guess_len(val)

    raw, labels = layout(labels)
    for _ in range(8):
        raw2, lab2 = layout(labels)
        if lab2 == labels and raw2 == raw:
            break
        raw, labels = raw2, lab2
    return raw


def convert(src, arch, mode, base, bad_text="00,0a,0d"):
    try:
        from keystone import KsError
    except ImportError:
        return {
            "error": "install: pip3 install keystone-engine capstone",
            "listing": "",
            "listing_html": "",
            "nbytes": 0,
            "kind": "",
        }

    src = src.strip()
    if not src:
        return {"listing": "", "listing_html": "", "nbytes": 0, "error": None, "kind": "empty"}

    try:
        origin = int(str(base).strip() or "0", 0)
    except ValueError:
        origin = 0
    bad = parse_bad(bad_text)

    try:
        ks, cs = engines(arch)
    except Exception as e:
        return {"error": str(e), "listing": "", "listing_html": "", "nbytes": 0, "kind": ""}

    use_bytes = mode == "bytes" or (mode == "auto" and looks_like_bytes(src))
    raw = None
    kind = "asm"

    if use_bytes:
        raw = parse_bytes(src)
        if raw is None and mode == "bytes":
            return {"error": "could not parse bytes", "listing": "", "listing_html": "", "nbytes": 0, "kind": "bytes"}
        if raw is not None:
            kind = "bytes"

    if raw is None:
        kind = "asm"
        try:
            raw = assemble_intel(src, ks, origin)
        except (KsError, ValueError) as e:
            raw = parse_bytes(src)
            if raw is None:
                return {"error": str(e), "listing": "", "listing_html": "", "nbytes": 0, "kind": "asm", "byte_line": ""}
            kind = "bytes"

    insns = disassemble_raw(raw, cs, origin)
    lines, html_lines, nbad = draw_listing(insns, raw, origin, bad)
    dump_lines, byte_line = dumps(raw)
    lines.extend(dump_lines)
    html_lines.append('<span class="dumps">')
    html_lines.extend(html.escape(x) if x else "" for x in dump_lines)
    html_lines.append("</span>")
    return {
        "listing": "\n".join(lines),
        "listing_html": "\n".join(html_lines),
        "nbytes": len(raw),
        "nbad": nbad,
        "error": None,
        "kind": kind,
        "byte_line": byte_line,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(n) or b"{}")
        out = convert(
            data.get("src") or "",
            data.get("arch") or "x86-32",
            data.get("mode") or "auto",
            data.get("base") or "0",
            data.get("bad") or "00,0a,0d",
        )
        body = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def main():
    p = argparse.ArgumentParser(description="Live asm <-> bytes viewer")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("Open http://127.0.0.1:%d" % args.port)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
