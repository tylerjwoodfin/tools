#!/bin/sh
echo "starting"

if [[ -z "$2" ]]; then
  echo "Error: Missing argument. Please provide the second argument."
  exit 1
fi

home_directory=$(eval echo ~$USER)

# $2 can be 'afternoon' or 'overnight', etc. to read the corresponding property
blocklist_file=$(/home/tyler/.local/bin/cabinet -g path blocklist "$2")

# Replace $HOME and ~ with the actual home directory path
blocklist_file=$(echo "${blocklist_file}" | sed "s|~|$home_directory|g" | sed "s|\$HOME|$home_directory|g")

echo "blocklist_file = '${blocklist_file}'"

if [[ -z "${blocklist_file}" ]]; then
  echo "Error: blocklist_file (cabinet -g path blocklist $2) is empty"
  exit 1
fi

blocklist_domains=$(cat "${blocklist_file}")

if [[ "$1" == "allow" ]]; then
  pihole_command="/usr/local/bin/pihole --wild -d"
else
  pihole_command="/usr/local/bin/pihole --wild"
fi

for domain in $blocklist_domains; do
  echo "${pihole_command} ${domain}"
  ${pihole_command} "$domain"
done

echo "done"

