"""Process-held file locks preventing duplicate desktop/API instances."""
from __future__ import annotations

from pathlib import Path


class SingleInstanceLock:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = path.open("a+b")
        if path.stat().st_size == 0:
            self._stream.write(b"0")
            self._stream.flush()
        self._stream.seek(0)
        try:
            if __import__("os").name == "nt":
                import msvcrt
                msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as error:
            self._stream.close()
            raise RuntimeError(f"TreeCut 已经有一个 {path.stem} 实例正在运行") from error

    def close(self) -> None:
        if self._stream.closed:
            return
        self._stream.seek(0)
        try:
            if __import__("os").name == "nt":
                import msvcrt
                msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
        finally:
            self._stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
