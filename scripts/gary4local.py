#!/usr/bin/env python3
"""Run installed gary4local services without opening the desktop application.

This controller intentionally manages only processes that it started and recorded.
It may use an already-healthy service started by another owner, but it will not stop it.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from typing import Any
import urllib.error
import urllib.request


ALIASES = {
    "gary": "gary",
    "terry": "melodyflow",
    "melodyflow": "melodyflow",
    "jerry": "stable-audio",
    "stable-audio": "stable-audio",
    "sa3": "sa3",
    "carey": "carey",
    "foundation": "foundation",
    "foundation-1": "foundation",
}

PUBLIC_PREFIXES = {
    "gary": "",
    "melodyflow": "",
    "stable-audio": "/audio",
    "sa3": "/sa3",
    "carey": "/carey",
    "foundation": "/foundation",
}

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259


class ControllerError(RuntimeError):
    pass


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def default_runtime_root() -> Path:
    override = os.environ.get("GARY4LOCAL_RUNTIME_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise ControllerError(
            "APPDATA is unavailable. Set GARY4LOCAL_RUNTIME_ROOT to the Gary4JUCE runtime folder."
        )
    return (Path(appdata) / "Gary4JUCE").resolve()


def process_details(pid: int) -> tuple[bool, int | None]:
    """Return process liveness and Windows creation time for PID reuse protection."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True, None
        except OSError:
            return False, None

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False, None
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False, None
        if exit_code.value != STILL_ACTIVE:
            return False, None

        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return True, None
        creation_time = (created.dwHighDateTime << 32) | created.dwLowDateTime
        return True, creation_time
    finally:
        kernel32.CloseHandle(handle)


def gary4local_app_running() -> bool:
    if os.name != "nt":
        return False
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq gary4local.exe", "/NH"],
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    return "gary4local.exe" in result.stdout.lower()


def configure_text_streams() -> None:
    """Keep Windows consoles from crashing on Unicode service logs."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def gpu_inventory() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {
            "available": False,
            "gpus": [],
            "careyRecommendation": "standard",
            "reason": "nvidia-smi was not found; use the conservative standard Carey family.",
        }

    result = subprocess.run(
        [
            executable,
            "--query-gpu=index,name,memory.total,memory.used,memory.free",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    if result.returncode != 0:
        return {
            "available": False,
            "gpus": [],
            "careyRecommendation": "standard",
            "reason": result.stderr.strip() or "nvidia-smi failed.",
        }

    gpus = []
    for line in result.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 5:
            continue
        try:
            index, name, total, used, free = fields
            gpus.append(
                {
                    "index": int(index),
                    "name": name,
                    "totalMiB": int(total),
                    "usedMiB": int(used),
                    "freeMiB": int(free),
                }
            )
        except ValueError:
            continue

    primary = gpus[0] if gpus else None
    xl_capable = bool(
        primary
        and primary["totalMiB"] >= 12 * 1024
        and primary["freeMiB"] >= 10 * 1024
    )
    if xl_capable:
        recommendation = "xl-capable"
        reason = "At least 12 GiB total and 10 GiB currently free; XL may be considered."
    else:
        recommendation = "standard"
        reason = (
            "Use the standard Carey family unless at least 12 GiB total and 10 GiB "
            "free are available. Other local services should be stopped first."
        )
    return {
        "available": bool(gpus),
        "gpus": gpus,
        "careyRecommendation": recommendation,
        "reason": reason,
    }


class ControllerLock:
    def __init__(self, path: Path, timeout: float = 10.0):
        self.path = path
        self.timeout = timeout
        self.handle = None

    def __enter__(self) -> "ControllerLock":
        if os.name != "nt":
            raise ControllerError("The headless service controller currently supports Windows only.")
        import msvcrt

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self.handle.write(b"0")
            self.handle.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self.handle.close()
                    self.handle = None
                    raise ControllerError("Another gary4local controller operation is still running.")
                time.sleep(0.1)

    def __exit__(self, exc_type, exc, traceback) -> None:
        import msvcrt

        if self.handle is not None:
            self.handle.seek(0)
            try:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self.handle.close()
                self.handle = None


class Gary4LocalController:
    def __init__(self, runtime_root: Path):
        self.runtime_root = runtime_root
        self.services_root = runtime_root / "services"
        self.manifest_path = self.services_root / "manifests" / "services.json"
        self.settings_path = runtime_root / "app_settings.json"
        self.token_path = runtime_root / "hf_token.txt"
        self.agent_root = runtime_root / "agent"
        self.state_path = self.agent_root / "services.json"
        self.lock_path = self.agent_root / "controller.lock"

        manifest = load_json(self.manifest_path, None)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("services"), list):
            raise ControllerError(
                f"No valid gary4local service manifest found at {self.manifest_path}. "
                "Install gary4local and build at least one service first."
            )
        self.services = {
            service["id"]: service
            for service in manifest["services"]
            if isinstance(service, dict) and isinstance(service.get("id"), str)
        }
        self.settings = load_json(self.settings_path, {})

    def canonical_id(self, name: str) -> str:
        service_id = ALIASES.get(name.lower())
        if not service_id or service_id not in self.services:
            choices = ", ".join(sorted(ALIASES))
            raise ControllerError(f"Unknown service '{name}'. Choose one of: {choices}")
        return service_id

    def service(self, name: str) -> tuple[str, dict[str, Any]]:
        service_id = self.canonical_id(name)
        return service_id, self.services[service_id]

    def service_dir(self, service: dict[str, Any]) -> Path:
        return self.runtime_root / Path(str(service["workingDir"]))

    def python_exe(self, service: dict[str, Any]) -> Path:
        return self.service_dir(service) / "env" / "Scripts" / "python.exe"

    def entry_point(self, service: dict[str, Any]) -> Path:
        return self.service_dir(service) / str(service["entryPoint"])

    def base_url(self, service: dict[str, Any]) -> str:
        return f"http://127.0.0.1:{int(service['port'])}"

    def local_url(self, name: str, path: str = "") -> str:
        service_id, service = self.service(name)
        normalized = "/" + path.lstrip("/") if path else ""
        prefix = PUBLIC_PREFIXES[service_id]
        if prefix and (normalized == prefix or normalized.startswith(prefix + "/")):
            normalized = normalized[len(prefix) :]
        return self.base_url(service) + normalized

    def health_url(self, service: dict[str, Any]) -> str | None:
        health = service.get("healthCheck")
        if not isinstance(health, dict) or not health.get("endpoint"):
            return None
        return self.base_url(service) + str(health["endpoint"])

    def health(self, service: dict[str, Any], timeout: float = 0.5) -> tuple[bool, int | None]:
        url = self.health_url(service)
        if not url:
            return False, None
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return 200 <= response.status < 300, response.status
        except urllib.error.HTTPError as error:
            return False, error.code
        except (urllib.error.URLError, TimeoutError, OSError):
            return False, None

    def port_open(self, service: dict[str, Any], timeout: float = 0.3) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", int(service["port"])), timeout):
                return True
        except OSError:
            return False

    def read_state(self) -> dict[str, Any]:
        state = load_json(self.state_path, {"version": 1, "services": {}})
        if not isinstance(state, dict):
            state = {"version": 1, "services": {}}
        if not isinstance(state.get("services"), dict):
            state["services"] = {}
        state["version"] = 1
        return state

    def write_state(self, state: dict[str, Any]) -> None:
        write_json_atomic(self.state_path, state)

    def owned_record(self, service_id: str) -> tuple[dict[str, Any] | None, bool]:
        record = self.read_state()["services"].get(service_id)
        if not isinstance(record, dict) or not isinstance(record.get("pid"), int):
            return None, False
        alive, creation_time = process_details(record["pid"])
        if not alive:
            return record, False
        expected = record.get("creationTime")
        if expected is not None and creation_time is not None and expected != creation_time:
            return record, False
        return record, True

    def status(self, name: str) -> dict[str, Any]:
        service_id, service = self.service(name)
        record, owned_alive = self.owned_record(service_id)
        healthy, status_code = self.health(service)
        port_open = healthy or self.port_open(service)

        if healthy:
            state = "running"
        elif owned_alive:
            state = "starting" if not port_open else "unhealthy"
        elif port_open:
            state = "unhealthy"
        else:
            state = "stopped"

        ownership = "agent" if owned_alive else ("external" if port_open else "none")
        return {
            "service": service_id,
            "displayName": service.get("displayName", service_id),
            "state": state,
            "healthy": healthy,
            "healthStatusCode": status_code,
            "ownership": ownership,
            "pid": record.get("pid") if owned_alive and record else None,
            "port": int(service["port"]),
            "baseUrl": self.base_url(service),
            "healthUrl": self.health_url(service),
            "environmentBuilt": self.python_exe(service).is_file(),
            "logPath": str(self.service_dir(service) / f"{service_id}.log"),
            "careyFamily": record.get("careyFamily") if owned_alive and record else None,
        }

    def doctor(self) -> dict[str, Any]:
        statuses = [self.status(service_id) for service_id in self.services]
        built = sum(1 for status in statuses if status["environmentBuilt"])
        warnings = []
        if gary4local_app_running():
            warnings.append(
                "gary4local.exe is running. Healthy UI-owned services may be used, but this "
                "controller will not stop them. Close the app for fully headless operation."
            )
        if built != len(statuses):
            warnings.append(f"Only {built} of {len(statuses)} service environments are built.")
        return {
            "ready": self.runtime_root.is_dir() and self.manifest_path.is_file() and built > 0,
            "runtimeRoot": str(self.runtime_root),
            "manifestPath": str(self.manifest_path),
            "gary4localAppRunning": gary4local_app_running(),
            "builtServiceCount": built,
            "serviceCount": len(statuses),
            "warnings": warnings,
            "gpu": gpu_inventory(),
            "services": statuses,
        }

    def carey_family(self, requested: str) -> str:
        if requested == "standard":
            return "standard"
        if requested == "xl":
            return "xl"
        if requested == "saved":
            return "xl" if bool(self.settings.get("careyUseXlModels", False)) else "standard"
        if requested != "auto":
            raise ControllerError(f"Unknown Carey family '{requested}'.")

        gpu = gpu_inventory()
        if (
            gpu.get("careyRecommendation") == "xl-capable"
            and bool(self.settings.get("careyUseXlModels", False))
        ):
            return "xl"
        return "standard"

    def resolved_environment(
        self,
        service_id: str,
        service: dict[str, Any],
        carey_family: str | None = None,
    ) -> dict[str, str]:
        env = os.environ.copy()
        service_dir = self.service_dir(service)
        python_path = os.pathsep.join((str(service_dir), str(self.services_root)))
        env.update(
            {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
                "PYTHONPATH": python_path,
            }
        )

        token = ""
        try:
            token = self.token_path.read_text(encoding="utf-8-sig").strip()
        except OSError:
            token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN", "")
        models_dir = os.environ.get("MODELS_DIR", str(self.runtime_root / "models"))

        replacements = {
            "${APPDATA}": os.environ.get("APPDATA", str(self.runtime_root.parent)),
            "${MODELS_DIR}": models_dir,
            "${HF_TOKEN}": token,
        }
        for key, raw_value in (service.get("env") or {}).items():
            value = str(raw_value)
            for marker, replacement in replacements.items():
                value = value.replace(marker, replacement)
            if value and "${" not in value:
                env[str(key)] = value

        if service_id == "melodyflow":
            enabled = bool(self.settings.get("melodyflowUseFlashAttn", False))
            env["MELODYFLOW_USE_FLASH_ATTN"] = "1" if enabled else "0"

        if service_id == "sa3":
            loudness = self.settings.get("sa3Loudness") or {}
            setting_map = {
                "peakNormalizeDb": "SA3_PEAK_NORMALIZE_DB",
                "limiterCeilingDb": "SA3_LIMITER_CEILING_DB",
                "latentRescale": "SA3_LATENT_RESCALE",
                "latentShift": "SA3_LATENT_SHIFT",
                "latentTargetStd": "SA3_LATENT_TARGET_STD",
                "continuationTailPad": "SA3_CONTINUE_TAIL_PAD",
            }
            for setting, env_name in setting_map.items():
                value = str(loudness.get(setting, "")).strip()
                if value:
                    env[env_name] = value

        if service_id == "carey":
            use_xl = carey_family == "xl"
            family = "acestep-v15-xl" if use_xl else "acestep-v15"
            env.update(
                {
                    "ACESTEP_CONFIG_PATH": f"{family}-base",
                    "ACESTEP_BASE_CONFIG_PATH": f"{family}-base",
                    "ACESTEP_SFT_CONFIG_PATH": f"{family}-sft",
                    "ACESTEP_TURBO_CONFIG_PATH": f"{family}-turbo",
                    "ACESTEP_LEGO_CONFIG_PATH": "acestep-v15-base",
                    "ACESTEP_REGULAR_CONFIG_PATH": "acestep-v15-base",
                    "ACESTEP_NO_INIT": "true",
                }
            )
        return env

    def start(
        self,
        name: str,
        timeout: float | None,
        carey_family: str = "auto",
    ) -> dict[str, Any]:
        service_id, service = self.service(name)
        if service_id != "carey" and carey_family != "auto":
            raise ControllerError("--carey-family may only be used when starting Carey.")
        resolved_carey_family = (
            self.carey_family(carey_family) if service_id == "carey" else None
        )
        with ControllerLock(self.lock_path):
            current = self.status(service_id)
            if current["healthy"]:
                current["action"] = "already-running"
                return current
            if current["ownership"] == "external":
                raise ControllerError(
                    f"Port {service['port']} is owned by another process but {self.health_url(service)} "
                    "is not healthy. Refusing to replace or kill it."
                )
            if current["ownership"] == "agent":
                raise ControllerError(
                    f"{service_id} is already starting under agent PID {current['pid']}."
                )

            python = self.python_exe(service)
            entry_point = self.entry_point(service)
            if not python.is_file():
                raise ControllerError(
                    f"{service_id} is not built. Open gary4local once and build its environment. "
                    f"Expected {python}"
                )
            if not entry_point.is_file():
                raise ControllerError(f"Missing service entry point: {entry_point}")

            service_dir = self.service_dir(service)
            log_path = service_dir / f"{service_id}.log"
            with log_path.open("ab", buffering=0) as log_file:
                banner = (
                    f"\n===== gary4claude headless start {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n"
                )
                log_file.write(banner.encode("utf-8"))
                process = subprocess.Popen(
                    [str(python), str(service["entryPoint"])],
                    cwd=service_dir,
                    env=self.resolved_environment(
                        service_id,
                        service,
                        resolved_carey_family,
                    ),
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=log_file,
                    creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
                    close_fds=True,
                )

            creation_time = None
            for _ in range(10):
                alive, creation_time = process_details(process.pid)
                if alive and creation_time is not None:
                    break
                time.sleep(0.05)

            state = self.read_state()
            state["services"][service_id] = {
                "pid": process.pid,
                "creationTime": creation_time,
                "startedAt": int(time.time()),
                "serviceDir": str(service_dir),
                "logPath": str(log_path),
                "careyFamily": resolved_carey_family,
            }
            self.write_state(state)

        if timeout is None:
            health = service.get("healthCheck") or {}
            timeout = max(60.0, float(health.get("startupGraceSeconds", 0)) + 30.0)
        if timeout <= 0:
            result = self.status(service_id)
            result["action"] = "started"
            return result

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.status(service_id)
            if result["healthy"]:
                result["action"] = "started"
                return result
            if result["ownership"] != "agent":
                break
            time.sleep(1.0)

        result = self.status(service_id)
        tail = self.tail_log(service_id, 30)
        if result["ownership"] != "agent":
            raise ControllerError(
                f"{service_id} exited before becoming healthy. Log: {result['logPath']}\n{tail}"
            )
        raise ControllerError(
            f"Timed out after {timeout:g}s waiting for {service_id}. It is still owned by the "
            f"agent and can be inspected or stopped. Log: {result['logPath']}\n{tail}"
        )

    def stop(self, name: str, timeout: float = 20.0) -> dict[str, Any]:
        service_id, service = self.service(name)
        with ControllerLock(self.lock_path):
            record, owned_alive = self.owned_record(service_id)
            current = self.status(service_id)
            if not owned_alive:
                state = self.read_state()
                if service_id in state["services"]:
                    del state["services"][service_id]
                    self.write_state(state)
                if current["ownership"] == "external":
                    raise ControllerError(
                        f"{service_id} is running but was not started by this controller. "
                        "Refusing to stop an external/UI-owned process."
                    )
                current["action"] = "already-stopped"
                return current

            pid = int(record["pid"])
            result = subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(pid)],
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
            deadline = time.monotonic() + max(0.0, timeout)
            while time.monotonic() < deadline:
                if not process_details(pid)[0]:
                    break
                time.sleep(0.2)
            if process_details(pid)[0]:
                raise ControllerError(
                    f"Could not stop {service_id} PID {pid}: "
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )

            state = self.read_state()
            state["services"].pop(service_id, None)
            self.write_state(state)

        current = self.status(service_id)
        if current["healthy"]:
            raise ControllerError(
                f"Stopped owned PID {pid}, but {service_id} is still healthy under another process."
            )
        current["action"] = "stopped"
        return current

    def tail_log(self, name: str, lines: int) -> str:
        service_id, service = self.service(name)
        log_path = self.service_dir(service) / f"{service_id}.log"
        if not log_path.is_file():
            return ""
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-lines:])


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--runtime-root",
        help="Override the installed runtime root (default: %%APPDATA%%\\Gary4JUCE)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start and stop installed gary4local services headlessly."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Check the installation and all service environments")
    add_common_options(doctor)

    status = sub.add_parser("status", help="Show one service or all service states")
    status.add_argument("service", nargs="?")
    add_common_options(status)

    start = sub.add_parser("start", help="Start a service, or use it if already healthy")
    start.add_argument("service")
    start.add_argument(
        "--timeout",
        type=float,
        help="Health wait in seconds; 0 starts without waiting",
    )
    start.add_argument(
        "--carey-family",
        choices=["auto", "standard", "xl", "saved"],
        default="auto",
        help="Carey model family; auto protects lower-VRAM GPUs",
    )
    add_common_options(start)

    ensure = sub.add_parser("ensure", help="Alias for start; ensure a service is healthy")
    ensure.add_argument("service")
    ensure.add_argument("--timeout", type=float)
    ensure.add_argument(
        "--carey-family",
        choices=["auto", "standard", "xl", "saved"],
        default="auto",
        help="Carey model family; auto protects lower-VRAM GPUs",
    )
    add_common_options(ensure)

    stop = sub.add_parser("stop", help="Stop a service only if this controller started it")
    stop.add_argument("service")
    stop.add_argument("--timeout", type=float, default=20.0)
    add_common_options(stop)

    url = sub.add_parser("url", help="Resolve a service endpoint to its localhost URL")
    url.add_argument("service")
    url.add_argument("path", nargs="?", default="")
    add_common_options(url)

    logs = sub.add_parser("logs", help="Print the tail of a service log")
    logs.add_argument("service")
    logs.add_argument("--lines", type=int, default=80)
    add_common_options(logs)

    gpu = sub.add_parser("gpu", help="Inspect GPU memory and Carey family guidance")
    add_common_options(gpu)
    return parser


def emit(payload: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    if isinstance(payload, str):
        print(payload)
        return
    if isinstance(payload, list):
        for item in payload:
            print(
                f"{item['service']:<13} {item['state']:<10} "
                f"owner={item['ownership']:<8} {item['baseUrl']}"
            )
        return
    if "services" in payload and "ready" in payload:
        print(f"runtime: {payload['runtimeRoot']}")
        print(
            f"ready: {str(payload['ready']).lower()} "
            f"({payload['builtServiceCount']}/{payload['serviceCount']} environments built)"
        )
        for warning in payload["warnings"]:
            print(f"warning: {warning}")
        emit(payload["services"], False)
        return
    if "gpus" in payload and "careyRecommendation" in payload:
        if not payload["available"]:
            print(f"GPU unavailable: {payload['reason']}")
            return
        for gpu in payload["gpus"]:
            print(
                f"GPU {gpu['index']}: {gpu['name']} | "
                f"{gpu['freeMiB']} MiB free / {gpu['totalMiB']} MiB total"
            )
        print(
            f"Carey: {payload['careyRecommendation']} | {payload['reason']}"
        )
        return
    print(
        f"{payload['service']}: {payload['state']} "
        f"(owner={payload['ownership']}, url={payload['baseUrl']})"
    )


def main(argv: list[str] | None = None) -> int:
    configure_text_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    as_json = bool(args.json)
    try:
        root = Path(args.runtime_root).expanduser().resolve() if args.runtime_root else default_runtime_root()
        controller = Gary4LocalController(root)

        if args.command == "doctor":
            payload = controller.doctor()
            emit(payload, as_json)
            return 0 if payload["ready"] else 1
        if args.command == "status":
            payload = (
                controller.status(args.service)
                if args.service
                else [controller.status(service_id) for service_id in controller.services]
            )
            emit(payload, as_json)
            return 0
        if args.command in ("start", "ensure"):
            emit(
                controller.start(
                    args.service,
                    args.timeout,
                    args.carey_family,
                ),
                as_json,
            )
            return 0
        if args.command == "stop":
            emit(controller.stop(args.service, args.timeout), as_json)
            return 0
        if args.command == "url":
            url = controller.local_url(args.service, args.path)
            emit({"service": controller.canonical_id(args.service), "url": url}, True) if as_json else print(url)
            return 0
        if args.command == "logs":
            if args.lines <= 0:
                raise ControllerError("--lines must be greater than zero")
            text = controller.tail_log(args.service, args.lines)
            emit({"service": controller.canonical_id(args.service), "log": text}, True) if as_json else print(text, end="" if text.endswith("\n") else "\n")
            return 0
        if args.command == "gpu":
            emit(gpu_inventory(), as_json)
            return 0
        parser.error("Unknown command")
    except ControllerError as error:
        if as_json:
            print(json.dumps({"success": False, "error": str(error)}, indent=2))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
