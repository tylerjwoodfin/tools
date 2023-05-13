#!/usr/bin/env bash

command -v mpv &>/dev/null || { echo "Error: mpv is not installed." && exit 1; }

# should work unless the link has been changed/ended/taken down...
declare -A urls=(
	["study"]="https://youtu.be/jfKfPfyJRdk"
	["chill"]="https://youtu.be/rUxyKA_-grg"
	["game"]="https://youtu.be/MVPTGNGiI-4"
	["fcc"]="https://coderadio-relay-ffm.freecodecamp.org/radio/8010/radio.mp3"
)

declare -A messages=(
	["study"]="Playing lofi hip hop radio - beats to relax/study to"
	["chill"]="Playing lofi hip hop radio - beats to sleep/chill to"
	["game"]="Playing synthwave radio - beats to chill/game to"
	["fcc"]="Playing freeCodeCamp code Radio"
)

usage() {
	cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Play/Stream lofi music audio, and nothing else
                          - Amberol (probably)

Options:
  -s, --study, relax      Play lofi radio beats to relax/study music.
  -c, --chill, sleep      Play lofi radio beats sleeps/chill music.
  -g, --game, synthwave   Play lofi synthwave radio beats to chill/game music.
  -f, --fcc, fcc, code    Play freeCodeCamp Code Radio.
  -r, --random            Play a random station URL (study, chill, game, fcc).
  -v, --video             Play with video (default: none, no video for fcc).
  -h, --help              Display this help message.
EOF
}

set_station() { station_name=$1 && url=${urls[$station_name]}; }
set_station_based_on_time_of_the_day() {
	hour=$(date +%_H)
	if ((hour >= 22 && hour < 6)); then
		set_station "chill"
	elif ((hour >= 6 && hour < 12)); then
		set_station "study"
	elif ((hour >= 18 && hour < 22)); then
		set_station "game"
	else
		set_station "fcc"
	fi
}

main() {
	local url
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
			-f | --fcc | code | fcc)
				set_station "fcc"
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

	echo "${messages[$station_name]}..."

	if $video; then
		mpv "$url"
	else
		mpv --no-video "$url"
	fi
}

main "$@"