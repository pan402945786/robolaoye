"""Render the local 3D scene to PNG and optional MP4; no AI image API is used.

Chrome/Edge is required. Video requires ffmpeg or imageio_ffmpeg. Three.js
r180 is downloaded on first run. Motion is keyframed, not physics simulated.
"""
import argparse
import base64
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PINNED_THREE = "0.180.0"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def vendor_three():
    destination = HERE / "vendor"
    wanted = {"package/build/three.module.js": "three.module.js",
              "package/build/three.core.js": "three.core.js", "package/LICENSE": "LICENSE"}
    if all((destination / name).is_file() for name in wanted.values()):
        return
    print(f"Downloading pinned Three.js {PINNED_THREE} ...", flush=True)
    with urllib.request.urlopen(f"https://registry.npmjs.org/three/-/three-{PINNED_THREE}.tgz", timeout=90) as response:
        payload = response.read()
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member, name in wanted.items():
            handle = archive.extractfile(member)
            if handle is None:
                raise RuntimeError(f"Missing vendor file: {member}")
            (destination / name).write_bytes(handle.read())
    (destination / "version.txt").write_text(f"three@{PINNED_THREE}\n", encoding="utf-8")


class WebSocket:
    """Standard-library websocket client for local Chrome DevTools."""
    def __init__(self, url):
        parsed = urllib.parse.urlsplit(url)
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=60)
        self.buffer = b""
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f"GET {parsed.path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n"
                   f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                   "Sec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode())
        header = b""
        while b"\r\n\r\n" not in header:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("DevTools closed during handshake")
            header += chunk
        head, self.buffer = header.split(b"\r\n\r\n", 1)
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if b" 101 " not in head.split(b"\r\n")[0] or expected.lower() not in head.lower():
            raise ConnectionError("Invalid local DevTools websocket handshake")

    def read(self, count):
        while len(self.buffer) < count:
            data = self.sock.recv(max(4096, count - len(self.buffer)))
            if not data:
                raise ConnectionError("DevTools websocket closed")
            self.buffer += data
        data, self.buffer = self.buffer[:count], self.buffer[count:]
        return data

    def send(self, data, opcode=1):
        if isinstance(data, str):
            data = data.encode()
        length = len(data)
        head = bytes([0x80 | opcode])
        if length < 126:
            head += bytes([0x80 | length])
        elif length < 65536:
            head += bytes([0x80 | 126]) + struct.pack("!H", length)
        else:
            head += bytes([0x80 | 127]) + struct.pack("!Q", length)
        mask = os.urandom(4)
        self.sock.sendall(head + mask + bytes(v ^ mask[i % 4] for i, v in enumerate(data)))

    def receive(self):
        fragments = []
        while True:
            first, second = self.read(2)
            length = second & 127
            if length == 126:
                length = struct.unpack("!H", self.read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.read(8))[0]
            mask = self.read(4) if second & 0x80 else None
            payload = self.read(length)
            if mask:
                payload = bytes(v ^ mask[i % 4] for i, v in enumerate(payload))
            opcode = first & 15
            if opcode == 8:
                raise ConnectionError("DevTools sent a close frame")
            if opcode == 9:
                self.send(payload, 10)
                continue
            if opcode == 10:
                continue
            fragments.append(payload)
            if first & 0x80:
                return json.loads(b"".join(fragments))


class CDP:
    def __init__(self, url):
        self.ws, self.counter, self.errors = WebSocket(url), 0, []

    def call(self, method, params=None):
        self.counter += 1
        self.ws.send(json.dumps({"id": self.counter, "method": method, "params": params or {}}))
        while True:
            response = self.ws.receive()
            if response.get("method") == "Runtime.exceptionThrown":
                self.errors.append(response)
            if response.get("id") == self.counter:
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def dimensions(self, width, height):
        self.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
        self.evaluate(f"window.resizeRender({width},{height})")

    def frame(self, seconds=0, mode="video"):
        self.evaluate(f"window.renderFrame({seconds!r},{json.dumps(mode)})")
        result = self.call("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        return base64.b64decode(result["data"])


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def log_message(self, *_):
        pass


def browser_path():
    candidates = [shutil.which("chrome"), shutil.which("msedge"),
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    for value in candidates:
        if value and Path(value).is_file():
            return str(value)
    raise RuntimeError("Chrome or Edge is required")


def ffmpeg_path():
    if executable := shutil.which("ffmpeg"):
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as error:
        raise RuntimeError("Video export requires ffmpeg or imageio_ffmpeg") from error


def json_url(url):
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)


def export(cdp, output, args):
    output.mkdir(parents=True, exist_ok=True)
    cdp.dimensions(1920, 1080)
    (output / "robolaoye-concept-a-v1.png").write_bytes(cdp.frame(0, "hero"))
    print("Product render saved (1920 x 1080).", flush=True)
    stills = output / "stills"
    stills.mkdir(exist_ok=True)
    times = [0, 6.2, 14.8, 19, 23.8, 29]
    for index, seconds in enumerate(times):
        (stills / f"{index:02d}_{seconds:04.1f}s.png").write_bytes(cdp.frame(seconds))
    try:
        from PIL import Image
        sheet = Image.new("RGB", (1920, 1620), "#edf0f0")
        for index, seconds in enumerate(times):
            with Image.open(stills / f"{index:02d}_{seconds:04.1f}s.png") as im:
                sheet.paste(im.convert("RGB").resize((960, 540), Image.Resampling.LANCZOS), (index % 2 * 960, index // 2 * 540))
        sheet.save(output / "storyboard.jpg", quality=94)
    except ImportError:
        pass
    print("Six storyboard frames saved.", flush=True)
    manifest = {"scene": "visualization/scene.js", "candidate": "support_leg_assisted_tracks",
                "status": "artistic_keyframes_not_physics_or_validated_capability",
                "renderer": cdp.evaluate("window.sceneInfo"), "stills_seconds": times,
                "source_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in ("scene.js", "index.html")}}
    if args.video:
        cdp.dimensions(args.width, args.height)
        count = round(34 * args.fps)
        movie, log_path = output / "robolaoye-concept-a-v1.mp4", output / "ffmpeg.log"
        with log_path.open("wb") as log:
            command = [ffmpeg_path(), "-hide_banner", "-loglevel", "warning", "-y", "-f", "image2pipe", "-vcodec", "png",
                       "-framerate", str(args.fps), "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "19",
                       "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(movie)]
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log, stdout=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            try:
                for frame in range(count):
                    process.stdin.write(cdp.frame(frame / args.fps))
                    if frame % max(1, args.fps * 2) == 0:
                        print(f"Video: {frame}/{count} frames ({frame/args.fps:.0f}/34 s)", flush=True)
                process.stdin.close()
                if process.wait(timeout=90):
                    raise RuntimeError(log_path.read_text(encoding="utf-8", errors="replace"))
            except BaseException:
                process.terminate()
                process.wait(timeout=15)
                raise
        manifest["video"] = {"file": movie.name, "duration_s": 34, "frames": count, "fps": args.fps,
                             "width": args.width, "height": args.height, "audio": False}
        print(f"Video saved: {movie}", flush=True)
    if cdp.errors:
        raise RuntimeError(f"Browser reported errors: {cdp.errors[:2]}")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/visualization")
    parser.add_argument("--video", action="store_true")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()
    if not 1 <= args.fps <= 60 or args.width < 640 or args.height < 360 or args.width % 2 or args.height % 2:
        parser.error("Use 1-60 fps and even dimensions >= 640 x 360")
    if abs(args.width / args.height - 16 / 9) > .01:
        parser.error("The title layout requires a 16:9 video")
    vendor_three()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix="robolaoye-render-", ignore_cleanup_errors=True) as profile:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            devtools_port = probe.getsockname()[1]
        url = f"http://127.0.0.1:{server.server_port}/index.html"
        command = [browser_path(), "--headless=new", "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
                   "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--disable-background-timer-throttling",
                   f"--user-data-dir={profile}", f"--remote-debugging-port={devtools_port}", "--window-size=1920,1080", url]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        cdp = None
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                try:
                    pages = json_url(f"http://127.0.0.1:{devtools_port}/json/list")
                    page = next(p for p in pages if p.get("type") == "page" and "index.html" in p.get("url", ""))
                    cdp = CDP(page["webSocketDebuggerUrl"])
                    break
                except (OSError, StopIteration, ValueError):
                    time.sleep(.2)
            if cdp is None:
                raise RuntimeError("Headless browser did not start")
            cdp.call("Runtime.enable")
            cdp.call("Page.enable")
            while time.monotonic() < deadline:
                if cdp.evaluate("window.sceneReady===true"):
                    break
                if cdp.errors:
                    raise RuntimeError(cdp.errors)
                time.sleep(.2)
            else:
                raise RuntimeError("3D scene did not become ready")
            print(json.dumps(cdp.evaluate("window.sceneInfo"), ensure_ascii=False), flush=True)
            export(cdp, args.output.resolve(), args)
        finally:
            if cdp:
                try:
                    cdp.ws.send(json.dumps({"id": 999999, "method": "Browser.close"}))
                    cdp.ws.sock.close()
                except OSError:
                    pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)
            server.shutdown()


if __name__ == "__main__":
    main()
