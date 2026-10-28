// 验收：据点预览页的"建筑拾取"（悬浮读建筑 / 空地读坐标 / 点击锁定）
// 用法: node tools/verify_preview_pick.mjs <url> <out.png> [maxWaitMs] [w] [h]
// 输出 JSON：拾取条数、命中的建筑信息、空地坐标、提示文案、截图路径
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const [, , url, out, maxWaitArg, wArg, hArg] = process.argv;
const MAXWAIT = +(maxWaitArg || 120000);
const W = +(wArg || 1600), H = +(hArg || 900);

const PORT = await (async () => {
  const net = await import('node:net');
  for (let p = 9501; p < 9900; p++) {
    const busy = await new Promise(res => {
      const s = net.connect(p, '127.0.0.1');
      s.on('connect', () => { s.destroy(); res(true); });
      s.on('error', () => res(false));
    });
    if (!busy) return p;
  }
  throw new Error('没有空闲调试端口');
})();

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'pickprof-'));
const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`,
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--hide-scrollbars', `--window-size=${W},${H}`,
  '--no-sandbox', '--disable-dev-shm-usage', '--js-flags=--max-old-space-size=8192',
  `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));

let ws, id = 0; const pend = new Map(); const logs = [];
const out_ = { url, pick: null };

try {
  let page = null;
  for (let i = 0; i < 80 && !page; i++) {
    try { page = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(p => p.type === 'page'); } catch { }
    if (!page) await sleep(250);
  }
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.method === 'Runtime.exceptionThrown')
      logs.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 220));
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error')
      logs.push('ERR ' + m.params.args.map(a => a.value ?? a.description ?? '').join(' ').slice(0, 220));
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  };
  const send = (method, params = {}) => {
    const i = ++id;
    ws.send(JSON.stringify({ id: i, method, params }));
    return new Promise(r => pend.set(i, r));
  };
  const evalJs = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result?.exceptionDetails) logs.push('EVAL ' + JSON.stringify(r.result.exceptionDetails).slice(0, 240));
    return r.result?.result?.value;
  };

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url });

  // 等 tile 流式加载完（__dbg.phase === 'done'），或等到超过 maxWait 但已经能拾取
  const t0 = Date.now();
  let phase = null, count = 0;
  while (Date.now() - t0 < MAXWAIT) {
    const st = await evalJs(`({p:(window.__dbg||{}).phase||'', c:(window.__pick||{}).count||0, l:(window.__dbg||{}).loaded||0, t:(window.__dbg||{}).tris||0})`);
    if (st) { phase = st.p; count = st.c; }
    if (phase === 'done' && count > 0) break;
    await sleep(1500);
  }
  out_.waitedMs = Date.now() - t0;
  out_.phase = phase;
  out_.pickCount = count;

  await sleep(1200);
  const center = await evalJs(`(()=>{const c=window.__pickApi.center(); if(!c) return null;
    return {x:c.x,y:c.y,name:c.info.name,world:c.info.world,yaw:c.info.yaw,scale:c.info.scale,size:c.info.size,tris:c.info.tris,tile:c.info.tile};})()`);
  out_.centerHit = center;

  if (center) {
    out_.hoverText = await evalJs(`window.__pickApi.hover(${center.x},${center.y})`);
    out_.clicked = await evalJs(`window.__pickApi.click(${center.x},${center.y})`);
    out_.hoverBoxVisible = await evalJs(`(()=>{const s=window.__scene;
      let n=0; s.traverse(o=>{ if(o.isLineSegments && o.visible) n++; }); return n;})()`);
    // 再在屏幕角落找一个纯空地，验证"空白处也给坐标"
    out_.emptyHit = await evalJs(`(()=>{const el=document.querySelector('canvas').getBoundingClientRect();
      for (const [fx,fy] of [[0.86,0.88],[0.9,0.2],[0.12,0.9],[0.95,0.5]]) {
        const x=el.left+el.width*fx, y=el.top+el.height*fy;
        if (!window.__pickApi.at(x,y)) return {x,y,empty:window.__pickApi.empty(x,y),text:window.__pickApi.hover(x,y)};
      } return null;})()`);
    await sleep(300);
  }

  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  if (shot.result?.data) {
    fs.writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
    out_.out = out; out_.bytes = fs.statSync(out).size;
  }
  out_.logs = logs.slice(0, 10);
  console.log(JSON.stringify(out_, null, 1));
} catch (e) {
  console.log(JSON.stringify({ error: String(e), logs }, null, 1));
} finally {
  try { ws?.close(); } catch { }
  chrome.kill();
}
process.exit(0);
