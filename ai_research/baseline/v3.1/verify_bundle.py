"""Verify the v3.1 candidate inventory, imports, bindings, and optional inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
RELEASE_VERSION = "3.1-project-candidate-d2-e1"


def verify_v31_identity(manifest: dict, *, schema_version: str,
                        projection_version: str) -> None:
    public = manifest.get("public")
    if (manifest.get("release_version") != RELEASE_VERSION or
            not isinstance(public, dict) or
            public.get("schema_version") != schema_version or
            public.get("projection_version") != projection_version):
        raise ValueError("v3.1 release identity or PUBLIC projection differs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-imports", action="store_true")
    parser.add_argument("--backbone-snapshot", type=Path)
    args = parser.parse_args()
    from runtime.v3_pretraining.project_release import verify_project_release
    from runtime.v3_pretraining.public_graph import PROJECTION_VERSION, SCHEMA_VERSION
    manifest = verify_project_release(ROOT)
    verify_v31_identity(manifest, schema_version=SCHEMA_VERSION,
                        projection_version=PROJECTION_VERSION)
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
    print(json.dumps({"release_version": manifest["release_version"],
                      "status": manifest["status"],
                      "files_verified": len(manifest["files_sha256"]),
                      "isolated_import": bool(args.check_imports),
                      "inference_smoke": bool(args.backbone_snapshot)}, sort_keys=True))


if __name__ == "__main__":
    main()
