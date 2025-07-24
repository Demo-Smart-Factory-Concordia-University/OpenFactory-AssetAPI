#!/bin/bash
set -e

# -----------------------------------------------------------------------------
# Script to deploy the virtual factory environment
#
# This script:
#   1. Starts virtual asset adapters using Docker Compose
#   2. Registers virtual devices with the OpenFactory backend
#
# Usage:
#   ./dev_tools/deploy_virtual_factory.sh
#
# Make sure:
#   - Kafka and ksqlDB are running (via `spinup`)
#   - You are inside the DevContainer environment (for access to openfactory-sdk)
# -----------------------------------------------------------------------------

echo "🚀 Deploying virtual assets via Docker Compose..."
docker compose -f dev_tools/virtual_factory/docker-compose.yml up -d

echo "✅ Virtual sensors started."

echo "🔧 Deploying virtual devices to OpenFactory..."
for workcenter_dir in dev_tools/virtual_factory/*/; do
  workcenter=$(basename "$workcenter_dir")
  echo "Deploying workcenter: $workcenter"
  openfactory-sdk device up "$workcenter_dir"
done

echo "✅ Virtual factory is now running."
