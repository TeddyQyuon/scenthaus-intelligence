"""Explicit human rollback; target files must still match their manifest."""

import argparse
from app.config import settings
from app.ml.versions import activate
from app.database import SessionLocal
from app.models import AuditLog


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    args = parser.parse_args()
    activate(settings.artifact_dir, args.version)
    with SessionLocal() as db:
        db.add(
            AuditLog(
                actor="operator-cli",
                action="model_rollback",
                detail={"version": args.version},
            )
        )
        db.commit()
    print("Activated", args.version)


if __name__ == "__main__":
    main()
