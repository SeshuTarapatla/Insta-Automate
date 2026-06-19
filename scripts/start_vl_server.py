"""Serve qwen3-vl on llama-server with a low image-token floor.

Ollama injects ``--image-min-tokens 1024`` for qwen3-vl, forcing every image to
~1067 vision tokens. qwen3-vl's CLIP encoder runs on CPU, and encode time is
linear in token count, so each image takes 7-12s. This bypasses Ollama and runs
its *bundled* llama-server.exe directly against the same model blob with a small
``--image-min-tokens`` (default 64), restoring ~0.2s/image.

The app (controllers/ollama.py) talks to this server's OpenAI endpoint at
http://127.0.0.1:11500/v1. Start this before running the entity_classify flow:

    python scripts/start_vl_server.py

No insta_automate imports here so it stays a zero-dependency standalone launcher.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_MODEL = os.getenv("OLLAMA_VL_MODEL", "qwen3-vl:4b-instruct")


def ollama_root() -> Path:
    override = os.getenv("OLLAMA_INSTALL_DIR")
    if override:
        return Path(override)
    return Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama"


def models_dir() -> Path:
    return Path(os.getenv("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")


def find_llama_server(root: Path) -> Path:
    primary = root / "lib" / "ollama" / "llama-server.exe"
    if primary.exists():
        return primary
    hits = list(root.rglob("llama-server.exe"))
    if not hits:
        sys.exit(f"llama-server.exe not found under {root}")
    return hits[0]


def resolve_gguf(model: str) -> Path:
    name, _, tag = model.partition(":")
    tag = tag or "latest"
    manifest = (
        models_dir() / "manifests" / "registry.ollama.ai" / "library" / name / tag
    )
    if not manifest.exists():
        sys.exit(f"manifest not found: {manifest}\nPull the model: ollama pull {model}")
    layers = json.loads(manifest.read_text())["layers"]
    model_layers = [
        layer for layer in layers if layer.get("mediaType", "").endswith("image.model")
    ]
    layer = max(model_layers or layers, key=lambda layer: layer.get("size", 0))
    return models_dir() / "blobs" / layer["digest"].replace(":", "-")


def build_env(server: Path) -> dict[str, str]:
    """Put Ollama's backend DLL dirs (cuda_*, vulkan, base) on PATH for GPU init."""
    libdir = server.parent
    backend_dirs = [libdir, *[d for d in libdir.iterdir() if d.is_dir()]]
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(
        [*(str(d) for d in backend_dirs), env.get("PATH", "")]
    )
    cuda = next((d for d in backend_dirs if d.name.startswith("cuda")), None)
    if cuda and (cuda / "ggml-cuda.dll").exists():
        env["GGML_BACKEND_PATH"] = str(cuda / "ggml-cuda.dll")
    env.setdefault("CUDA_VISIBLE_DEVICES", "0")
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    # 127.0.0.1 is enough: the k3s (Rancher Desktop) worker pod reaches the host
    # via host.docker.internal, which forwards to the Windows host's loopback
    # (same path Ollama used on :11434). Override with --host 0.0.0.0 only if a
    # client needs to reach it over the LAN.
    parser.add_argument("--host", default=os.getenv("VL_SERVER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("VL_SERVER_PORT", "11500")))
    parser.add_argument(
        "--image-min-tokens",
        type=int,
        default=int(os.getenv("VL_IMAGE_MIN_TOKENS", "64")),
    )
    parser.add_argument("--ctx", type=int, default=int(os.getenv("VL_CTX", "4096")))
    parser.add_argument(
        "--no-autorestart",
        action="store_true",
        help="exit on first crash instead of restarting",
    )
    parser.add_argument(
        "--max-restarts",
        type=int,
        default=0,
        metavar="N",
        help="stop after N restarts (0 = unlimited)",
    )
    args = parser.parse_args()

    root = ollama_root()
    server = find_llama_server(root)
    gguf = resolve_gguf(args.model)
    if not gguf.exists():
        sys.exit(f"model blob missing: {gguf}\nPull it: ollama pull {args.model}")

    cmd = [
        str(server),
        "--model", str(gguf),
        "--mmproj", str(gguf),
        "--host", args.host,
        "--port", str(args.port),
        "--ctx-size", str(args.ctx),
        "--image-min-tokens", str(args.image_min_tokens),
        "--flash-attn", "auto",
        "--no-webui",
        "--offline",
        "--no-mmap",
        "--no-jinja",
        "--chat-template", "chatml",
        "-np", "1",
        "-b", "512",
        "-ub", "512",
    ]
    print(
        f"qwen3-vl -> http://{args.host}:{args.port}/v1  "
        f"(image-min-tokens={args.image_min_tokens}, blob={gguf.name[:19]})",
        flush=True,
    )

    # Windows STATUS_CONTROL_C_EXIT — treat as user-initiated stop, not a crash
    CTRL_C_EXIT = -1073741510

    env = build_env(server)
    restarts = 0
    backoff = 5

    while True:
        start = time.monotonic()
        try:
            rc = subprocess.run(cmd, env=env).returncode
        except KeyboardInterrupt:
            print("\nStopped.", flush=True)
            sys.exit(0)

        if rc == 0 or rc == CTRL_C_EXIT:
            sys.exit(0)

        if args.no_autorestart:
            sys.exit(rc)

        restarts += 1
        if args.max_restarts and restarts > args.max_restarts:
            print(f"Max restarts ({args.max_restarts}) reached. Exiting.", flush=True)
            sys.exit(rc)

        # Reset backoff if the server ran long enough (not an instant crash loop)
        if time.monotonic() - start > 60:
            backoff = 5

        print(
            f"[{time.strftime('%H:%M:%S')}] Server crashed (exit {rc})."
            f" Restart #{restarts} in {backoff}s...",
            flush=True,
        )
        try:
            time.sleep(backoff)
        except KeyboardInterrupt:
            print("\nStopped.", flush=True)
            sys.exit(0)

        backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    main()
