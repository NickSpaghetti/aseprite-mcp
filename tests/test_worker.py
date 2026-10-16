"""The long-lived Aseprite worker (core/worker.py, lua/worker.lua)."""
import asyncio
import os
import signal
import subprocess
import time

import pytest
from conftest import fails, ok, run

from aseprite_mcp.core import commands
from aseprite_mcp.core.errors import AsepriteError
from aseprite_mcp.tools import canvas, script

BUSY_2S = 'local t = os.clock() while os.clock() - t < 2 do end print("done")'


def _aseprite_pids():
    found = []
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            argv0 = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")[0]
        except OSError:
            continue
        if os.path.basename(argv0) == b"aseprite":
            found.append(int(pid))
    return found


def _layer_names(path):
    out = run(commands.run_script(
        'for _, l in ipairs(app.activeSprite.layers) do print("LAYER:" .. l.name) end', path))
    return [line[len("LAYER:"):] for line in out.splitlines() if line.startswith("LAYER:")]


def test_timeout_parsing_rejects_bad_values():
    assert commands._parse_timeout("2.5") == 2.5
    for bad in ("0", "-1", "soon"):
        with pytest.raises(ValueError, match="ASEPRITE_TIMEOUT"):
            commands._parse_timeout(bad)


def test_one_process_serves_many_calls(sprite):
    ok(run(script.run_lua_script('print("warm")')))
    pid = commands.worker.pid
    for _ in range(5):
        ok(run(script.run_lua_script('print(app.activeSprite.width)', sprite)))
    assert commands.worker.pid == pid
    assert _aseprite_pids() == [pid]


def test_runaway_script_is_killed_and_the_next_call_recovers(monkeypatch):
    monkeypatch.setattr(commands.worker, "timeout", 2)
    start = time.monotonic()
    fails(script.run_lua_script("while true do end"), AsepriteError, "did not finish within 2s")
    assert time.monotonic() - start < 10
    assert _aseprite_pids() == [], "the timed-out Aseprite is still running"
    assert ok(run(script.run_lua_script('print("back")'))).strip() == "back"


def test_worker_restarts_after_a_crash():
    ok(run(script.run_lua_script('print("up")')))
    os.kill(commands.worker.pid, signal.SIGKILL)
    time.sleep(0.2)
    assert ok(run(script.run_lua_script('print("up again")'))).strip() == "up again"


def test_requests_do_not_share_globals_or_sprites(sprite):
    ok(run(script.run_lua_script('leaked = 42', sprite)))
    out = ok(run(script.run_lua_script('print(tostring(leaked), tostring(app.activeSprite), #app.sprites)')))
    assert out.strip() == "nil\tnil\t0"


def test_each_request_reads_the_file_from_disk(base_dir):
    path = f"{base_dir}/worker_fresh.aseprite"
    ok(run(canvas.create_canvas(8, 8, path)))
    assert _layer_names(path) == ["Layer 1"]
    # Change the file behind the worker's back with a separate Aseprite.
    edit = f"{base_dir}/worker_fresh_edit.lua"
    open(edit, "w").write('local s = app.activeSprite s:newLayer().name = "outside" s:saveAs(s.filename)')
    subprocess.run([commands.ASEPRITE_PATH, "--batch", path, "--script", edit], check=True, capture_output=True)
    assert _layer_names(path) == ["Layer 1", "outside"]


def test_event_loop_keeps_running_during_a_call():
    async def main():
        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                ticks += 1
                await asyncio.sleep(0.05)

        task = asyncio.create_task(ticker())
        await asyncio.sleep(0)
        await script.run_lua_script(BUSY_2S)
        task.cancel()
        return ticks

    # ~40 ticks fit in 2s; a blocking call allows none.
    assert run(main()) >= 20


def test_concurrent_edits_to_one_file_all_land(base_dir):
    path = f"{base_dir}/worker_concurrent.aseprite"
    ok(run(canvas.create_canvas(8, 8, path)))

    async def main():
        await asyncio.gather(*(canvas.add_layer(path, f"layer{i}") for i in range(20)))

    run(main())
    names = _layer_names(path)
    assert len(names) == 21, names
    assert {f"layer{i}" for i in range(20)} <= set(names)
