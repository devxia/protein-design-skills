"""Cross-platform subprocess helpers for long-running tool commands."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import Any, Optional, Union


# Keep the original function so test suites that monkeypatch subprocess.run
# retain their existing seam while callers migrate to run_process().
_ORIGINAL_SUBPROCESS_RUN = subprocess.run

# A child carrying this marker already belongs to a process group owned by an
# outer protein-design launcher. Nested runners must inherit that group instead
# of creating another session that job_manager can no longer cancel.
_MANAGED_PROCESS_GROUP_ENV = "PROTEIN_DESIGN_MANAGED_PROCESS_GROUP"
_TERMINATE_GRACE_SECONDS = 1.0


def _environment_with_group_marker(
    env: Optional[dict[str, str]],
) -> dict[str, str]:
    """Copy an environment and mark the child as part of a managed tree."""
    result = os.environ.copy() if env is None else dict(env)
    result[_MANAGED_PROCESS_GROUP_ENV] = "1"
    return result


def _in_managed_process_group() -> bool:
    """Return whether an outer launcher owns this POSIX process tree."""
    return os.name == "posix" and os.environ.get(_MANAGED_PROCESS_GROUP_ENV) == "1"


def process_group_popen_kwargs(**kwargs: Any) -> dict[str, Any]:
    """Return ``Popen`` kwargs for the one owner of a process tree.

    On POSIX the owner starts a session and marks its environment. Descendant
    :func:`run_process` calls see that marker and inherit the same group.
    """
    result = dict(kwargs)
    if os.name == "posix":
        result["start_new_session"] = True
        result["env"] = _environment_with_group_marker(result.get("env"))
    elif os.name == "nt":
        result["creationflags"] = result.get("creationflags", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    return result


def _popen_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible internal wrapper for process group kwargs."""
    return process_group_popen_kwargs(**kwargs)


def _posix_descendant_pids(pid: int) -> list[int]:
    """Return a parent-before-child snapshot of a POSIX process subtree."""
    try:
        result = _ORIGINAL_SUBPROCESS_RUN(
            ["ps", "-axo", "pid=,ppid="],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    children: dict[int, list[int]] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            child_pid, parent_pid = (int(part) for part in parts)
        except ValueError:
            continue
        children.setdefault(parent_pid, []).append(child_pid)

    descendants = []
    pending = list(children.get(pid, ()))
    while pending:
        child_pid = pending.pop(0)
        descendants.append(child_pid)
        pending.extend(children.get(child_pid, ()))
    return descendants


def _signal_posix_pids(pids: list[int], sig: int) -> None:
    """Signal known subtree members leaf-first, tolerating exit races."""
    for pid in reversed(pids):
        try:
            os.kill(pid, sig)
        except (OSError, AttributeError, TypeError, ValueError):
            pass


def _wait_for_posix_tree_exit(
    leader_pid: int,
    *,
    owns_process_group: bool,
    tracked_pids: list[int],
    timeout: float,
) -> bool:
    """Wait for an owned group or an inherited subtree to be confirmed dead."""
    deadline = time.monotonic() + timeout
    while True:
        if owns_process_group:
            alive = process_group_is_alive(
                leader_pid,
                fallback_to_process=False,
            )
            if alive is False:
                return True
        else:
            states = [process_is_alive(pid) for pid in tracked_pids]
            if states and all(state is False for state in states):
                return True

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.05, remaining))


def _terminate_process_tree(
    process: subprocess.Popen[str],
    *,
    owns_process_group: bool,
) -> list[int]:
    """Terminate a process tree and return POSIX PIDs tracked for escalation."""
    pid = process.pid
    if os.name == "posix":
        if owns_process_group:
            terminate_process_group(pid)
            return [pid]

        # The caller is a member of the outer group, so killpg would also kill
        # that caller. Snapshot only this subprocess's descendants before the
        # leader can exit and its children are reparented.
        tracked_pids = [pid, *_posix_descendant_pids(pid)]
        _signal_posix_pids(tracked_pids, signal.SIGTERM)
        return tracked_pids

    if os.name == "nt":
        # taskkill /T is the standard Python-free way to terminate descendants
        # when a Windows Job Object is not available to this process.
        try:
            _ORIGINAL_SUBPROCESS_RUN(
                ["taskkill", "/PID", str(pid), "/T"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return []
        except (OSError, subprocess.TimeoutExpired):
            pass

    try:
        process.terminate()
    except OSError:
        pass
    return []


def _kill_process_tree(
    process: subprocess.Popen[str],
    *,
    owns_process_group: bool,
    tracked_pids: Optional[list[int]] = None,
) -> None:
    """Forcefully terminate a process group after graceful shutdown fails."""
    pid = process.pid
    if os.name == "posix":
        if owns_process_group:
            terminate_process_group(pid, force=True)
        else:
            _signal_posix_pids(tracked_pids or [pid], signal.SIGKILL)
        return
    if os.name == "nt":
        try:
            _ORIGINAL_SUBPROCESS_RUN(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        process.kill()
    except OSError:
        pass


def run_process(
    args: list[str],
    *,
    timeout: Optional[float] = None,
    capture_output: bool = True,
    text: bool = True,
    env: Optional[dict[str, str]] = None,
    cwd: Optional[Union[str, os.PathLike[str]]] = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a command in an isolated process group.

    The return value has the same shape as :func:`subprocess.run`. On timeout
    the complete process tree is terminated before ``TimeoutExpired`` is
    raised, so callers retain their existing timeout handling.  Extra keyword
    arguments are accepted for compatibility with ``subprocess.run``.
    """
    # Preserve the old subprocess.run monkeypatch seam used by callers and
    # tests.  Normal execution always reaches Popen below, where process-group
    # isolation is applied.  Additional subprocess.run-compatible options are
    # forwarded through the compatibility path.
    if subprocess.run is not _ORIGINAL_SUBPROCESS_RUN:
        run_kwargs: dict[str, Any] = {
            "capture_output": capture_output,
            "text": text,
            "timeout": timeout,
            **kwargs,
        }
        if env is not None:
            run_kwargs["env"] = env
        if cwd is not None:
            run_kwargs["cwd"] = cwd
        return subprocess.run(args, **run_kwargs)

    popen_kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE if capture_output else None,
        "stderr": subprocess.PIPE if capture_output else None,
        "text": text,
        **kwargs,
    }
    if env is not None:
        popen_kwargs["env"] = env
    if cwd is not None:
        popen_kwargs["cwd"] = cwd

    owns_process_group = False
    if os.name == "posix":
        if _in_managed_process_group():
            # Preserve the marker even when a caller supplies a replacement
            # environment. Do not allow a nested start_new_session to split the
            # tree away from its outer owner.
            popen_kwargs.pop("start_new_session", None)
            if "env" in popen_kwargs:
                popen_kwargs["env"] = _environment_with_group_marker(
                    popen_kwargs["env"]
                )
        else:
            owns_process_group = True
            popen_kwargs = _popen_kwargs(popen_kwargs)
    elif os.name == "nt":
        # Preserve the existing Windows process-group and taskkill /T behavior.
        popen_kwargs = _popen_kwargs(popen_kwargs)

    process = subprocess.Popen(args, **popen_kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        tracked_pids = _terminate_process_tree(
            process,
            owns_process_group=owns_process_group,
        )
        if os.name == "posix" and not _wait_for_posix_tree_exit(
            process.pid,
            owns_process_group=owns_process_group,
            tracked_pids=tracked_pids,
            timeout=_TERMINATE_GRACE_SECONDS,
        ):
            # Do not rely on communicate() timing: the leader may exit and
            # close its pipes while an ignore-SIGTERM descendant remains.
            _kill_process_tree(
                process,
                owns_process_group=owns_process_group,
                tracked_pids=tracked_pids,
            )
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_process_tree(
                process,
                owns_process_group=owns_process_group,
                tracked_pids=tracked_pids,
            )
            stdout, stderr = process.communicate()
        timeout_error = subprocess.TimeoutExpired(
            args,
            timeout,
            output=stdout if stdout is not None else exc.output,
            stderr=stderr if stderr is not None else exc.stderr,
        )
        raise timeout_error from exc

    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def _windows_process_identity(pid: int) -> Optional[dict[str, str]]:
    """Return a Windows process creation timestamp using the Win32 API."""
    try:
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_process_times = kernel32.GetProcessTimes
        get_process_times.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
        ]
        get_process_times.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        # PROCESS_QUERY_LIMITED_INFORMATION works without elevated privileges
        # for ordinary processes on supported Windows versions.
        handle = open_process(0x1000, False, pid)
        if not handle:
            return None
        try:
            creation = FILETIME()
            exit_time = FILETIME()
            kernel_time = FILETIME()
            user_time = FILETIME()
            if not get_process_times(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            ):
                return None
            value = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            return {"kind": "windows_creation_filetime", "value": str(value)}
        finally:
            close_handle(handle)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _windows_process_is_alive(pid: int) -> Optional[bool]:
    """Check a Windows process without using ``os.kill(pid, 0)``.

    Python implements most Windows ``os.kill`` signals via TerminateProcess,
    so a Win32 query is required for a side-effect-free liveness check.
    """
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_exit_code = kernel32.GetExitCodeProcess
        get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit_code.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        handle = open_process(0x1000, False, pid)
        if not handle:
            # ERROR_INVALID_PARAMETER means there is no such PID.  Access
            # denied and other failures cannot safely be interpreted as dead.
            return False if ctypes.get_last_error() == 87 else None
        try:
            exit_code = wintypes.DWORD()
            if not get_exit_code(handle, ctypes.byref(exit_code)):
                return None
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            close_handle(handle)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def get_process_identity(pid: int) -> Optional[dict[str, str]]:
    """Return a stable, best-effort identity for a currently running process.

    The identity is based on process creation time rather than PID alone. It
    can therefore be persisted and compared before cancellation to avoid
    signalling an unrelated process after PID reuse.
    """
    if not isinstance(pid, int) or pid <= 0:
        return None

    if os.name == "nt":
        return _windows_process_identity(pid)

    if sys.platform.startswith("linux"):
        try:
            # The command name in /proc/<pid>/stat may contain spaces and ')',
            # so split after the final ')' before selecting field 22. The
            # resulting list begins at field 3, making starttime index 19.
            stat_path = os.path.join("/proc", str(pid), "stat")
            with open(stat_path, encoding="utf-8") as stat_file:
                raw = stat_file.read()
            command_end = raw.rfind(")")
            if command_end < 0:
                return None
            fields = raw[command_end + 2 :].split()
            if len(fields) > 19:
                return {"kind": "linux_proc_start_ticks", "value": fields[19]}
        except (OSError, ValueError):
            return None
        return None

    if os.name == "posix":
        try:
            result = _ORIGINAL_SUBPROCESS_RUN(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        value = result.stdout.strip() if result.returncode == 0 else ""
        if value:
            return {"kind": "posix_ps_lstart", "value": value}

    return None


def _posix_ps_liveness(pid: int, *, group: bool) -> Optional[bool]:
    """Use process states to distinguish live members from zombies."""
    command = (
        ["ps", "-axo", "pgid=,stat="]
        if group
        else ["ps", "-o", "stat=", "-p", str(pid)]
    )
    try:
        result = _ORIGINAL_SUBPROCESS_RUN(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    states = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if group:
            if len(parts) != 2:
                continue
            try:
                if int(parts[0]) != pid:
                    continue
            except ValueError:
                continue
            states.append(parts[1])
        elif parts:
            states.append(parts[0])
    # ps uses a leading Z for zombies. A group containing only zombies cannot
    # execute work and is considered terminated for cancellation purposes.
    return any(state and not state.startswith("Z") for state in states)


def process_is_alive(pid: int) -> Optional[bool]:
    """Return process liveness, or ``None`` when it cannot be confirmed."""
    if os.name == "nt":
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, AttributeError, TypeError, ValueError):
        return None
    if os.name == "posix":
        state_alive = _posix_ps_liveness(pid, group=False)
        if state_alive is not None:
            return state_alive
    return True


def process_group_is_alive(
    pid: int,
    *,
    fallback_to_process: bool = True,
) -> Optional[bool]:
    """Return whether an isolated process group is still alive.

    POSIX can probe the complete group. For legacy jobs that were not group
    leaders, ``fallback_to_process`` checks the tracked PID after a missing
    group. New isolated jobs disable that fallback because a lingering zombie
    or a recycled PID must not make a terminated group appear alive. Windows
    has no equivalent group query, so the tracked leader is checked instead.
    """
    if os.name == "posix":
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            if fallback_to_process:
                return process_is_alive(pid)
            return False
        except PermissionError:
            return True
        except (OSError, AttributeError, TypeError, ValueError):
            return None
        state_alive = _posix_ps_liveness(pid, group=True)
        if state_alive is not None:
            return state_alive
        return True
    return process_is_alive(pid)


def terminate_process_group(pid: int, *, force: bool = False) -> bool:
    """Terminate a previously isolated process group by its leader PID.

    The PID is expected to be the leader of a session created by
    :func:`run_process`. If the group cannot be addressed, fall back to the
    leader itself so this helper is also safe for callers tracking an older
    process that was not started with group isolation. Return ``True`` only
    when a termination request was successfully issued.
    """
    sig = signal.SIGKILL if force else signal.SIGTERM
    if os.name == "posix":
        try:
            os.killpg(pid, sig)
            return True
        except ProcessLookupError:
            try:
                os.kill(pid, sig)
            except (OSError, AttributeError, TypeError, ValueError):
                return False
            return True
        except PermissionError:
            return False
        except (OSError, AttributeError, TypeError, ValueError):
            try:
                os.kill(pid, sig)
            except (OSError, AttributeError, TypeError, ValueError):
                return False
            return True
    if os.name == "nt":
        command = ["taskkill", "/PID", str(pid), "/T"]
        if force:
            command.append("/F")
        try:
            result = _ORIGINAL_SUBPROCESS_RUN(
                command, capture_output=True, text=True, timeout=10, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    try:
        os.kill(pid, sig)
    except (OSError, AttributeError, TypeError, ValueError):
        return False
    return True
