# Cabbie

Ask AI to run commands on your behalf using natural language.
Now you're playing with fire!

## Features

- Natural language command interpretation
- Automatic command execution with proper process management
- 6-second timeout for command execution
- Graceful process termination (SIGTERM followed by SIGKILL if needed)
- Real-time output capture
- AI-powered output interpretation
- Debug mode for troubleshooting

## Installation

1. Ensure you have Python 3.6+ installed
2. Install the required dependencies:
   ```bash
   pip install openai cabinet
   ```
3. Make the script executable:
   ```bash
   chmod +x main.py
   ```

## Configuration

1. Set up your OpenAI API key in the Cabinet configuration:
   ```bash
   cabinet put keys openai YOUR_API_KEY
   ```

## Usage

Run the tool with a natural language description of what you want to do:

```bash
./main.py "show me all files in my documents folder"
```

The tool will:
1. Convert your request into appropriate shell commands
2. Execute the commands with proper process management
3. Capture and display the output
4. Provide a user-friendly interpretation of the results

## Examples

```bash
# Count files in a directory
./main.py "how many files are in my documents folder"

# Check system information
./main.py "what's my system information"

# Monitor system resources
./main.py "show me my system resources"
```

## Debug Mode

The tool includes a debug mode that can be enabled by setting `DEBUG = True` in the script. This will show detailed information about:
- Command cleaning and processing
- Process management
- Timeout handling
- Error conditions

## Notes

- Commands are executed with a 6-second timeout
- Long-running commands will be automatically terminated
- The tool uses process groups to ensure proper cleanup of child processes
- Commands are executed in a shell environment
- Output is captured and interpreted by AI for user-friendly presentation