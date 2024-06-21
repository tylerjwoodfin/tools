#!/usr/bin/env zsh

command -v mpv &>/dev/null || { echo "Error: mpv is not installed." && exit 1; }

declare -A urls=(
    ["study"]="https://www.youtube.com/watch?v=jfKfPfyJRdk"
    ["chill"]="https://www.youtube.com/watch?v=Z9D16KYgUJE"
    ["game"]="https://www.youtube.com/watch?v=akW7qWS_p-g"
)

get_message() {
    local key=$1
    local url=${urls[$key]}
    echo "Playing ${key} lofi - $url"
}

stations=(study chill game)
current_station_index=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Play/Stream lofi music audio, and nothing else
                          - Amberol (probably)

Options:
  -s, --study, relax      Play lofi radio beats to relax/study music.
  -c, --chill, sleep      Play lofi radio beats sleeps/chill music.
  -g, --game, synthwave   Play lofi synthwave radio beats to chill/game music.
  -r, --random            Play a random station URL (study, chill, game).
  -v, --video             Play with video (default: none).
  -h, --help              Display this help message.
EOF
}

set_station() { 
    station_name=${stations[$current_station_index]}
	url=${urls[$station_name]}
	message=$(get_message "$station_name")
	echo "$message"
}

set_station_based_on_time_of_the_day() {
    hour=$(date +%_H)
    if ((hour >= 22 && hour < 6)); then
        set_station "chill"
    elif ((hour >= 6 && hour < 12)); then
        set_station "study"
    else
        set_station "game"
    fi
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

open_browser_search() {
    search_query="24/7+Lofi+Stream"
    open_browser "https://www.youtube.com/results?search_query=$search_query"
}

create_input_conf() {
    cat <<EOF > /tmp/mpv_input.conf
n quit 42
b quit 43
q quit
EOF
}

play_stream() {
    local video=$1
    local url=$2
    echo "${messages[$station_name]}..."
    echo "Press 'n' to play the next stream"
    echo "Press 'b' to open the current stream in a browser"
    echo "Press 'q' to quit"

    create_input_conf

    if $video; then
        mpv --input-conf=/tmp/mpv_input.conf "$url"
    else
        mpv --no-video --input-conf=/tmp/mpv_input.conf "$url"
    fi
}

cleanup() {
    rm -f /tmp/mpv_input.conf
    echo -e "\nExiting..."
    exit 0
}

main() {
    trap cleanup SIGINT SIGTERM EXIT

    local video=false
    if [[ $# -eq 0 ]]; then
        set_station_based_on_time_of_the_day
    else
        while [[ $# -gt 0 ]]; do
            case $1 in
            -s | --study | relax | study)
                set_station "study"
                shift
                ;;
            -c | --chill | sleep | chill)
                set_station "chill"
                shift
                ;;
            -g | --game | synthwave | game)
                set_station "game"
                shift
                ;;
            -r | --random)
                random_station_name=$(shuf -n 1 -e "${!urls[@]}")
                set_station "$random_station_name"
                shift
                ;;
            -v | --video)
                video=true
                shift
                ;;
            -h | --help)
                usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1" >&2
                usage
                exit 1
                ;;
            esac
        done
    fi

    # Play streams in a loop
    while true; do
        station_name=${stations[$current_station_index]}
        url=${urls[$station_name]}
        play_stream "$video" "$url"
        exit_status=$?
        
        if [ $exit_status -eq 42 ]; then
            # User pressed 'n', move to next station
            current_station_index=$(( (current_station_index + 1) % ${#stations[@]} ))
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