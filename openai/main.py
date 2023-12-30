"""
openai

see README.md for instructions
"""

import os
import sys
import openai
#pylint: disable=wrong-import-order
from cabinet import Cabinet

cab = Cabinet()

openai.api_key = cab.get("keys", "openai")


def submit(query, log="", debug=False):
    """
    submits `query` to openai
    """
    response = openai.Completion.create(
        model="text-davinci-002",
        prompt=f"""{log}\n{query}""",
        temperature=0.6,
        max_tokens=1024
    )

    # debugging
    if debug:
        print(".......")
        print(query)
        print(".......")
        print(response)
        print(".......")

    to_return = response["choices"][0]["text"]
    if "\n\n" in to_return:
        to_return = to_return.split("\n\n")[1]
    return to_return


def cli():
    """
    a back-and-forth interaction with GPT3
    """

    log = ""
    print(f"""{submit("Please greet me.", "")}\n\n""")

    while True:
        try:
            user_input = input("> ")

            if user_input == 'clear':
                os.system('clear')

            output = submit(user_input, log)
            if not output:
                print("I don't have an answer for that.")

            print(f"""{output}\n\n""")
            log = f"{log}\n{output}"
        except KeyboardInterrupt:
            try:
                sys.exit(0)
            except SystemExit:
                sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        response_simple = submit(' '.join(sys.argv[1:]), '')

        if '\n\n' in response_simple:
            response_simple = response_simple.split("\n\n")[1:]

        print(response_simple)
    else:
        cli()
