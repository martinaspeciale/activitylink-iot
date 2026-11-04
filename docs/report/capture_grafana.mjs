// Capture the real Grafana dashboard for a preserved run
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';

const root = path.resolve(import.meta.dirname, '../..');
const [summaryPath, output] = process.argv.slice(2);
if (!summaryPath || !output) {
  throw new Error('Usage: node docs/report/capture_grafana.mjs RUN_SUMMARY OUTPUT_PNG');
}
if (fs.existsSync(output)) {
  throw new Error('Choose a new screenshot output path');
}
const run = JSON.parse(fs.readFileSync(summaryPath, 'utf8'));
const credentials = JSON.parse(fs.readFileSync(path.join(root, 'runtime/native-stack/credentials.json')));
const login = await fetch('http://127.0.0.1:3000/login', {
  method: 'POST',
  headers: {'content-type': 'application/json'},
  body: JSON.stringify({user: 'admin', password: credentials.grafana_admin})
});
if (!login.ok) {
  throw new Error(`Grafana login failed: ${login.status}`);
}
const cookies = login.headers.getSetCookie().map(cookie => {
  const pair = cookie.split(';')[0];
  const split = pair.indexOf('=');
  return {
    name: pair.slice(0, split),
    value: pair.slice(split + 1),
    domain: '127.0.0.1',
    path: '/'
  };
});
const profile = fs.mkdtempSync(path.join(root, 'runtime/native-stack/report-grafana-'));
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new',
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  `--user-data-dir=${profile}`,
  '--remote-debugging-port=0',
  '--remote-debugging-address=127.0.0.1',
  'about:blank'
], {stdio: 'ignore'});
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
let socket;
try {
  const active = path.join(profile, 'DevToolsActivePort');
  for (let attempt = 0; !fs.existsSync(active); attempt++) {
    if (attempt > 100 || chrome.exitCode !== null) {
      throw new Error('Chrome startup failed');
    }
    await pause(200);
  }
  const port = fs.readFileSync(active, 'utf8').split('\n')[0];
  const tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
  socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = reject;
  });
  let sequence = 0;
  const pending = new Map();
  socket.onmessage = ({data}) => {
    const response = JSON.parse(data);
    if (!pending.has(response.id)) {
      return;
    }
    const {resolve, reject, timeout} = pending.get(response.id);
    pending.delete(response.id);
    clearTimeout(timeout);
    if (response.error) {
      reject(new Error(JSON.stringify(response.error)));
    } else {
      resolve(response.result);
    }
  };
  function call(method, params = {}) {
    const id = ++sequence;
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`Browser timeout: ${method}`));
      }, 30000);
      pending.set(id, {resolve, reject, timeout});
      socket.send(JSON.stringify({id, method, params}));
    });
  }
  await call('Network.enable');
  await call('Network.setCookies', {cookies});
  await call('Emulation.setDeviceMetricsOverride', {
    width: 1000,
    height: 740,
    deviceScaleFactor: 2,
    mobile: false
  });
  await call('Page.enable');
  const query = new URLSearchParams({
    from: String(Math.floor((run.start - 1) * 1000)),
    to: String(Math.ceil((run.end + 1) * 1000)),
    'var-run_id': run.run_id,
    kiosk: '1',
    theme: 'light'
  });
  const url = `http://127.0.0.1:3000/d/activitylink?${query}`;
  await call('Page.navigate', {url});
  let body = '';
  for (let attempt = 0; attempt < 40; attempt++) {
    await pause(500);
    const result = await call('Runtime.evaluate', {
      expression: 'document.body.innerText',
      returnByValue: true
    });
    body = result.result.value;
    if (body.includes('Invalid, out of order and dropped')) {
      break;
    }
  }
  await pause(4000);
  const result = await call('Runtime.evaluate', {
    expression: 'document.body.innerText',
    returnByValue: true
  });
  body = result.result.value;
  if (!body.includes('Node failures') || body.includes('No data') || body.includes('Sign in')) {
    throw new Error('Grafana did not render the expected run');
  }

  // Capture only the two upper panels; plotted values and labels are not edited
  const screenshot = await call('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false,
    clip: {x: 0, y: 0, width: 1000, height: 364, scale: 1}
  });
  fs.writeFileSync(output, Buffer.from(screenshot.data, 'base64'), {flag: 'wx'});
  const provenance = {
    captured_at: new Date().toISOString(),
    run_id: run.run_id,
    recorded_start: run.start,
    recorded_end: run.end,
    source_summary: path.relative(root, path.resolve(summaryPath)),
    dashboard_url: url,
    theme: 'Grafana native light theme',
    view: 'top row: stale flags and commanded/reported LEDs',
    image_values_edited: false,
    scope: 'new browser screenshot of preserved hardware measurements; no new experiment'
  };
  fs.writeFileSync(output + '.json', JSON.stringify(provenance, null, 2) + '\n', {flag: 'wx'});
  console.log(`Saved real Grafana view: ${output}`);
} finally {
  socket?.close();
  chrome.kill('SIGTERM');
}
