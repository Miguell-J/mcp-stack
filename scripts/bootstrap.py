"""Reproducible bootstrap. Never edits an existing dependency checkout silently."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UV_VERSION = "0.12.13"


def run(*args: str, cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref", help="Explicit override; prefer recording the full commit in stack.yaml"
    )
    parser.add_argument(
        "--update-dependency",
        action="store_true",
        help="Explicitly allow switching a clean existing checkout",
    )
    parser.add_argument("--deps-only", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("UV_CACHE_DIR", str(ROOT / ".uv-cache"))
    python = ROOT / ".venv/bin/python"
    uv = ROOT / ".venv/bin/uv"
    if not python.exists():
        run(sys.executable, "-m", "venv", str(ROOT / ".venv"))
    if not uv.exists():
        run(str(python), "-m", "pip", "install", f"uv=={UV_VERSION}")
    if not args.deps_only:
        run(str(uv), "sync", "--locked", "--all-packages")
    if Path(sys.prefix) != ROOT / ".venv":
        run(
            str(python),
            __file__,
            "--deps-only",
            *(["--ref", args.ref] if args.ref else []),
            *(["--update-dependency"] if args.update_dependency else []),
        )
        return
    from mcp_stack.config import load_config
    from mcp_stack.render import render

    config = load_config(ROOT / "config/stack.yaml")
    dependency = ROOT / ".deps/mcp-one"
    ref = args.ref or config.mcp_one.ref
    existed = dependency.exists()
    if not existed:
        dependency.parent.mkdir(exist_ok=True)
        run("git", "clone", config.mcp_one.url, str(dependency))
    if git(dependency, "remote", "get-url", "origin") != config.mcp_one.url:
        raise SystemExit("Dependency origin differs from the official URL; refusing to change it")
    if git(dependency, "status", "--porcelain"):
        raise SystemExit("Dependency checkout is dirty; preserve changes before bootstrap")
    try:
        target = git(dependency, "rev-parse", "--verify", f"{ref}^{{commit}}")
    except subprocess.CalledProcessError:
        run("git", "-C", str(dependency), "fetch", "origin", ref)
        target = git(dependency, "rev-parse", "FETCH_HEAD")
    current = git(dependency, "rev-parse", "HEAD")
    if current != target:
        if existed and not args.update_dependency:
            raise SystemExit(
                f"Dependency is {current}; requested {target}. "
                "Use --update-dependency to switch explicitly."
            )
        run("git", "-C", str(dependency), "switch", "--detach", target)
    print(f"MCP One: {target} ({config.mcp_one.url})", flush=True)
    if target != config.mcp_one.ref:
        print("WARNING: local ref override differs from the reproducible stack pin", flush=True)
    run(str(python), "-m", "compileall", "-q", str(dependency / "src"))
    run(str(uv), "sync", "--locked", cwd=dependency)
    run(str(dependency / ".venv/bin/python"), "-c", "from mcp_one.server import create_app")
    render(config, ROOT)
    print("Bootstrap complete. Run make up.")


if __name__ == "__main__":
    main()
