#!/bin/bash

mkdir -p /var/log/postgresql/
chown postgres:postgres /var/log/postgresql/

cat > /etc/postgresql.conf << EOF
listen_addresses = '*'
port = 5432
archive_mode = on
archive_command = 'cp %p /oracle/pg_data/archive/%f'
max_wal_senders = 10
wal_level = replica
wal_log_hints = on
log_replication_commands = on
EOF

cat > /etc/postgresql/pg_hba.conf << EOF
local all ${POSTGRES_USER} peer
host  all all 0.0.0.0/0 password
host  replication ${DB_REPL_USER} ${DB_REPL_HOST} trust
EOF

docker-entrypoint.sh "$@"
