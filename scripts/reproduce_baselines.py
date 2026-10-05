"""Validate fresh-seed determinism against the previous report's measured results."""
import os
from pathlib import Path
import sys
import subprocess
import json
root=Path(__file__).resolve().parents[1]
os.environ['PYTHONPATH']=str(root/'backend')+os.pathsep+str(root)
os.environ.setdefault('ADMIN_PASSWORD','local-fixture-only-password')
from ml.core import ARTIFACTS
previous=json.loads((ARTIFACTS/'baselines.json').read_text())
subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root/'backend',check=True)
from app.seed import seed
seed()
from ml.baselines import train
current=train()
for key in ['data_hash','split','recommender','forecast','weights']:
    assert previous[key]==current[key],key
print('Fresh seed reproduces baseline hash, weights and all metrics',flush=True)
