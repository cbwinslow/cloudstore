#!/bin/bash

# Script to securely update IP Burger proxy credentials in .env file
# This script avoids exposing credentials in command history

# Set temporary environment variables for proxy credentials
# These are from the IP Burger configuration provided
export IPBURGER_HOST="96-44-188-194.ip.ipb.cloud"
export IPBURGER_PORT="9443"
export IPBURGER_USERNAME="BMm0Rr"
export IPBURGER_PASSWORD="WM2yu8Tw"

# Backup the current .env file
cp .env .env.backup

# Update the .env file with the new credentials
sed -i "s|PROXY_PROVIDER=.*|PROXY_PROVIDER=ipburger|g" .env
sed -i "s|PROXY_API_KEY=.*|PROXY_API_KEY=${IPBURGER_USERNAME}:${IPBURGER_PASSWORD}|g" .env

# Add or update proxy-specific settings
if grep -q "PROXY_HOST=" .env; then
    sed -i "s|PROXY_HOST=.*|PROXY_HOST=${IPBURGER_HOST}|g" .env
else
    echo "PROXY_HOST=${IPBURGER_HOST}" >> .env
fi

if grep -q "PROXY_PORT=" .env; then
    sed -i "s|PROXY_PORT=.*|PROXY_PORT=${IPBURGER_PORT}|g" .env
else
    echo "PROXY_PORT=${IPBURGER_PORT}" >> .env
fi

if grep -q "PROXY_USERNAME=" .env; then
    sed -i "s|PROXY_USERNAME=.*|PROXY_USERNAME=${IPBURGER_USERNAME}|g" .env
else
    echo "PROXY_USERNAME=${IPBURGER_USERNAME}" >> .env
fi

if grep -q "PROXY_PASSWORD=" .env; then
    sed -i "s|PROXY_PASSWORD=.*|PROXY_PASSWORD=${IPBURGER_PASSWORD}|g" .env
else
    echo "PROXY_PASSWORD=${IPBURGER_PASSWORD}" >> .env
fi

# Enable proxy for all sites that might need it
sed -i "s|PROXY_ENABLED=.*|PROXY_ENABLED=true|g" .env
sed -i "s|EBAY_PROXY_ENABLED=.*|EBAY_PROXY_ENABLED=true|g" .env
sed -i "s|AMAZON_PROXY_ENABLED=.*|AMAZON_PROXY_ENABLED=true|g" .env
sed -i "s|SHOPGOODWILL_PROXY_ENABLED=.*|SHOPGOODWILL_PROXY_ENABLED=true|g" .env

echo "Proxy credentials updated successfully in .env file."
echo "A backup of the original .env file was created at .env.backup"

# Clear the environment variables for security
unset IPBURGER_HOST
unset IPBURGER_PORT
unset IPBURGER_USERNAME
unset IPBURGER_PASSWORD

# Set proper permissions on .env file
chmod 600 .env

