"""Private filesystem object store for a single demo host.

All writers must use this adapter: its lock and generation checks coordinate
the API and ingestion worker on the same filesystem.
"""

import os
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from google.api_core.exceptions import NotFound, PreconditionFailed

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class LocalBucket:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.name = "local-private"

    @contextmanager
    def locked(self):
        with (self.root / ".lock").open("a+b") as lock:
            if os.name == "nt":
                if os.fstat(lock.fileno()).st_size == 0:
                    lock.write(b"\0")
                    lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def blob(self, name):
        path = PurePosixPath(name)
        if (
            not name
            or path.is_absolute()
            or any(p in {".", ".."} or p.startswith(".") for p in path.parts)
        ):
            raise ValueError("Invalid object name")
        target = (self.root / str(path)).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Invalid object path")
        return LocalBlob(self, str(path), target)

    def list_blobs(self, prefix="", max_results=None, **kwargs):
        results = []
        with self.locked():
            for path in self.root.rglob("*"):
                if not path.is_file() or path.is_symlink() or path.name.startswith("."):
                    continue
                name = path.relative_to(self.root).as_posix()
                if name.startswith(prefix):
                    blob = self.blob(name)
                    blob._reload()
                    results.append(blob)
                    if max_results and len(results) >= max_results:
                        break
        return iter(results)


class LocalBlob:
    def __init__(self, bucket, name, path):
        self.bucket, self.name, self.path = bucket, name, path
        self.generation = self.size = self.time_created = None

    def _reload(self):
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            raise NotFound("Object not found") from None
        self.generation, self.size = (stat.st_ino << 64) | stat.st_mtime_ns, stat.st_size
        self.time_created = datetime.fromtimestamp(stat.st_mtime, timezone.utc)

    def reload(self, **kwargs):
        with self.bucket.locked():
            self._reload()

    def _check(self, match):
        if match is None:
            return
        try:
            stat = self.path.stat()
            generation = (stat.st_ino << 64) | stat.st_mtime_ns
        except FileNotFoundError:
            generation = 0
        if generation != match:
            raise PreconditionFailed("Object generation changed")

    def _write(self, reader, match):
        with self.bucket.locked():
            self._check(match)
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".upload-", dir=self.path.parent)
            try:
                with os.fdopen(fd, "wb") as out:
                    shutil.copyfileobj(reader, out)
                os.replace(tmp, self.path)
                self._reload()
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)

    def upload_from_filename(self, filename, if_generation_match=None, **kwargs):
        with open(filename, "rb") as source:
            self._write(source, if_generation_match)

    def upload_from_string(self, data, if_generation_match=None, **kwargs):
        from io import BytesIO

        self._write(
            BytesIO(data.encode("utf-8") if isinstance(data, str) else data), if_generation_match
        )

    def download_to_filename(self, filename, if_generation_match=None, **kwargs):
        with self.bucket.locked():
            self._check(if_generation_match)
            try:
                shutil.copyfile(self.path, filename)
            except FileNotFoundError:
                raise NotFound("Object not found") from None

    def delete(self, if_generation_match=None, **kwargs):
        with self.bucket.locked():
            self._check(if_generation_match)
            try:
                self.path.unlink()
            except FileNotFoundError:
                raise NotFound("Object not found") from None
