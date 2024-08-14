#!/bin/zsh

# Function to check if the script is being run from Python, crontab, or through subprocess
check_parent_process() {
    local parent_process=$(ps -o comm= -p $PPID)
    local grandparent_process=$(ps -o comm= -p $(ps -o ppid= -p $PPID) 2>/dev/null)

    if [[ $parent_process == "cron" || $grandparent_process == "cron" ]]; then
        return 0
    elif [[ $parent_process == "python"* ]]; then
        return 0
    else
        return 1
    fi
}


# Check if the script is being run from Python, crontab, or through subprocess
if ! check_parent_process; then
    echo "This script can only be run from a Python script or crontab."
    exit 1
fi

if [[ -z "$2" ]]; then
  echo "Error: Missing argument. Please provide the second argument."
  exit 1
fi

echo "starting"

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

# Properly read lines into an array
blocklist_domains=("${(@f)$(cat "${blocklist_file}")}")

if [[ "$1" == "allow" ]]; then
    pihole_command=(/usr/local/bin/pihole --wild -d)
else
    pihole_command=(/usr/local/bin/pihole --wild)
fi

for domain in $blocklist_domains; do
    echo "${pihole_command[@]} $domain"
    "${pihole_command[@]}" "$domain"
done

echo "done"

