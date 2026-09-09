#!/bin/bash
# Riempie la cache asset di Webots (R2025a) scaricando con curl gli asset
# che il downloader interno di Webots spesso fallisce
# ("Cannot download ... error code: 2: Connection closed" / 399).
# Nome file in cache = SHA1 dell'URL completo (verificato su R2025a).
# Uso: bash scripts/seed_webots_cache.sh [TAG_RELEASE]
# Esempio: bash scripts/seed_webots_cache.sh R2025a
set -u
TAG="${1:-R2025a}"
CACHE="$LOCALAPPDATA/Cyberbotics/Webots/cache/assets"
BASE="https://raw.githubusercontent.com/cyberbotics/webots/$TAG"
mkdir -p "$CACHE"
ok=0; fail=0
while IFS= read -r p; do
  [ -z "$p" ] && continue
  url="$BASE/$p"
  h=$(echo -n "$url" | sha1sum | cut -d' ' -f1)
  if [ -f "$CACHE/$h" ]; then echo "CACHED $p"; ok=$((ok+1)); continue; fi
  if curl -s -m 60 --retry 3 "$url" -o "$CACHE/$h"; then echo "GOT $p"; ok=$((ok+1));
  else echo "FAIL $p"; fail=$((fail+1)); rm -f "$CACHE/$h"; fi
done <<'ASSETS'
projects/robots/gctronic/e-puck/protos/textures/gctronic_logo.png
projects/robots/gctronic/e-puck/protos/textures/e-puck1_plate_base_color.jpg
projects/robots/gctronic/e-puck/protos/textures/e-puck1_plate_roughness.jpg
projects/robots/gctronic/e-puck/protos/textures/e-puck1_plate_metalness.jpg
projects/robots/gctronic/e-puck/protos/textures/e-puck1_plate_normal.jpg
projects/robots/gctronic/e-puck/protos/textures/e-puck1_plate_occlusion.jpg
projects/robots/gctronic/e-puck/protos/textures/e-puck1_turret_base_color.jpg
projects/robots/gctronic/e-puck/protos/textures/e-puck1_turret_roughness.jpg
projects/robots/gctronic/e-puck/protos/textures/e-puck1_turret_metalness.jpg
projects/robots/gctronic/e-puck/protos/textures/e-puck1_turret_normal.jpg
projects/robots/gctronic/e-puck/protos/textures/e-puck1_turret_occlusion.jpg
projects/robots/gctronic/e-puck/protos/textures/e-puck2_plate.jpg
projects/default/worlds/sounds/rotational_motor.wav
projects/appearances/protos/textures/copper/copper_base_color.jpg
projects/appearances/protos/textures/copper/copper_roughness.jpg
projects/appearances/protos/textures/copper/copper_metalness.jpg
projects/default/worlds/textures/cubic/mountains_right.jpg
projects/default/worlds/textures/cubic/mountains_right.hdr
ASSETS
echo "== ok:$ok fail:$fail total:$(ls "$CACHE" | wc -l)"
