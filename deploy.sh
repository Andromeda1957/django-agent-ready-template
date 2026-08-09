#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-webapp}"
REMOTE_HOST="${REMOTE_HOST:-root@example.com}"
REMOTE_USER="${REMOTE_USER:-webapp_user}"
REMOTE_DIR="${REMOTE_DIR:-/home/webapp_user/app}"
APP_DOMAIN="${APP_DOMAIN:-example.com}"
RELEASE_ID="${RELEASE_ID:-$(git rev-parse HEAD)}"
IMPORT_LINTER_CMD="${IMPORT_LINTER_CMD:-lint-imports}"

[[ "$APP_NAME" =~ ^[a-z][a-z0-9_-]{1,39}$ ]] || {
    echo "ERROR: APP_NAME contains unsupported characters." >&2; exit 2;
}
[[ "$REMOTE_HOST" =~ ^[A-Za-z0-9_.@-]+$ ]] || {
    echo "ERROR: REMOTE_HOST contains unsupported characters." >&2; exit 2;
}
[[ "$REMOTE_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || {
    echo "ERROR: REMOTE_USER contains unsupported characters." >&2; exit 2;
}
[[ "$REMOTE_DIR" =~ ^/[A-Za-z0-9_./-]+$ ]] || {
    echo "ERROR: REMOTE_DIR must be a simple absolute path." >&2; exit 2;
}
[[ "$APP_DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || {
    echo "ERROR: APP_DOMAIN contains unsupported characters." >&2; exit 2;
}
[[ "$RELEASE_ID" =~ ^[A-Fa-f0-9]{7,64}$ ]] || {
    echo "ERROR: RELEASE_ID must be a Git commit identifier." >&2; exit 2;
}
command -v ansible-playbook >/dev/null || {
    echo "ERROR: ansible-playbook is required on the deployment runner." >&2; exit 2;
}
command -v gio >/dev/null || {
    echo "ERROR: gio is required for recoverable temporary-file cleanup." >&2; exit 2;
}

echo "Checking release gates..."
ruff check .
"$IMPORT_LINTER_CMD"
python3 tools/check_security_patterns.py
python3 manage.py test web

archive="$(mktemp "$PWD/.deploy-artifact.${APP_NAME}.XXXXXX.tar.gz")"
cleanup() { gio trash -- "$archive"; }
trap cleanup EXIT

tar --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='web/tests' --exclude='web/tests/*' \
    -czf "$archive" \
    config web static manage.py requirements.txt constraints.txt \
    "${APP_NAME}.service" \
    "${APP_NAME}-health-monitor.service" \
    "${APP_NAME}-health-monitor.timer" \
    "${APP_NAME}_nginx"

ssh_host="$REMOTE_HOST"
ansible_user_args=()
if [[ "$REMOTE_HOST" == *@* ]]; then
    ansible_user_args=(-u "${REMOTE_HOST%%@*}")
    ssh_host="${REMOTE_HOST#*@}"
fi

export APP_NAME REMOTE_USER REMOTE_DIR APP_DOMAIN RELEASE_ID
export RELEASE_ARTIFACT="$archive"
export ANSIBLE_HOST_KEY_CHECKING=True

ansible-playbook \
    -i "${ssh_host}," \
    "${ansible_user_args[@]}" \
    ops/ansible/deploy.yml

echo "Deployment complete for release $RELEASE_ID."
