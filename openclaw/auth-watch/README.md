# OpenAI auth watch

When a food reminder or word quiz calls OpenAI and the ChatGPT subscription login is expired or otherwise unusable, Cherry sends one Telegram message with the sign-in command and the two checks that confirm it worked. She stays quiet until that login works again, then sends once more if it breaks later.

There is no separate schedule. The message goes out from the call that failed.
