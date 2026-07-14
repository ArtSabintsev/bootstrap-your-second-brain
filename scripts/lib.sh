#!/usr/bin/env bash
# Shared helpers for brain scripts. Source from other scripts:
#   ROOT=...; # shellcheck source=lib.sh
#   source "$ROOT/scripts/lib.sh"
#
# Expects ROOT to be set to the vault root before sourcing.

brain_py() {
  if [[ -x "$ROOT/.venv/bin/python3" ]]; then
    "$ROOT/.venv/bin/python3" "$@"
  else
    python3 "$@"
  fi
}

# Current local branch (master on this template repo, main on many forks).
brain_git_branch() {
  git -C "$ROOT" symbolic-ref --short HEAD 2>/dev/null \
    || git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null \
    || echo "master"
}

brain_git_pull() {
  local branch
  branch="$(brain_git_branch)"
  git -C "$ROOT" pull --rebase --autostash "origin" "$branch"
}

brain_git_push() {
  local branch
  branch="$(brain_git_branch)"
  git -C "$ROOT" push "origin" "$branch"
}

# True if config.sources.<key> is enabled (default true when missing).
brain_source_enabled() {
  local key="$1"
  local v
  v="$(brain_py "$ROOT/scripts/config.py" "sources.$key" 2>/dev/null || echo true)"
  case "$v" in
    true|True|TRUE|1|yes|Yes|YES) return 0 ;;
    false|False|FALSE|0|no|No|NO|null|None|"") return 1 ;;
    *) return 0 ;;
  esac
}
