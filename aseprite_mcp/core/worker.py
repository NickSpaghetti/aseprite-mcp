"""The one long-lived Aseprite this server talks to.

Aseprite is single-threaded and every request may rewrite a file, so requests
run one at a time through a single process. That ordering is also what keeps
concurrent tool calls on the same file from losing each other's writes.

The process runs lua/worker.lua, which reads JSON requests on stdin and answers
with framed JSON replies on stdout. On start it is sent lua/lib.lua and every
lua/ops/*.lua file, which register the ops that tools call by name. A request
that runs past the timeout gets the process killed; the next request starts a
fresh one. A crash is handled the same way.
"""

import collections
import json
import os
import queue
import subprocess
import tempfile
import threading
from pathlib import Path

from .errors import AsepriteError

FRAME = "\x1eASEMCP "
_LUA_DIR = Path(__file__).resolve().parent.parent / "lua"
_EOF = None


class AsepriteWorker:
    def __init__(self, executable: str, timeout: float):
        self.executable = executable
        self.timeout = timeout
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._lines: queue.Queue = queue.Queue()
        self._stderr: collections.deque = collections.deque(maxlen=50)
        self._script_path: str | None = None
        self._next_id = 0

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc and self._proc.poll() is None else None

    def run_op(self, op: str, args: dict, filename: str | None = None):
        """Run a registered op on `filename` and return its result (decoded JSON, or None)."""
        request = {"op": op, "args": {k: v for k, v in args.items() if v is not None}}
        if filename:
            request["file"] = filename
        with self._lock:
            reply, _ = self._request(request)
        return reply.get("result")

    def run_script(self, code: str, filename: str | None = None) -> str:
        """Run a Lua chunk with `filename` open as the active sprite; return what it printed."""
        request = {"code": code}
        if filename:
            request["file"] = filename
        with self._lock:
            reply, stray = self._request(request)
        return "\n".join(filter(None, [reply.get("output", ""), *stray]))

    def run_cli(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run a separate `aseprite <args>` process, in turn with the worker's requests."""
        with self._lock:
            try:
                return subprocess.run([self.executable, *args], capture_output=True, text=True,
                                      encoding="utf-8", timeout=self.timeout)
            except subprocess.TimeoutExpired:
                raise AsepriteError(f"Aseprite did not finish within {self.timeout:g}s and was killed") from None

    def close(self) -> None:
        with self._lock:
            self._stop()

    def _request(self, request: dict) -> tuple[dict, list[str]]:
        # Caller holds self._lock.
        if self._proc is None or self._proc.poll() is not None:
            self._start()
        return self._send(request)

    def _send(self, request: dict) -> tuple[dict, list[str]]:
        self._next_id += 1
        request = {"id": self._next_id, **request}
        try:
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()
        except OSError:
            raise self._died() from None
        reply, stray = self._read_reply()
        if reply.get("id") != request["id"]:
            raise AsepriteError(f"Aseprite worker answered request {reply.get('id')} instead of {request['id']}")
        if not reply.get("ok"):
            error = reply.get("error") or {}
            raise AsepriteError(error.get("message") or error.get("code") or "Aseprite reported a failure",
                                code=error.get("code"))
        return reply, stray

    def _read_reply(self) -> tuple[dict, list[str]]:
        stray = []
        while True:
            try:
                line = self._lines.get(timeout=self.timeout)
            except queue.Empty:
                self._stop()
                raise AsepriteError(f"Aseprite did not finish within {self.timeout:g}s and was killed") from None
            if line is _EOF:
                raise self._died()
            if line.startswith(FRAME):
                return json.loads(line[len(FRAME):]), stray
            stray.append(line.rstrip("\n"))

    def _died(self) -> AsepriteError:
        detail = "\n".join(self._stderr).strip()
        self._stop()
        return AsepriteError("Aseprite worker exited unexpectedly" + (f": {detail}" if detail else ""))

    def _start(self) -> None:
        self._stop()
        # Written to the temp dir rather than run from the package, so a wrapper
        # that runs Aseprite in a container (it mounts the temp dir) can read it.
        fd, self._script_path = tempfile.mkstemp(prefix="aseprite-mcp-worker-", suffix=".lua")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write((_LUA_DIR / "worker.lua").read_text(encoding="utf-8"))
        self._proc = subprocess.Popen(
            [self.executable, "--batch", "--script", self._script_path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        self._lines = queue.Queue()
        self._stderr.clear()
        threading.Thread(target=self._pump_stdout, args=(self._proc, self._lines), daemon=True).start()
        threading.Thread(target=self._pump_stderr, args=(self._proc,), daemon=True).start()
        # The op files go over stdin rather than by path, for the same reason.
        chunks = [_LUA_DIR / "lib.lua", *sorted((_LUA_DIR / "ops").glob("*.lua"))]
        load = [{"name": path.relative_to(_LUA_DIR).as_posix(), "code": path.read_text(encoding="utf-8")}
                for path in chunks]
        try:
            self._send({"load": load})
        except AsepriteError:
            self._stop()
            raise

    def _stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None:
            if proc.poll() is None:
                # terminate first: a wrapper like `docker run` forwards SIGTERM
                # to the container, but cannot forward SIGKILL.
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    stream.close()
                except OSError:
                    pass
        if self._script_path:
            try:
                os.remove(self._script_path)
            except OSError:
                pass
            self._script_path = None

    @staticmethod
    def _pump_stdout(proc: subprocess.Popen, lines: queue.Queue) -> None:
        try:
            for line in proc.stdout:
                lines.put(line)
        except (OSError, ValueError):
            pass
        lines.put(_EOF)

    def _pump_stderr(self, proc: subprocess.Popen) -> None:
        try:
            for line in proc.stderr:
                self._stderr.append(line.rstrip("\n"))
        except (OSError, ValueError):
            pass
