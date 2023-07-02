# OpenAI (GPT3)

## dependencies
- [cabinet](https://pypi.org/project/cabinet/) (or just hardcode API key)
- requests: Used for making HTTP requests to the OpenAI API.
   - Installation: pip install requests
- gtts: Used for converting text to speech and generating audio files.
   - Installation: pip install gtts
- pygame: Used for playing audio files.
  - Installation: pip install pygame
- pydub: Used for manipulating audio files.
  - Installation: pip install pydub
- cabinet: Used for storing and retrieving API keys securely.
  - Installation: pip install cabinet
- speech_recognition: Used for speech recognition functionality.
  - Installation: pip install SpeechRecognition
- playsound: Used for playing audio files without displaying any terminal output.
  - Installation: pip install playsound
- sox: Used for audio file conversion and playback (required for os.system("play ...") command).
  - Installation: On Ubuntu/Linux: sudo apt-get install sox libsox-fmt-all

## setup

- using `cabinet`, store the API key you generated from the reference website in `keys -> openai`.

  - for example, if you have no properties in your settings.json file, it should look like:

  ```
  {
      "keys": {
          "openai": "yourkeyhere"
      }
  }
  ```

## usage

- `../path/to/main.py` for an interactive cli
- `../path/to/main.py do you think we're in a simulation` to send "do you think we're in a simulation" to openai using your key

## reference

- https://beta.openai.com/docs/quickstart/build-your-application
