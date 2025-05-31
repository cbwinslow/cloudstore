#!/bin/bash

# Exit on error
set -e

echo "Setting up PostgreSQL users..."

# Default passwords - consider changing these to more secure passwords!
POSTGRES_PASSWORD="PostgresAdmin123!"
CBWINSLOW_PASSWORD="Temp1234!"

# Connect as postgres user and set up passwords
echo "Configuring postgres user..."
sudo -u postgres psql -c "ALTER USER postgres PASSWORD '$POSTGRES_PASSWORD';"

echo "Creating cbwinslow superuser..."
sudo -u postgres psql -c "CREATE USER cbwinslow WITH SUPERUSER PASSWORD '$CBWINSLOW_PASSWORD';"

echo "Creating cloudstore database..."
sudo -u postgres psql -c "CREATE DATABASE cloudstore OWNER cbwinslow;"

# Now restore the original pg_hba.conf if backup exists
if [ -f "/etc/postgresql/17/main/pg_hba.conf.backup" ]; then
  echo "Restoring original pg_hba.conf..."
  sudo mv /etc/postgresql/17/main/pg_hba.conf.backup /etc/postgresql/17/main/pg_hba.conf
  
  # Restart PostgreSQL to apply changes
  echo "Restarting PostgreSQL service..."
  sudo systemctl restart postgresql
else
  echo "No pg_hba.conf.backup found, skipping restore."
fi

echo "PostgreSQL users configured successfully!"
echo "postgres password: $POSTGRES_PASSWORD"
echo "cbwinslow password: $CBWINSLOW_PASSWORD"
echo "Database 'cloudstore' created and owned by 'cbwinslow'"
echo ""
echo "IMPORTANT: Make sure to update your .env file with these credentials."

