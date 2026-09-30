"""Verify the frozen bundle inventory, imports, bindings, and optional inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-imports", action="store_true")
    parser.add_argument("--backbone-snapshot", type=Path)
    args = parser.parse_args()
    from runtime.v3_pretraining.project_release import verify_project_release
    manifest = verify_project_release(ROOT)
    if args.check_imports:
        code = ("from pathlib import Path\n"
                "import models.v3_pretraining.architecture as a\n"
                "import runtime.v3_pretraining.project_release as r\n"
                "import runtime.v3_pretraining.public_graph as p\n"
                "root=Path.cwd().resolve()\n"
                "assert all(Path(m.__file__).resolve().is_relative_to(root) for m in (a,r,p))\n")
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT,
                                capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError("isolated release import failed: " + result.stderr)
    if args.backbone_snapshot:
        from runtime.v3_pretraining.project_release import load_project_release_worker
        from runtime.v3_pretraining.public_graph import validate_public
        worker = load_project_release_worker(
            ROOT, backbone_snapshot=args.backbone_snapshot, device="cpu")
        public = worker.analyze_public(article_id="release-smoke-001",
                                       content="서울에서 로봇 대회가 열렸다.")
        validate_public(public)
        if (public["schema_version"] != manifest["public"]["schema_version"] or
                public["projection_version"] != manifest["public"]["projection_version"]):
            raise ValueError("PUBLIC version differs from release manifest")
    print(json.dumps({"status": manifest["status"],
                      "files_verified": len(manifest["files_sha256"]),
                      "isolated_import": bool(args.check_imports),
                      "inference_smoke": bool(args.backbone_snapshot)}, sort_keys=True))


if __name__ == "__main__":
    main()
