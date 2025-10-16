#!/bin/sh

podman run -d \
  --name medow \
  -v /home/opc/medow-data/config.yaml:/app/config.yaml:ro,Z \
  -v /home/opc/medow-data/sql:/app/sql:rw,Z \
  -v /home/opc/medow-data/downloads:/app/static/downloads:rw,Z \
  -p 80:8000 \
  localhost/medow:1
