#!/bin/sh
blockDomains=$(cat /home/tyler/git/tools/pihole/blocklist)

for domain in $blockDomains; do
  sudo pihole --wild -d $domain
done
