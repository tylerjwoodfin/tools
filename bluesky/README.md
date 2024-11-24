# BlueSkyTool

BlueSkyTool is a Python script for posting messages to [BlueSky](https://bsky.app) directly from the terminal.

## Features

- Authenticate with BlueSky using saved credentials.
- Post messages directly to your BlueSky account from the command line.
- Modular design with reusable components.

## Prerequisites

- Python 3.9 or newer
- Dependencies:
  - `atproto` library
  - [Cabinet](https://www.github.com/tylerjwoodfin/cabinet)
- Your BlueSky credentials stored in a `Cabinet` instance under the key `bluesky`.

## Installation

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. Install dependencies:
   ```bash
   pip install atproto cabinet
   ```

3. Set up your credentials in `Cabinet`:
   Use the `cabinet` library to securely store your BlueSky `handle` and `password` under the key `bluesky`:
   ```json
    {
      "bluesky": {
         "handle": "your_handle",
         "password": "your_password"
      }
    }
   ```

## Usage

Run the script from the terminal:

```bash
python3 bluesky.py
```

You will be prompted to enter a message to post.

## Code Overview

The core functionality is encapsulated in the `BlueSkyTool` class:
- `authenticate()`: Logs in using credentials stored in `Cabinet`.
- `post(message: str)`: Posts a message to your BlueSky account.
- `run(message: str)`: Combines authentication and posting for seamless execution.

## License

This project is licensed under the MIT License.