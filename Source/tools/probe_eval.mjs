// 打开页面并执行一段表达式，返回结果（调试用）
// 用法: node tools/probe_eval.mjs <url> "<js 表达式>" [waitMs]
import { spawn } from 'node:child_process';

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const [, , url, expr, waitMsArg, pngOut] = process.argv;
const waitMs = +(waitMsArg || 12000);
const PORT = 9500 + Math.floor(Math.random() * 300);

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`,
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--hide-scrollbars', '--window-size=1200,700',
  '--no-sandbox', '--disable-dev-shm-usage', 'about:blank',
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function targets() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const j = await r.json();
      if (j.length) return j;
    } catch { }
    await sleep(250);
  }
  throw new Error('chrome 没起来');
}

const pages = await targets();
const page = pages.find(p => p.type === 'page') || pages[0];
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);

let id = 0;
const pend = new Map();
const errs = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.method === 'Runtime.exceptionThrown') {
    const d = m.params.exceptionDetails;
    errs.push('EXC: ' + (d.exception?.description || d.text));
  }
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
};
const send = (method, params = {}) => {
  const i = ++id; ws.send(JSON.stringify({ id: i, method, params }));
  return new Promise(r => pend.set(i, r));
};

await send('Page.enable');
await send('Runtime.enable');
await send('Page.navigate', { url });
await sleep(800);
for (let i = 0; i < 150; i++) {
  const r = await send('Runtime.evaluate', { expression: 'window.__ready===true', returnByValue: true });
  if (r.result?.result?.value) break;
  await sleep(200);
}
await sleep(waitMs);
const res = await send('Runtime.evaluate', {
  expression: expr, returnByValue: true, awaitPromise: true
});
console.log(JSON.stringify(res.result, null, 1));
if (pngOut) {
  await sleep(1500);
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  const fs = await import('node:fs');
  fs.writeFileSync(pngOut, Buffer.from(shot.result.data, 'base64'));
  console.log('shot -> ' + pngOut);
}
if (errs.length) console.log('ERRORS:\n' + errs.slice(0, 8).join('\n'));
chrome.kill();
process.exit(0);
