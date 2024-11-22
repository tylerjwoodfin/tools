"""
BlueSky tool for easily posting through the terminal.
This script allows users to post directly to BlueSky using the official atproto library.
"""

import sys
from atproto import Client, client_utils
from cabinet import Cabinet


class BlueSkyTool:
    """
    A tool for interacting with the BlueSky API.
    Handles authentication and posting functionality.
    """

    def __init__(self):
        """
        initializes the BlueSkyTool with a client and cabinet instance.
        """
        self.client = Client()
        self.cabinet = Cabinet()

    def authenticate(self) -> None:
        """
        authenticates the client using credentials stored in cabinet.

        Raises:
            ValueError: if no credentials are found in cabinet.
        """
        creds: dict | None = self.cabinet.get('bluesky', return_type=dict)

        if creds is None:
            self.cabinet.log('No BlueSky credentials found.', level='error')
            raise ValueError("BlueSky credentials not found in Cabinet.")

        self.client.login(creds['handle'], creds['password'])

    def post(self, post_message: str) -> None:
        """
        posts a message to BlueSky.

        Args:
            post_message (str): the text to be posted.

        Returns:
            None
        """
        text = client_utils.TextBuilder().text(post_message)
        self.client.send_post(text)
        print("💙")

    def run(self, post_message: str) -> None:
        """
        runs the BlueSkyTool by authenticating and posting a message.

        Args:
            message (str): the text to post.

        Returns:
            None
        """
        try:
            self.authenticate()
            self.post(post_message)
        except ValueError as e:
            print(e)


if __name__ == '__main__':
    # ensure a message is provided as an argument
    if len(sys.argv) < 2:
        print("Usage: python bluesky.py '<message>'")
    else:
        message = sys.argv[1]
        tool = BlueSkyTool()
        tool.run(message)
