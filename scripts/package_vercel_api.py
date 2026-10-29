"""Build an allowlisted API deployment directory, excluding databases and secrets."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".vercel-api-candidate"


def main():
    # Refuse to overlay an old bundle: stale code must not reach a deployment.
    TARGET.mkdir(exist_ok=False)
    for source in (ROOT / "api").rglob("*.py"):
        relative = source.relative_to(ROOT)
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    for name in ("plan.py", "progression.py"):
        shutil.copyfile(ROOT / name, TARGET / name)
    shutil.copyfile(ROOT / "api" / "requirements.txt", TARGET / "requirements.txt")
    dependencies = [line.strip() for line in (ROOT / "api" / "requirements.txt").read_text().splitlines()
                    if line.strip() and not line.startswith("#")]
    (TARGET / "pyproject.toml").write_text(
        '[project]\nname = "workout-progression-api"\nversion = "1.0.0"\n'
        'requires-python = ">=3.12,<3.13"\n'
        f'dependencies = {json.dumps(dependencies)}\n'
        '[tool.vercel]\nentrypoint = "api.index:app"\n', encoding="utf-8"
    )
    (TARGET / "vercel.json").write_text(json.dumps({
        "$schema": "https://openapi.vercel.sh/vercel.json",
        "framework": "fastapi",
        "regions": ["iad1"],
        "fluid": True,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared API candidate: {TARGET}")


if __name__ == "__main__":
    main()
