#!/bin/sh
echo "starting"

blocklist_file=$(/home/tyler/.local/bin/cabinet -g path blocklist)
echo "blocklist_file = '${blocklist_file}'"

if [[ -z "${blocklist_file}" ]]; then
  echo "Error: blocklist_file (cabinet -g path blocklist) is empty"
  exit 1
fi

blocklist_domains=$(cat "${blocklist_file}")

if [[ "$1" == "allow" ]]; then
  pihole_command="sudo pihole --wild -d"
else
  pihole_command="sudo pihole --wild"
fi

for domain in $blocklist_domains; do
  echo "${pihole_command} ${domain}"
  ${pihole_command} "$domain"
done

echo "done"