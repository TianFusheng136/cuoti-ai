import json
import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
SBOM = ROOT / "sbom" / "python.cdx.json"


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    direct_names = {normalize(Requirement(item).name) for item in project["dependencies"]}
    document = json.loads(SBOM.read_text(encoding="utf-8"))
    components = {
        normalize(component["name"]): component["bom-ref"]
        for component in document.get("components", [])
    }
    missing = sorted(direct_names - components.keys())
    if missing:
        raise SystemExit(f"Python SBOM缺少直接依赖：{', '.join(missing)}")

    root_ref = document["metadata"]["component"]["bom-ref"]
    dependencies = document.setdefault("dependencies", [])
    root = next((item for item in dependencies if item["ref"] == root_ref), None)
    if root is None:
        root = {"ref": root_ref}
        dependencies.append(root)
    root["dependsOn"] = sorted(components[name] for name in direct_names)
    dependencies.sort(key=lambda item: item["ref"])
    SBOM.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
