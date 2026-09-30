#!/usr/bin/env python3
"""Small, mobile-friendly web pendant for the paint robot.

Run from the repository root, then open the printed URL on a phone connected
to the same trusted LAN. Each button tap performs one configured Cartesian
step. Authentication is disabled by default; pass ``--token`` to enable it.
"""

from __future__ import annotations

import argparse
import atexit
import secrets
from pathlib import Path
import sys

from flask import Flask, jsonify, render_template_string, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.applications.base.robot_jog_service import RobotJogService
from src.robot_systems.paint.bootstrap_provider import PaintBootstrapProvider


LINEAR_AXES = {"X", "Y", "Z"}
ROTARY_AXES = {"RX", "RY", "RZ"}
LINEAR_STEPS = (0.1, 0.2, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 250.0)
ROTARY_STEPS = (0.1, 0.2, 0.5, 1.0, 5.0, 10.0, 45.0, 90.0, 180.0, 360.0)

PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>Paint Robot Jog</title>
  <style>
    :root { color-scheme: dark; --accent:#a975c1; --stop:#c62828; --panel:#20242b; }
    * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
    body { margin:0; background:#111419; color:#f4f5f6; font:16px system-ui,sans-serif; touch-action:manipulation; }
    main { width:min(720px,100%); margin:auto; padding:16px; }
    h1 { margin:0 0 12px; font-size:1.4rem; }
    .status,.controls,.axis { background:var(--panel); border-radius:14px; padding:14px; margin-bottom:12px; }
    .status { display:flex; justify-content:space-between; gap:10px; }
    #state.ok { color:#75d47f; } #state.bad { color:#ff7770; }
    label { display:grid; gap:6px; }
    input[type=range] { width:100%; min-height:44px; accent-color:var(--accent); }
    .axis { display:grid; grid-template-columns:1fr 62px 1fr; align-items:center; gap:10px; }
    .axis span { text-align:center; font-weight:700; }
    button { min-height:64px; border:0; border-radius:12px; color:white; background:var(--accent); font-size:1.35rem; font-weight:800; user-select:none; }
    button.active { filter:brightness(1.35); transform:scale(.98); }
    button:disabled { opacity:.45; }
    #stop { width:100%; background:var(--stop); min-height:72px; margin-top:2px; }
    #pose { margin-top:8px; color:#bbc0c8; font:0.86rem ui-monospace,monospace; overflow-wrap:anywhere; }
    .hint { color:#bbc0c8; font-size:.88rem; line-height:1.35; }
  </style>
</head>
<body><main>
  <h1>Paint Robot Jog</h1>
  <section class="status"><span>Robot</span><strong id="state">Checking…</strong></section>
  <section class="controls">
    <label>Linear step: <b><span id="linearValue">1</span> mm</b>
      <input id="linear" type="range" min="0" max="8" step="1" value="3">
    </label>
    <label>Rotation step: <b><span id="rotaryValue">1</span>°</b>
      <input id="rotary" type="range" min="0" max="9" step="1" value="3">
    </label>
    <div id="pose">Pose: —</div>
  </section>
  <div id="axes"></div>
  <button id="stop">STOP MOTION</button>
  <p class="hint">Each tap performs one step. Wait for the move to finish before tapping again. Keep the physical emergency stop within reach.</p>
</main>
<script>
const token = new URLSearchParams(location.search).get('token') || '';
const headers = {'Content-Type':'application/json', 'X-Jog-Token':token};
const axes = ['X','Y','Z','RX','RY','RZ'];
const linearSteps = [0.1,0.2,0.5,1,5,10,50,100,250];
const rotarySteps = [0.1,0.2,0.5,1,5,10,45,90,180,360];
const axesRoot = document.querySelector('#axes');
let moving = false;

for (const axis of axes) {
  const row = document.createElement('section'); row.className = 'axis';
  row.innerHTML = `<button data-axis="${axis}" data-direction="MINUS">−</button><span>${axis}</span><button data-axis="${axis}" data-direction="PLUS">+</button>`;
  axesRoot.append(row);
}
for (const id of ['linear','rotary']) {
  const slider=document.querySelector('#'+id), output=document.querySelector('#'+id+'Value');
  const values=id==='linear'?linearSteps:rotarySteps;
  slider.addEventListener('input',()=>output.textContent=values[Number(slider.value)]);
}
async function api(path, body={}) {
  const response = await fetch(path,{method:'POST',headers,body:JSON.stringify(body),cache:'no-store'});
  if (!response.ok) throw new Error((await response.json().catch(()=>({}))).error || response.statusText);
  return response.json();
}
function setMoving(value, button=null) {
  moving=value;
  document.querySelectorAll('[data-axis]').forEach(item=>item.disabled=value);
  button?.classList.toggle('active', value);
}
async function step(button) {
  if (moving) return;
  const axis=button.dataset.axis;
  const isLinear=axes.slice(0,3).includes(axis);
  const slider=document.querySelector(isLinear?'#linear':'#rotary');
  const amount=(isLinear?linearSteps:rotarySteps)[Number(slider.value)];
  setMoving(true, button);
  try {
    await api('/api/jog/step',{axis,direction:button.dataset.direction,step:amount});
  } catch (error) { showError(error); }
  finally { setMoving(false, button); updateState(); }
}
async function stop() {
  try { await api('/api/jog/stop'); } catch (error) { showError(error); }
  setMoving(false);
}
function showError(error) { const s=document.querySelector('#state'); s.textContent=error.message; s.className='bad'; }
document.querySelectorAll('[data-axis]').forEach(button=>{
  button.addEventListener('click',()=>step(button));
  button.addEventListener('contextmenu',event=>event.preventDefault());
});
document.querySelector('#stop').addEventListener('click',stop);
window.addEventListener('pagehide',()=>navigator.sendBeacon('/api/jog/stop?token='+encodeURIComponent(token)));
async function updateState() {
  try {
    const r=await fetch('/api/state',{headers:{'X-Jog-Token':token},cache:'no-store'}), data=await r.json();
    if(!r.ok) throw new Error(data.error||r.statusText);
    const s=document.querySelector('#state'); s.textContent=data.connected?'Connected':'Unavailable'; s.className=data.connected?'ok':'bad';
    document.querySelector('#pose').textContent='Pose: '+(data.position?.map(v=>Number(v).toFixed(2)).join(', ')||'—');
  } catch(error) { showError(error); }
}
updateState(); setInterval(updateState,1000);
</script></body></html>"""


class JogRuntime:
    def __init__(self, server_url: str, tool: int, user: int) -> None:
        provider = PaintBootstrapProvider()
        robot = provider.build_robot() if server_url == "http://localhost:5000" else None
        if robot is None:
            from src.engine.robot.drivers.ros2_robot import Ros2Robot
            robot = Ros2Robot(server_url=server_url)
        self.robot = robot
        self.jog = RobotJogService(
            robot_service=robot,
            tool_getter=lambda: tool,
            user_getter=lambda: user,
        )

    def step(self, axis: str, direction: str, amount: float) -> None:
        self.jog.jog("JOG_ROBOT", axis, direction, amount)

    def stop(self) -> None:
        self.jog.stop_jog()


def create_app(runtime: JogRuntime, token: str | None = None) -> Flask:
    app = Flask(__name__)

    def authorized() -> bool:
        if not token:
            return True
        supplied = request.headers.get("X-Jog-Token") or request.args.get("token", "")
        return secrets.compare_digest(supplied, token)

    @app.before_request
    def require_token():
        if not authorized():
            return jsonify(error="Invalid or missing jog token"), 401
        return None

    @app.get("/")
    def index():
        return render_template_string(PAGE)

    @app.get("/api/state")
    def state():
        try:
            position = runtime.robot.get_current_position()
            return jsonify(connected=bool(position), position=position)
        except Exception as exc:
            return jsonify(connected=False, position=[], error=str(exc)), 503

    @app.post("/api/jog/step")
    def step_jog():
        data = request.get_json(silent=True) or {}
        axis = str(data.get("axis", "")).upper()
        direction = str(data.get("direction", "")).upper()
        try:
            amount = float(data.get("step"))
        except (TypeError, ValueError):
            return jsonify(error="Step must be numeric"), 400
        if axis not in LINEAR_AXES | ROTARY_AXES or direction not in {"PLUS", "MINUS"}:
            return jsonify(error="Invalid axis or direction"), 400
        allowed_steps = LINEAR_STEPS if axis in LINEAR_AXES else ROTARY_STEPS
        if amount not in allowed_steps:
            return jsonify(error="Invalid step size"), 400
        runtime.step(axis, direction, amount)
        return jsonify(ok=True)

    @app.post("/api/jog/stop")
    def stop_jog():
        runtime.stop()
        return jsonify(ok=True)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--robot-url", default="http://localhost:5000")
    parser.add_argument("--tool", type=int, default=0)
    parser.add_argument("--user", type=int, default=0)
    parser.add_argument(
        "--token",
        default=None,
        help="optional access token; authentication is disabled when omitted",
    )
    args = parser.parse_args()

    runtime = JogRuntime(args.robot_url, args.tool, args.user)
    atexit.register(runtime.stop)
    if args.token:
        url = f"http://<robot-pc-ip>:{args.port}/?token={args.token}"
        print(f"Open {url}", flush=True)
    else:
        print(
            f"WARNING: authentication disabled; open http://<robot-pc-ip>:{args.port}/",
            flush=True,
        )
    create_app(runtime, args.token).run(
        host=args.host,
        port=args.port,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
