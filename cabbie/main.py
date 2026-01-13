"""
Cabbie

A tool that uses OpenAI to generate commands to run on the user's behalf.
"""

#! /usr/bin/env python3

import subprocess
import sys
import os

# Try to use pipx environments first (if available)
pipx_venvs = os.path.expanduser("~/.local/share/pipx/venvs")
cabinet_venv = f"{pipx_venvs}/cabinet/lib/python3.12/site-packages"
python_helpers_venv = f"{pipx_venvs}/tyler-python-helpers/lib/python3.12/site-packages"

# Add pipx venvs if they exist
for venv_path in [cabinet_venv, python_helpers_venv]:
    if os.path.exists(venv_path) and venv_path not in sys.path:
        sys.path.insert(0, venv_path)

# Fallback to local git repos if pipx venvs don't work
cabinet_path = os.path.expanduser("~/git/cabinet/src")
python_helpers_path = os.path.expanduser("~/git/python-helpers")

for path in [cabinet_path, python_helpers_path]:
    if path not in sys.path:
        sys.path.insert(0, path)

from tyler_python_helpers import ChatGPT  # pylint: disable=import-error # type: ignore

# Debug mode - set to True to enable debug logging
DEBUG = False
chatgpt = ChatGPT()


def debug_print(message: str) -> None:
    """Print debug messages if DEBUG is True."""
    if DEBUG:
        print(f"DEBUG: {message}")


def clean_command(command: str) -> str:
    """Clean up the command by removing markdown formatting."""
    debug_print(f"Cleaning command: {command}")
    # Remove markdown code block syntax
    command = command.replace("```bash", "").replace("```", "")
    # Remove any leading/trailing whitespace
    cleaned = command.strip()
    # Remove any remaining 'bash' prefix if it exists
    if cleaned.startswith("bash"):
        cleaned = cleaned[4:].strip()
    debug_print(f"Cleaned command: {cleaned}")
    return cleaned


def run_command(command: str, timeout: int = 6) -> tuple[str, str]:
    """Run a command in the background and capture its output."""
    debug_print(f"Running command with {timeout}s timeout: {command}")

    try:
        # Use subprocess.run with a timeout
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=True,
            preexec_fn=os.setsid,  # Create new process group
        )

        debug_print("Command completed successfully")
        return result.stdout, result.stderr

    except subprocess.TimeoutExpired as exc:
        debug_print("Command timed out, attempting to terminate...")
        raise TimeoutError(f"Command timed out after {timeout} seconds") from exc

    except KeyboardInterrupt:
        debug_print("Received keyboard interrupt")
        raise
    except Exception as e:
        debug_print(f"Error in run_command: {e}")
        raise e


def main():
    """
    main function
    """
    try:

        # Get system info in a cross-platform way
        debug_print("Getting device info")
        try:
            # Try hostnamectl first (Linux)
            device_type = subprocess.check_output(["hostnamectl"]).decode("utf-8")
        except Exception:  # pylint: disable=broad-exception-caught
            # Fall back to uname (macOS and other Unix-like systems)
            device_type = subprocess.check_output(["uname", "-a"]).decode("utf-8")
        debug_print(f"Device info: {device_type}")

        command = " ".join(sys.argv[1:])
        if not command:
            print("Error: No command received from user")
            sys.exit(1)
        debug_print(f"User command: {command}")

        prompt = f"""
        You are a helpful assistant that can run commands on behalf of the user.
        You are running on a {device_type} device.
        
        Rules for command generation:
        1. Output only the command(s) to satisfy the user's request
        2. Use simple, reliable commands that work on most Unix-like systems
        3. Avoid complex shell features like command substitution unless necessary
        4. For system info, prefer standard commands like 'uname', 'df', 'free', etc.
        5. Do not include any explanations or markdown formatting
        6. If multiple commands are needed, separate them with &&
        7. Do not start command with 'bash' or 'zsh'.
        
        The user's request is: {command}
        """

        # Get command from OpenAI
        debug_print("Getting command from OpenAI")
        command_to_run = chatgpt.query(prompt)
        command_to_run = clean_command(command_to_run)

        if not command_to_run:
            print("Error: No command received from OpenAI")
            sys.exit(1)

        # Run the command and store the output
        try:
            debug_print("Executing command")
            stdout, stderr = run_command(command_to_run)
            output = stdout.strip()
            if stderr:
                print(f"Warning: Command produced stderr: {stderr.strip()}")
                output = stderr.strip()
        except TimeoutError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error running command: {e}")
            if e.stdout:
                print(f"Command stdout: {e.stdout}")
            if e.stderr:
                print(f"Command stderr: {e.stderr}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nCommand interrupted by user")
            sys.exit(1)

        # Summarize the output
        debug_print("Getting summary from OpenAI")
        summary_prompt = f"""
        A user asked you how to run the following command: {command}
        You responded with the following command: {command_to_run}
        The output of the command is: {output}
        Interpret the output within a single sentence in a user-friendly way.
        Do not refer to the command or the output as 'output' or 'command'.
        """

        # Get summary from OpenAI
        summary = chatgpt.query(summary_prompt)
        debug_print("Got summary from OpenAI")
        print(summary)

    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        sys.exit(1)
    except Exception as e:  # pylint: disable=broad-exception-caught
        debug_print(f"Unexpected error in main: {e}")
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
