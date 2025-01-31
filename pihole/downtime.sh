#!/bin/zsh

# Function to check if the script is being run from Python, crontab, or atd
check_parent_process() {
    local parent_process grandparent_process

    # Get the parent and grandparent process names
    parent_process=$(ps -o comm= -p $PPID)
    grandparent_process=$(ps -o comm= -p $(ps -o ppid= -p $PPID) 2>/dev/null)

    # Check if the parent or grandparent process matches the criteria
    case $parent_process in
        cron|python*|atd)
            return 0
            ;;
    esac

    case $grandparent_process in
        cron|python*|atd)
            return 0
            ;;
    esac

    return 1
}

# Function to clean up scheduled at jobs
cleanup_scheduled_jobs() {
    local script_path=$0
    local mode=$2

    # List all pending at jobs
    atq | while read job_number rest; do
        # Check if this job contains our script and the reblock command
        at -c "$job_number" | grep -q "$script_path.*block.*$mode" && {
            atrm "$job_number"
            /home/tyler/.local/bin/cabinet --log "Removed scheduled job #$job_number for $mode"
        }
    done
}

# Check if the script is being run from Python, crontab, or through subprocess
parent_process=$(check_parent_process)
if [ $? -ne 0 ] && [ "1" == "block" ]; then
    echo "This script can only be run from a Python script or crontab."
    exit 1
fi

if [[ -z "$2" ]]; then
  echo "Error: Missing argument. Please provide the second argument."
  exit 1
fi

echo "starting"

# If running in allow mode from crontab, clean up scheduled jobs
if [[ "$1" == "allow" && "$parent_process" == "cron" ]]; then
    echo "Cleaning up scheduled jobs..."
    cleanup_scheduled_jobs "$@"
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

# Properly read lines into an array
blocklist_domains=("${(@f)$(cat "${blocklist_file}")}")

verify_command=(/usr/local/bin/pihole -q)
if [[ "$1" == "allow" ]]; then
    pihole_command=(/usr/local/bin/pihole --wild -d)
else
    # block
    pihole_command=(/usr/local/bin/pihole --wild)
fi

max_retries=3
failed_domains=()

# Process all domains first
for domain in $blocklist_domains; do
    echo "${pihole_command[@]} $domain"
    "${pihole_command[@]}" "$domain"
done

# Parallel verification using xargs
verify_results=$(echo "$blocklist_domains" | xargs -P 10 -n 1 "${verify_command[@]}")

failed_domains=()
for domain in $blocklist_domains; do
    result=$("${verify_command[@]}" "$domain")

    # Unblocking case: If `allow` is used, check if the domain is still blocked
    if [[ "$1" == "allow" ]]; then
        if [[ "$result" == *"Match found in exact whitelist"* || "$result" == *"No results found"* ]]; then
            echo "✅ $domain is correctly unblocked."
        else
            # Make sure the match is for the exact domain, not a subdomain
            if echo "$result" | grep -qE "Match found in.*\b$domain\b"; then
                echo "❌ $domain is still blocked, adding to failed_domains"
                failed_domains+=("$domain")
            else
                echo "✅ $domain is not blocked."
            fi
        fi

    # Blocking case: If `block` is used, check if the domain is still missing from blocklist
    elif [[ "$1" == "block" ]]; then
        if [[ "$result" == *"Match found in exact blacklist"* || "$result" == *"Match found in"* ]]; then
            # Ensure the match is for the exact domain
            if echo "$result" | grep -qE "Match found in.*\b$domain\b"; then
                echo "✅ $domain is correctly blocked."
            else
                echo "✅ $domain is not blocked."
            fi
        else
            echo "❌ $domain is not in the blocklist, adding to failed_domains"
            failed_domains+=("$domain")
        fi
    fi
done

# Retry failed domains (Parallelized)
for attempt in {1..$max_retries}; do
    [[ ${#failed_domains[@]} -eq 0 ]] && break
    
    echo "Retrying failed domains (Attempt $attempt)..."
    temp_failed=()
    
    # Run commands in parallel
    echo "${failed_domains[@]}" | xargs -P 10 -n 1 "${pihole_command[@]}"
    
    verify_results=$(echo "${failed_domains[@]}" | xargs -P 10 -n 1 "${verify_command[@]}")
    
    while IFS= read -r domain; do
        result=$(echo "$verify_results" | grep "$domain")

        if [[ "$1" == "allow" && -z "$result" ]]; then
            temp_failed+=("$domain")
        elif [[ "$1" == "block" && ( "$result" != *"$domain"* && "$result" != *"Match found in"* ) ]]; then
            temp_failed+=("$domain")
        fi
    done <<< "${failed_domains[@]}"

    failed_domains=("${temp_failed[@]}")
done

# Logging results
if [[ ${#failed_domains[@]} -eq 0 ]]; then
    /home/tyler/.local/bin/cabinet --log "All domains successfully processed."
else
    for domain in "${failed_domains[@]}"; do
        /home/tyler/.local/bin/cabinet --log "Failed to process domain $domain after $max_retries attempts" --level "error"
    done
fi

echo "done"