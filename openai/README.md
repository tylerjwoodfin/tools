# OpenAI (GPT3)

## dependencies

- [cabinet](https://pypi.org/project/cabinet/)
  - `cabinet --configure` for setup

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
