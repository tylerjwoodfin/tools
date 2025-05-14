#!/bin/zsh

# Usage:
#   find_largest_files.zsh <directory> [count]
# 
# Description:
#   Lists the largest files under the specified directory.
#   <directory> - Directory to search in (required)
#   [count]     - Number of results to display (optional, default: 20)

if [[ -z "$1" ]]; then
  echo "Usage: $0 <directory> [count]"
  exit 1
fi

DIR="$1"
COUNT="${2:-20}"

echo "Scanning $DIR for largest files..."
sudo find "$DIR" -type f -printf '%s %p\n' 2>/dev/null | \
  sort -nr | \
  head -n "$COUNT" | \
  awk '{ printf("%10d MB  %s\n", $1/1024/1024, $2) }'

