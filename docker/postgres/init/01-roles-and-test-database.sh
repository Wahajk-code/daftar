#!/bin/sh
# Runs once, when the data volume is first created.
# daftar      the owner role (POSTGRES_USER): runs migrations and creates scratch databases for tests.
# daftar_app  the application role: no schema changes; audit_events is insert and select only (set by the migrations).
# daftar_test a second database so tests never touch development data.
set -e

psql -v ON_ERROR_STOP=1 -v app_password="$APP_DB_PASSWORD" --username "$POSTGRES_USER" --dbname postgres <<'SQL'
CREATE ROLE daftar_app LOGIN PASSWORD :'app_password';
CREATE DATABASE daftar_test OWNER daftar;
SQL
