#!/usr/bin/env zsh
command -v mpv &>/dev/null || { echo "Error: mpv is not installed." && exit 1; }

lofi_json=$($HOME/.local/bin/cabinet -g lofi)

declare -A urls
while IFS="=" read -r key value; do
    urls[$key]=$value
done < <(echo "$lofi_json" | jq -r 'to_entries | .[] | "\(.key)=\(.value)"')

stations=(study chill game)
current_station_index=1

set_station() { 
    station_name=${stations[$current_station_index]}
	url=${urls[$station_name]}
}

open_browser() {
    local url=$1
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "$url"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        xdg-open "$url"
    else
        echo "Unsupported OS. Please open a browser and go to: $url"
    fi
}

create_input_conf() {
    cat <<EOF > /tmp/mpv_input.conf
n quit 42
b quit 43
q quit
EOF
}

play_stream() {
    local url=$2
    echo "Playing ${station_name} - $url"
    echo "'n' - next'"
    echo "'b' - open in browser"
    echo "'q' - quit"

    create_input_conf

    mpv --no-video --really-quiet --input-conf=/tmp/mpv_input.conf "$url"
}

cleanup() {
    rm -f /tmp/mpv_input.conf
    echo -e "\nExiting..."
    exit 0
}

main() {
    trap cleanup SIGINT SIGTERM EXIT

    local video=false
    set_station "study"

    # Play streams in a loop
    while true; do
        station_name=${stations[$current_station_index]}
        url=${urls[$station_name]}
        play_stream "$video" "$url"
        exit_status=$?
        
        if [ $exit_status -eq 42 ]; then
            # User pressed 'n', move to next station
            echo "\n"
            current_station_index=$(( (current_station_index + 1) % ${#stations[@]} + 1))
        elif [ $exit_status -eq 43 ]; then
            # User pressed 'b', open in browser
            open_browser "$url"
            # Don't change the station, replay the same one
        elif [ $exit_status -eq 0 ]; then
            # Normal exit (user pressed 'q')
            break
        else
            # Stream failed, try next
            echo "Failed to play $station_name stream. Trying next..."
            current_station_index=$(( (current_station_index + 1) % ${#stations[@]} ))
        fi
    done
}

main "$@"