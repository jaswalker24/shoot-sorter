#!/bin/bash
# usage:
#   ~/shoot-sorter/tag <folder> --profile motorsport|gig|kyoto [--sample N] [--apply]      (tagger)
#   ~/shoot-sorter/tag index|search|ocr|sharpness|bursts|rank|captions|journal|ask|faces|name-person|schedule|scene|camera ...   (features)
HOME_LOCAL="${SHOOT_SORTER_HOME:-$HOME/shoot-sorter}"
"$HOME_LOCAL/start-ollama.sh" >/dev/null
case "$1" in
  index|search|ocr|sharpness|bursts|rank|captions|journal|ask|faces|name-person|schedule|scene|camera)
    exec nice -n 10 "$HOME_LOCAL/venv/bin/python" "$HOME_LOCAL/features.py" "$@" ;;
  *)
    exec nice -n 10 "$HOME_LOCAL/venv/bin/python" "$HOME_LOCAL/tagger.py" "$@" ;;
esac
