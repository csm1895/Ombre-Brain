"""Path safety checks for Level 0 readonly tools."""

from pathlib import Path, PurePosixPath

from .allowlist import ALL_ALLOWED_PATHS

_SUSPICIOUS_NAME_PARTS = ("secret", "token", "key", "password", "credential")


def _has_forbidden_name(name: str) -> bool:
    lowered = name.lower()
    return lowered == ".env" or any(part in lowered for part in _SUSPICIOUS_NAME_PARTS)


def _looks_hidden(path_like: str) -> bool:
    pure = PurePosixPath(path_like)
    return any(part.startswith(".") for part in pure.parts if part not in ("", "."))


def ensure_safe_id(candidate: str) -> str:
    if not isinstance(candidate, str) or not candidate.strip():
        raise ValueError("invalid_id")
    cleaned = candidate.strip()
    pure = PurePosixPath(cleaned)
    if ".." in pure.parts:
        raise PermissionError("not_allowed")
    if _looks_hidden(cleaned):
        raise PermissionError("not_allowed")
    if _has_forbidden_name(pure.name):
        raise PermissionError("not_allowed")
    return cleaned


def ensure_allowed_path(path: Path) -> Path:
    if not isinstance(path, Path):
        path = Path(path)
    name = path.name
    if _has_forbidden_name(name):
        raise PermissionError("not_allowed")
    if any(part == ".." for part in path.parts):
        raise PermissionError("not_allowed")
    if any(part.startswith(".") for part in path.parts if part not in ("", ".") and part != path.anchor):
        raise PermissionError("not_allowed")
    try:
        resolved = path.resolve(strict=False)
    except OSError as exc:
        raise PermissionError("not_allowed") from exc
    if resolved not in ALL_ALLOWED_PATHS:
        raise PermissionError("not_allowed")
    return resolved
