// 用 CDP 给本地网页截图（支持等待 window.__ready / 自定义等待）
// 用法: node tools/shot.mjs <url> <out.png> [waitMs] [width] [height]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// 每次都用独立的临时 profile：否则多次调用会连到上一次没退干净的 headless 实例，
// 页面停在 about:blank（截图全白、什么都不报）。
function __dirnameTmp(){
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'shotprof-'));
  return d;
}

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const [, , url, out, waitMsArg, wArg, hArg] = process.argv;
const waitMs = +(waitMsArg || 2500);
const W = +(wArg || 1600), H = +(hArg || 900);
// 端口要真空闲：多次调用留下的 headless 实例会占着固定/随机端口，
// 连上去看到的是上一次的 about:blank（截图全白，且不报任何错）。
const PORT = await (async () => {
  const net = await import('node:net');
  for (let p = 9411; p < 9800; p++) {
    const busy = await new Promise(res => {
      const s = net.connect(p, '127.0.0.1');
      s.on('connect', () => { s.destroy(); res(true); });
      s.on('error', () => res(false));
    });
    if (!busy) return p;
  }
  throw new Error('没有空闲调试端口');
})();

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`,
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--hide-scrollbars', `--window-size=${W},${H}`,
  '--no-sandbox', '--disable-dev-shm-usage',
  `--user-data-dir=${(__dirnameTmp())}`, 'about:blank',
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
const logs = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.method === 'Runtime.exceptionThrown') {
    const d = m.params.exceptionDetails;
    logs.push('EXC: ' + (d.exception?.description || d.text));
  }
  if (m.method === 'Runtime.consoleAPICalled' && (m.params.type === 'error' || m.params.type === 'warning')) {
    logs.push(m.params.type + ': ' + m.params.args.map(a => a.value ?? a.description ?? '').join(' '));
  }
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
};
function send(method, params = {}) {
  const i = ++id;
  ws.send(JSON.stringify({ id: i, method, params }));
  return new Promise(r => pend.set(i, r));
}

await send('Page.enable');
await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url });
await sleep(600);

// 等 __ready（最多 20 s）
let ready = false;
for (let i = 0; i < 100; i++) {
  const r = await send('Runtime.evaluate', { expression: 'window.__ready===true', returnByValue: true });
  if (r.result?.result?.value) { ready = true; break; }
  await sleep(200);
}
await sleep(waitMs);
const clickSel = process.argv[7];
if (clickSel) {
  await send('Runtime.evaluate', { expression: `document.querySelector(${JSON.stringify(clickSel)})?.click()` });
  await sleep(+(process.argv[8] || 3000));
}

const err = await send('Runtime.evaluate', {
  expression: `JSON.stringify(window.__dbg||{}) + ' TOWN=' + JSON.stringify(window.__town||{}) + ' | ' + (document.querySelector('#toast')?.textContent||'')`,
  returnByValue: true,
});
const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
fs.writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
console.log(JSON.stringify({ ready, info: err.result?.result?.value, logs: logs.slice(0, 8), out, bytes: fs.statSync(out).size }, null, 1));

ws.close();
chrome.kill();
process.exit(0);
