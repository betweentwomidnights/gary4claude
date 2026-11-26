# gary4local Headless Profile

Use this profile when the user has installed gary4local on Windows and wants the
agent to run the music services without opening the desktop application.

This controller guide describes the older Python service environments. Current
Carey uses native ace-server and Yuey is native too. Their lifecycle support has
not been modernized in this hosted-inference documentation pass. Discover the
installed runtime and controller capabilities before applying these recipes;
do not assume a native executable has a Python environment to start.

## Requirements

1. Install gary4local.
2. Open it once and build the service environments the user wants to use.
3. Close gary4local for fully headless operation.
4. Use the absolute skill directory supplied by `SKILL.md`; do not resolve
   scripts relative to the current project. Run:

```powershell
python "<skill-dir>/scripts/gary4local.py" doctor --json
```

Proceed only when `ready` is `true` and the needed service has
`environmentBuilt: true`. Other unbuilt services do not block use of a built one.

The controller reads the installed manifest under `%APPDATA%\Gary4JUCE`, applies
the saved gary4local settings, starts the installed virtual environment, waits for
health, and records process ownership under `%APPDATA%\Gary4JUCE\agent`.

## Service Lifecycle

Before calling a local API, ensure its service is healthy:

```powershell
python "<skill-dir>/scripts/gary4local.py" ensure jerry --json
```

After the request has completed and its audio has been saved, stop the service:

```powershell
python "<skill-dir>/scripts/gary4local.py" stop jerry --json
```

The controller may reuse a healthy service started by the desktop app or another
owner. It deliberately refuses to stop any process it did not start. In the
intended headless workflow, close gary4local first so every service the agent
starts is agent-owned.

Useful commands:

```powershell
python "<skill-dir>/scripts/gary4local.py" status --json
python "<skill-dir>/scripts/gary4local.py" status carey --json
python "<skill-dir>/scripts/gary4local.py" logs carey --lines 100
python "<skill-dir>/scripts/gary4local.py" url sa3 /sa3/generate/loop
python "<skill-dir>/scripts/gary4local.py" gpu --json
```

Use `--timeout 0` with `start` or `ensure` only when deliberately starting in the
background. Normally let the command wait for a healthy service.

## GPU and Carey Model Family

Inspect GPU memory before starting Carey:

```powershell
python "<skill-dir>/scripts/gary4local.py" gpu --json
python "<skill-dir>/scripts/gary4local.py" ensure carey --carey-family auto --json
```

`auto` is the safe default. It selects the standard ACE-Step family unless the
saved desktop setting enables XL and the primary GPU has at least 12 GiB total
with 10 GiB currently free. On an 8 GiB GPU, use the standard family. Stop every
other model service before Carey.

Use `--carey-family standard` or `--carey-family xl` only for an intentional
override. `--carey-family saved` reproduces the desktop toggle without applying
the headless VRAM guard.

## Local API Routing

| Character | Controller name | Local base | Public prefix removed locally |
|-----------|-----------------|------------|-------------------------------|
| Gary | `gary` | `http://127.0.0.1:8000` | none |
| Terry | `terry` | `http://127.0.0.1:8002` | none |
| Carey | `carey` | `http://127.0.0.1:8003` | `/carey` |
| Jerry | `jerry` | `http://127.0.0.1:8005` | `/audio` |
| SA3 | `sa3` | `http://127.0.0.1:8006` | `/sa3` |
| Foundation | `foundation` | `http://127.0.0.1:8015` | `/foundation` |

Examples:

- Remote `/audio/generate/loop` becomes local `http://127.0.0.1:8005/generate/loop`.
- Remote `/sa3/prompts` becomes local `http://127.0.0.1:8006/prompts`.
- Native Carey `/carey/synth` becomes local `http://127.0.0.1:8003/synth`;
  use `/props` and `/job` as described in `carey.md`. Older Python installations
  can expose legacy `/cover` instead. Do not mix the two contracts.
- Remote `/foundation/randomize` becomes local `http://127.0.0.1:8015/randomize`.
- Gary `/api/juce/continue_music` remains that path on port 8000.
- Terry `/api/juce/transform_audio` remains that path on port 8002.

Use the `url` command when uncertain. It accepts either public or local-style paths
and returns the correct direct URL:

```powershell
python "<skill-dir>/scripts/gary4local.py" url jerry /audio/generate/loop
# http://127.0.0.1:8005/generate/loop
```

Once the local profile is selected, do not call `g4l.thecollabagepatch.com`.

## Headless Music Workflow

Run one GPU-heavy stage at a time:

1. Ensure only the service needed for the next stage.
2. Submit one request and poll its direct local status endpoint when asynchronous.
3. Save returned audio and metadata before doing anything else.
4. Stop the current service.
5. Ensure the next service and pass it the saved base64 WAV.

This replaces the remote deployment's always-on services and shared queue. Do not
start several local model services in parallel. Sequential service ownership avoids
GPU contention and makes failures much easier to recover from.

Gary and Terry use similar `/api/juce` paths but are separate processes. Use port
8000 for Gary continuation and port 8002 for Terry transformation and polling.

## Failures and Recovery

- If startup fails, inspect
  `python "<skill-dir>/scripts/gary4local.py" logs <service>`.
- If status says `ownership: external`, use a healthy service but do not attempt to
  stop it. Ask the user to close gary4local or the owning process if necessary.
- If a port is occupied but health fails, do not kill the port owner. Report the
  conflict.
- Stop only through this controller. Do not use broad `taskkill` or kill all Python
  processes.
- Preserve every completed audio artifact before stopping or switching services.
