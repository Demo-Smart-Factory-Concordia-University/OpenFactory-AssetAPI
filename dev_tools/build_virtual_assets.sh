#!/bin/bash
set -e

echo "🔧 Building virtual asset images..."

# Build the virtual temperature sensor
docker build -t virtual-temp-sensor ./dev_tools/virtual_assets/temp_sensor

# Future assets can go here:
# docker build -t virtual-pressure-sensor ./dev_tools/virtual_assets/pressure_sensor
# docker build -t virtual-vibration-sensor ./dev_tools/virtual_assets/vibration_sensor

echo "✅ All virtual asset images built."
