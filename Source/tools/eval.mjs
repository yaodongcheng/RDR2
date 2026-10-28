// 在无头 Chrome 里打开页面，等 ready 后执行一段表达式并打印结果
// 用法: node tools/eval.mjs <url> "<expr>" [waitMs]
import { spawn } from 'node:child_process';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const [, , url, expr, waitMsArg] = process.argv;
const waitMs = +(waitMsArg || 8000);
const PORT = 9600 + Math.floor(Math.random() * 200);
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`,
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--no-sandbox',
  '--window-size=1200,800', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let page;
for (let i = 0; i < 60; i++) {
  try {
    const j = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    page = j.find(x => x.type === 'page') || j[0];
    if (page) break;
  } catch { }
  await sleep(250);
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pend = new Map();
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
const send = (method, params = {}) => { const i = ++id; ws.send(JSON.stringify({ id: i, method, params })); return new Promise(r => pend.set(i, r)); };
await send('Page.enable'); await send('Runtime.enable');
await send('Page.navigate', { url });
await sleep(waitMs);
const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
console.log(JSON.stringify(r.result?.result?.value ?? r.result, null, 1));
ws.close(); chrome.kill(); process.exit(0);
