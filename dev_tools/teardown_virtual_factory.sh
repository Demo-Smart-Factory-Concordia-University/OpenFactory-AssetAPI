#!/bin/bash
set -e

# -----------------------------------------------------------------------------
# Script to tear down the virtual factory environment
#
# This script:
#   1. Removes virtual devices from the OpenFactory backend
#   2. Stops and removes virtual asset adapter containers
#
# Usage:
#   ./dev_tools/teardown_virtual_factory.sh
#
# Make sure:
#   - You are inside the DevContainer environment (for access to openfactory-sdk)
# -----------------------------------------------------------------------------

echo "🧹 Tearing down virtual factory..."

echo "🗑️ Removing OpenFactory devices..."
for workcenter_dir in dev_tools/virtual_factory/*/; do
  workcenter=$(basename "$workcenter_dir")
  echo "Removing workcenter: $workcenter"
  openfactory-sdk device down "$workcenter_dir"
done

echo "⛔ Stopping and removing virtual sensors..."
docker compose -f dev_tools/virtual_factory/docker-compose.yml down

echo "✅ Virtual factory has been torn down."
