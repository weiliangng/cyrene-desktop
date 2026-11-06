"""Cross-process launcher lock; the OS releases it on exit, crash, or reboot."""
from contextlib import contextmanager
import os
from pathlib import Path
import time


@contextmanager
def startup_lock(path, timeout=300):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b'0')
            handle.flush()
        deadline = time.monotonic() + timeout
        announced = False
        while True:
            handle.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise SystemExit('Another Cyrene launcher is still starting. Wait for it to finish and try again.')
                if not announced:
                    print('Another launcher is starting Cyrene; waiting for it to finish...', flush=True)
                    announced = True
                time.sleep(0.25)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
