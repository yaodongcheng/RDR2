// 离线喂给 AVG 用的「2D 背景」截图器（真实 3D 场景 → JPG）
// 与 tools/shot.mjs 同一套 CDP 手法，差别：
//   1) 等的是城镇预览页自己的 __dbg.phase==='done'（不是 window.__ready）
//   2) 直接出 JPEG（1920×1080 的 PNG 每张 3 MB，60+ 张会把仓库撑爆）
//   3) 失败也会写一张「读不到」的报告，不让批处理静默卡死
//
// 用法:
//   node tools/bgshot.mjs <url> <out.jpg> [waitMs=1200] [W=1920] [H=1080] [timeoutS=150]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const [, , url, out, waitMsArg, wArg, hArg, toArg] = process.argv;
const waitMs = +(waitMsArg || 1200);
const W = +(wArg || 1920), H = +(hArg || 1080);
const timeoutS = +(toArg || 150);

const PORT = await (async () => {
  const net = await import('node:net');
  for (let p = 9811; p < 9999; p++) {
    const busy = await new Promise(res => {
      const s = net.connect(p, '127.0.0.1');
      s.on('connect', () => { s.destroy(); res(true); });
      s.on('error', () => res(false));
    });
    if (!busy) return p;
  }
  throw new Error('没有空闲调试端口');
})();

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'bgshot-'));
const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`,
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--hide-scrollbars', `--window-size=${W},${H}`,
  '--no-sandbox', '--disable-dev-shm-usage',
  `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function targets() {
  for (let i = 0; i < 120; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const j = await r.json();
      if (j.length) return j;
    } catch { }
    await sleep(250);
  }
  throw new Error('chrome 没起来');
}

let ws, id = 0; const pend = new Map(); const logs = [];
try {
  const pages = await targets();
  const page = pages.find(p => p.type === 'page') || pages[0];
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.method === 'Runtime.exceptionThrown') {
      logs.push('EXC: ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 160));
    }
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      logs.push('err: ' + m.params.args.map(a => a.value ?? a.description ?? '').join(' ').slice(0, 160));
    }
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  };
  const send = (method, params = {}) => {
    const i = ++id;
    ws.send(JSON.stringify({ id: i, method, params }));
    return new Promise(r => pend.set(i, r));
  };

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url });

  let phase = '?', tris = 0, cam = null, tgt = null;
  const t0 = Date.now();
  while ((Date.now() - t0) / 1000 < timeoutS) {
    const r = await send('Runtime.evaluate', {
      expression: `JSON.stringify(window.__dbg||{})`, returnByValue: true,
    });
    try {
      const d = JSON.parse(r.result?.result?.value || '{}');
      phase = d.phase || '?'; tris = d.tris || 0; cam = d.cam; tgt = d.tgt;
    } catch { }
    if (phase === 'done') break;
    await sleep(400);
  }
  await sleep(waitMs);

  // 定格一帧再截：避免 OrbitControls 阻尼动画在截图瞬间还没收敛
  await send('Runtime.evaluate', { expression: `(()=>{try{window.__controls&&window.__controls.update();window.__renderer&&window.__renderer.render(window.__scene,window.__camera);}catch(e){}})()` });
  await sleep(350);

  const shot = await send('Page.captureScreenshot', { format: 'jpeg', quality: 90, captureBeyondViewport: false });
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
  console.log(JSON.stringify({ ok: phase === 'done', phase, tris, cam, tgt, out, bytes: fs.statSync(out).size, logs: logs.slice(0, 3) }));
} catch (e) {
  console.log(JSON.stringify({ ok: false, error: String(e), out, logs: logs.slice(0, 3) }));
} finally {
  try { ws?.close(); } catch { }
  chrome.kill();
}
process.exit(0);
