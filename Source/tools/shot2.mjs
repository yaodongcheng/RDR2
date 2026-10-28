// 截图（带 --no-proxy-server，本地服务在代理环境里也能开）
// 用法: node raw/cutscene/_shot2.mjs <url> <out.png> [waitMs] [w] [h]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const [, , url, out, waitMsArg, wArg, hArg] = process.argv;
const waitMs = +(waitMsArg || 3000);
const W = +(wArg || 1600), H = +(hArg || 1000);
const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'shotprof-'));

const PORT = await (async () => {
  for (let p = 9820; p < 9999; p++) {
    const busy = await new Promise(res => {
      const s = net.connect(p, '127.0.0.1');
      s.on('connect', () => { s.destroy(); res(true); });
      s.on('error', () => res(false));
    });
    if (!busy) return p;
  }
  throw new Error('no port');
})();

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`,
  '--no-proxy-server', '--proxy-bypass-list=*',
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--hide-scrollbars', `--window-size=${W},${H}`,
  '--no-sandbox', '--disable-dev-shm-usage', '--autoplay-policy=no-user-gesture-required',
  `--user-data-dir=${prof}`, 'about:blank',
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
async function targets() {
  for (let i = 0; i < 80; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const j = await r.json();
      if (j.length) return j;
    } catch { }
    await sleep(250);
  }
  throw new Error('chrome not up');
}
const pages = await targets();
const page = pages.find(p => p.type === 'page') || pages[0];
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pend = new Map(); const logs = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.method === 'Runtime.exceptionThrown') logs.push('EXC: ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
  if (m.method === 'Runtime.consoleAPICalled') logs.push(m.params.type + ': ' + m.params.args.map(a => a.value ?? a.description ?? '').join(' '));
  if (m.method === 'Network.loadingFailed') logs.push('NETFAIL: ' + m.params.errorText + ' ' + (m.params.type||''));
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
};
const send = (method, params = {}) => { const i = ++id; ws.send(JSON.stringify({ id: i, method, params })); return new Promise(r => pend.set(i, r)); };

await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
const nav = await send('Page.navigate', { url });
await sleep(1200);
const st = await send('Runtime.evaluate', { expression: 'document.title + " | len=" + document.body.innerHTML.length', returnByValue: true });
await sleep(waitMs);
const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
fs.writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
console.log(JSON.stringify({ nav: nav.result, state: st.result?.result?.value, logs: logs.slice(0, 20), out, bytes: fs.statSync(out).size }, null, 1));
ws.close(); chrome.kill(); process.exit(0);
