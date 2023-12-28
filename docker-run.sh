docker run \
  -p 5000:5000 \
  --name medow-docker-dev \
  --mount type=bind,source="$(pwd)"/sql/,target=/app/mnt/sql \
  --mount type=bind,source="$(pwd)"/yt_dl/,target=/app/mnt/yt_dl \
  medow-docker:latest
