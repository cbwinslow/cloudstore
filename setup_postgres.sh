#!/bin/bash

# Backup original pg_hba.conf
sudo cp /etc/postgresql/17/main/pg_hba.conf /etc/postgresql/17/main/pg_hba.conf.backup

# Create new pg_hba.conf with peer authentication for local connections
sudo tee /etc/postgresql/17/main/pg_hba.conf > /dev/null << EOL
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# "local" is for Unix domain socket connections only
local   all             postgres                                peer
local   all             all                                     scram-sha-256
# IPv4 local connections:
host    all             all             127.0.0.1/32            scram-sha-256
# IPv6 local connections:
host    all             all             ::1/128                 scram-sha-256
EOL

# Set proper permissions
sudo chmod 640 /etc/postgresql/17/main/pg_hba.conf
sudo chown postgres:postgres /etc/postgresql/17/main/pg_hba.conf

# Restart PostgreSQL to apply changes
sudo systemctl restart postgresql

echo "PostgreSQL configuration updated. You can now run commands as postgres user."

