#!/bin/bash
# run_manual_update.sh
# Safely run the database update script inside the Docker container
# to ensure all dependencies (like pandas) are correctly available.

echo "Running populate_v2.py inside the investing-app Docker container..."
docker exec -it investing-app python3 populate_v2.py
