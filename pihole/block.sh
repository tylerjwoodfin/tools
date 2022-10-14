#!/bin/sh
echo "starting"

blockDomains=$(cat /home/tyler/git/tools/pihole/blocklist)

echo "${blockDomains}"

for domain in $blockDomains; do
  echo "blocking..."
  sudo pihole --wild "$domain"
done

echo "done"
