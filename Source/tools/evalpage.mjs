// 在 headless Chrome 里打开页面并求值一个 JS 表达式，用于验收（不改页面状态）
// 用法: node tools/evalpage.mjs <url> "<expr>" [waitMs]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const [, , url, expr, waitMsArg] = process.argv;
const waitMs = +(waitMsArg || 2500);
const W = 1440, H = 900;

const PORT = await (async () => {
  const net = await import('node:net');
  for (let p = 9911; p < 9999; p++) {
    const busy = await new Promise(res => {
      const s = net.connect(p, '127.0.0.1');
      s.on('connect', () => { s.destroy(); res(true); });
      s.on('error', () => res(false));
    });
    if (!busy) return p;
  }
  throw new Error('no free port');
})();

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'evalp-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`,
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--hide-scrollbars',
  `--window-size=${W},${H}`, '--no-sandbox', `--user-data-dir=${profile}`, 'about:blank'],
  { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, id = 0; const pend = new Map(); const logs = [];
try {
  let page = null;
  for (let i = 0; i < 120 && !page; i++) {
    try {
      const j = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      page = j.find(p => p.type === 'page');
    } catch { }
    if (!page) await sleep(250);
  }
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.method === 'Runtime.exceptionThrown') logs.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 200));
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error')
      logs.push('ERR ' + m.params.args.map(a => a.value ?? a.description ?? '').join(' ').slice(0, 200));
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  };
  const send = (method, params = {}) => {
    const i = ++id;
    ws.send(JSON.stringify({ id: i, method, params }));
    return new Promise(r => pend.set(i, r));
  };
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Page.navigate', { url });
  await sleep(waitMs);
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  console.log(JSON.stringify({ value: r.result?.result?.value, logs }, null, 1));
} catch (e) {
  console.log(JSON.stringify({ error: String(e), logs }));
} finally {
  try { ws?.close(); } catch { }
  chrome.kill();
}
process.exit(0);
