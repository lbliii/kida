"""Build and smoke-test Kida distribution artifacts for stability verification."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    display = " ".join(cmd)
    print(f"$ {display}", flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _venv_python(venv: Path) -> Path:
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _smoke_code() -> str:
    return textwrap.dedent(
        r"""
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        import kida
        from kida import DictLoader, Environment, SandboxedEnvironment, SecurityError

        assert kida.__version__

        env = Environment(loader=DictLoader({
            "components.html": "{% def card(title: str) %}<h1>{{ title }}</h1>{% end %}",
            "page.html": "{% from 'components.html' import card %}{{ card('Hello') }}",
        }))
        assert env.get_template("page.html").render() == "<h1>Hello</h1>"

        component = env.get_template("components.html").def_metadata()["card"]
        assert component.name == "card"
        assert component.params[0].name == "title"
        assert component.params[0].annotation == "str"

        sandbox = SandboxedEnvironment()
        try:
            sandbox.from_string("{{ obj.__class__ }}").render(obj=object())
        except SecurityError:
            pass
        else:
            raise AssertionError("sandbox allowed blocked __class__ access")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "components.html").write_text(
                "{% def card(title: str) %}{{ title }}{% end %}",
                encoding="utf-8",
            )
            (root / "page.html").write_text(
                "{% from 'components.html' import card %}{{ card('Hi') }}",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "kida", "check", str(root), "--validate-calls"],
                check=False,
                capture_output=True,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr

            proc = subprocess.run(
                [sys.executable, "-m", "kida", "components", str(root), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr
            data = json.loads(proc.stdout)
            assert data[0]["name"] == "card"
            assert data[0]["params"][0]["annotation"] == "str"

        print("Package smoke passed")
        """
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="kida-package-") as tmp:
        tmpdir = Path(tmp)
        dist = tmpdir / "dist"
        venv = tmpdir / "venv"

        _run(["uv", "build", "--out-dir", str(dist)])

        wheels = sorted(dist.glob("*.whl"))
        sdists = sorted(dist.glob("*.tar.gz"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected exactly one wheel in {dist}, found {len(wheels)}")
        if len(sdists) != 1:
            raise RuntimeError(f"expected exactly one sdist in {dist}, found {len(sdists)}")

        python_exe = shutil.which("python3") or sys.executable
        _run([python_exe, "-m", "venv", str(venv)])
        venv_python = _venv_python(venv)

        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        _run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--disable-pip-version-check",
                str(wheels[0]),
            ],
            env=env,
        )
        _run([str(venv_python), "-c", _smoke_code()], env=env)

        print(f"Built artifacts: {wheels[0].name}, {sdists[0].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
