"""Small deterministic artifacts and atomic cache writes."""
import hashlib
import json
import os
import tempfile
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".partial-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def write_jsonl(path, rows):
    atomic_write(path, "".join(canonical(row) + "\n" for row in rows))


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
