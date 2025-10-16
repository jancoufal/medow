#!/bin/sh

podman rm -f medow
podman rmi medow:1

podman build -t medow:1 .