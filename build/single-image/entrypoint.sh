#!/bin/bash
set -e

# Shellcheck source=runtime/functions
source "${APP_HOME}/functions"

[[ ${DEBUG} == true ]] && set -x

# Export params

export POSTGRES_USER=${PG_USER}
export PG_PASSWORD=${POSTGRES_PASSWORD}

export MINIO_ROOT_USER=${MINIO_ACCESS_KEY}
export MINIO_ROOT_PASSWORD=${MINIO_SECRET_KEY}

########################################
# POSTGRES & MINIO: prepare
########################################
create_datadir
create_certdir
create_logdir
create_rundir

########################################
# POSTGRES: launch
########################################
set_resolvconf_perms

configure_postgresql

echo "Starting PostgreSQL ${PG_VERSION}..."
exec start-stop-daemon --start --chuid "${PG_USER}:${PG_USER}" --exec "${PG_BINDIR}/postgres" -- -D "${PG_DATADIR}" &

########################################
# MINIO: launch
########################################
if [ ! -z ${MINIO_CERTDIR} ]; then
  MINIO_CERT_COMAND="--certs-dir ${MINIO_CERTDIR}"
  export MINIO_SECURE="true"
fi
MINIO_PARAMS="server ${MINIO_DATADIR} --address :9000 --console-address :9001 ${MINIO_CERT_COMAND}"
echo "Starting MINIO ${MINIO_RELEASE} with params ${MINIO_PARAMS}..."
exec start-stop-daemon --start --chuid "${MINIO_USER}:${MINIO_USER}" --exec "${MINIO_BINARY}" -- ${MINIO_PARAMS} &

if [ "${START_SERVICES}" = "true" ]; then

  ########################################
  # UI: launch
  ########################################
  echo "Starting Box UI..."
  exec start-stop-daemon --start --chuid "${BOT_UI_USER}:${BOT_UI_USER}" --exec "${APP_HOME}/app" -- ui 1 &

  # ########################################
  # # TG: launch
  # ########################################
  echo "Starting Box TG..."
  exec start-stop-daemon --start --chuid "${BOT_TG_USER}:${BOT_TG_USER}" --exec "${APP_HOME}/app" -- bot 3 &
fi

while :; do
  sleep 100
  echo 'Main process is still alive!'
done