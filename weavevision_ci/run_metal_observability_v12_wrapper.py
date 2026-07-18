from __future__ import annotations

import json

import numpy as np

import run_metal_observability_v12 as audit

_original_dumps = json.dumps


def _numpy_json_default(value):
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _safe_dumps(obj, *args, **kwargs):
    kwargs.setdefault("default", _numpy_json_default)
    return _original_dumps(obj, *args, **kwargs)


audit.json.dumps = _safe_dumps

if __name__ == "__main__":
    audit.main()
