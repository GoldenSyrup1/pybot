"""A line that takes issue with the bot's own answer is answered about that answer.

"that makes no sense", "that cant be right", "youre confusing me" name nothing of their own: the
thing they are about is the paragraph the bot has just printed. On main every one of them was read
as a shrug or as bad news about the person ("Fair enough.", "Thanks for telling me - I'm here if
you want to dig into any of that"), which is the bot saying it heard nothing at the one moment the
person is telling it the answer failed.

The reading and the wording live in `bot/memory/doubt.py`, next to the store it reads; this module
is here so the claim has a band of its own. It sits above the small talk (`chat.py`, 300), which is
what answered these lines with a stock nod, and below the safety band: a line in a crisis is never
this module's, however it is phrased. Nothing is claimed from any other module's real answer -
`respond` returns None on every line that is not a doubt about the bot's own last sentence.
"""
from ..memory import doubt

# Above the small talk (chat, 300) - it is that module's stock nod these lines were getting - and
# below the store (7000) and the safety band (9000 and up).
PRIORITY = 400


def respond(text, memory):
    """The reply to a doubt about the bot's own last answer, or None for every other line."""
    return doubt.reply_for(text, memory)
