#!/usr/bin/env node
/**
 * Screenshot a page at a TRUE device viewport, and report what the page
 * actually did there.
 *
 * `chrome --headless --window-size=390,844` does NOT give you a 390px
 * viewport: Chrome clamps the window to a 500px minimum, so the page lays
 * out at 500 and the PNG is merely cropped to 390. Every "mobile defect" you
 * find that way is an artifact — measured with a probe page that printed
 * window.innerWidth: requested 390, reported 500, in both old and new
 * headless.
 *
 * So this drives the DevTools Protocol instead and calls
 * Emulation.setDeviceMetricsOverride, which is what actually resizes the
 * layout viewport (and sets mobile:true, so media queries, touch and the
 * meta viewport behave as on a phone).
 *
 * It also returns the two numbers that decide whether a page is responsive:
 * documentElement.scrollWidth vs innerWidth (horizontal overflow), and the
 * list of elements wider than the viewport, which names the culprit instead
 * of leaving you to guess from a picture.
 *
 *   node scripts/device-shot.mjs <url> <out.png> <width> <height> [dpr] [mobile]
 */
import { spawn } from "node:child_process";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [url, out, w = "390", h = "844", dpr = "2", mobile = "1"] = process.argv.slice(2);
if (!url || !out) {
  console.error("usage: device-shot.mjs <url> <out.png> [w] [h] [dpr] [mobile]");
  process.exit(1);
}

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PORT = 9333 + (process.pid % 500);
const profile = mkdtempSync(join(tmpdir(), "ri-cdp-"));

const chrome = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
  "--no-first-run", "--no-default-browser-check",
  `--user-data-dir=${profile}`, `--remote-debugging-port=${PORT}`,
  "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function endpoint() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      return (await r.json()).webSocketDebuggerUrl;
    } catch { await sleep(250); }
  }
  throw new Error("chrome did not expose a debugging endpoint");
}

let id = 0;
function rpc(ws, method, params = {}, sessionId) {
  return new Promise((resolve, reject) => {
    const msgId = ++id;
    const onMsg = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id !== msgId) return;
      ws.removeEventListener("message", onMsg);
      m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve(m.result);
    };
    ws.addEventListener("message", onMsg);
    ws.send(JSON.stringify({ id: msgId, method, params, sessionId }));
  });
}

try {
  const wsUrl = await endpoint();
  const ws = new WebSocket(wsUrl);
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));

  const { targetId } = await rpc(ws, "Target.createTarget", { url: "about:blank" });
  const { sessionId } = await rpc(ws, "Target.attachToTarget", { targetId, flatten: true });
  const S = (m, p) => rpc(ws, m, p, sessionId);

  await S("Page.enable");
  // THE call that headless --window-size cannot do: a real layout viewport.
  await S("Emulation.setDeviceMetricsOverride", {
    width: Number(w), height: Number(h),
    deviceScaleFactor: Number(dpr), mobile: mobile === "1",
  });
  if (mobile === "1") {
    await S("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });
  }

  await S("Page.navigate", { url });
  await new Promise((resolve) => {
    const done = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.method === "Page.loadEventFired" && m.sessionId === sessionId) {
        ws.removeEventListener("message", done);
        resolve();
      }
    };
    ws.addEventListener("message", done);
    setTimeout(resolve, 15000);
  });
  await sleep(1200);   // fonts + hydration

  // What the page DID at this size — the part a screenshot cannot tell you.
  const probe = await S("Runtime.evaluate", {
    returnByValue: true,
    expression: `(() => {
      const d = document.documentElement;
      const over = [];
      for (const el of document.querySelectorAll("body *")) {
        const r = el.getBoundingClientRect();
        if (r.width > d.clientWidth + 1 || r.right > d.clientWidth + 1) {
          over.push({
            tag: el.tagName.toLowerCase(),
            cls: (el.className && el.className.baseVal !== undefined
                   ? el.className.baseVal : String(el.className || "")).slice(0, 60),
            w: Math.round(r.width), right: Math.round(r.right),
          });
        }
      }
      // report only the OUTERMOST offenders — a wide table inside a scroll
      // container reports the container, not fifty cells
      const seen = new Set();
      const top = over.filter((o) => {
        const k = o.tag + "." + o.cls;
        if (seen.has(k)) return false;
        seen.add(k); return true;
      }).slice(0, 8);
      return {
        innerWidth: window.innerWidth,
        scrollWidth: d.scrollWidth,
        clientWidth: d.clientWidth,
        overflow: d.scrollWidth - d.clientWidth,
        offenders: top,
        title: document.title,
      };
    })()`,
  });

  const shot = await S("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  writeFileSync(out, Buffer.from(shot.data, "base64"));
  console.log(JSON.stringify(probe.result.value, null, 1));
  ws.close();
} finally {
  chrome.kill("SIGKILL");
}
