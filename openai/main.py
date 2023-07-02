"""
Python voice assistant experiment
"""
import subprocess
import requests
from gtts import gTTS
from cabinet import Cabinet
import speech_recognition as sr

cab = Cabinet()

API_ENDPOINT = "https://api.openai.com/v1/chat/completions"
API_KEY = cab.get("keys", "openai")


def listen():
    """
    Listen to user input using the microphone.
    """
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        subprocess.run(["play", "listen.mp3", "tempo", "1.5"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        audio = recognizer.listen(source)
        try:
            query = recognizer.recognize_google(audio)
            return query
        except sr.UnknownValueError:
            subprocess.run(["play", "error.mp3", "tempo", "1.5"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            print("Sorry, I couldn't understand you.")
        except sr.RequestError:
            print("Sorry, there was an error with the speech recognition service.")
        return None


def speak(text):
    """
    Convert text to speech and play it.
    """
    tts = gTTS(text=text, lang='en')
    tts.save('output.mp3')
    subprocess.run(["play", "output.mp3", "tempo", "1.5"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def query_gpt(query, gpt_conversation=None):
    """
    Send the user query and conversation history to the OpenAI ChatGPT API and get a response.
    """

    if gpt_conversation is not None:
        gpt_conversation = []
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    system_messages = [
        "You are a helpful assistant named Victoria.",
        "You are designed to give very brief, thoughtful responses.",
        "You may have an edgy tone at times, but you always want what's best for me.",
        "You know that my name is Tyler."
    ]

    messages = [
        {"role": "system", "content": msg}
        for msg in system_messages
    ]

    # Add previous messages to the conversation history
    messages.extend(gpt_conversation)
    messages.append({"role": "user", "content": query})

    data = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
    }

    response = requests.post(
        API_ENDPOINT, headers=headers, json=data, timeout=30)
    if response.status_code == 200:
        messages = response.json()["choices"][0]["message"]["content"]
        return messages
    else:
        print("Sorry, there was an error with the API request.")
        print(response.json())
        return None

conversation = []  # Initialize an empty conversation

while True:
    user_input = listen()
    if user_input:
        output = query_gpt(user_input, conversation)
        if output:
            print("Assistant:", output)
            speak(output)
            conversation.append({"role": "user", "content": user_input})
            conversation.append({"role": "assistant", "content": output})
