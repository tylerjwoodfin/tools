#!/bin/sh
echo "starting"

blocklist_file=$(cabinet -g path blocklist)
echo "blocklist_file = '${blocklist_file}'"

if [[ -z "${blocklist_file}" ]]; then
  echo "Error: blocklist_file (cabinet -g path blocklist) is empty"
  exit 1
fi

blocklist_domains=$(cat "${blocklist_file}")

for domain in $blocklist_domains; do
  echo "blocking ${domain}..."
  sudo pihole --wild "$domain"
done

echo "done"
