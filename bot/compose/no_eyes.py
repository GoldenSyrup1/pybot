"""The reader for a thing of the person's own that is on their side of the screen.

Two shapes, one reading. A line can ask the bot to open, read, look at, fill in, print or send
something of theirs, or it can simply hand the thing over ("here's a screenshot", "the link is
www..."). Either way nothing here can see it: nothing comes through an attachment, nothing can be
opened, and there are no hands to click with. On main the first shape got the search hedge, "a
quick search online will get you a solid answer", which sends somebody to go and google their own
inbox, and the second got "Got it. Is there anything you'd like a hand with?" as though the
picture had arrived.

The pool that answers is read from the object, never invented: a link is pasted, a photo or a
screen is described, an inbox is copied from, a form is read out, a click or a print is turned
into steps, and a bare "this" is the text on their screen. Nothing here is a fact about the world.

Both readings are narrow. The ask needs the bot's own act ("can you ...", or an imperative with
"for me") and a verb only an eye or a hand can do; the handed line needs a handing word and the
family named, or a bare link. Both stand down for what the bot can do ("can you write my cv for
me", "can you type up my notes"), for a line that already holds the text ("i pasted the text
below"), for what the bot keeps of the person ("can you see my chats with you"), for an address or
a number they are giving the bot, for a message or a text (this chat, not their mail), and for any
body part, symptom or doctor's word: a rash is not a file, and the pharmacist line is the answer.

This lives in its own file because `bot/compose/fallback.py` is at the world's size limit; the
fallback imports the two readers and keeps the choosing of the line.
"""
import re

SEEING_FAMILIES = {
    "link": ("link", "links", "url", "urls", "website", "websites", "site", "sites",
             "webpage", "web page", "webpages", "page", "pages", "article", "articles",
             "tab", "tabs", "browser"),
    "photo": ("screen", "screens", "camera", "webcam", "photo", "photos", "picture",
             "pictures", "image", "images", "screenshot", "screenshots", "video", "videos",
             "clip", "clips", "notification", "notifications"),
    "voice": ("voice note", "voice notes", "voice memo", "voice memos", "voice message",
              "voice messages", "voice recording", "voice recordings", "voice clip",
              "recording", "recordings", "audio", "audio clip", "audio file", "audio message",
              "sound file", "sound clip", "memo", "memos", "voicemail", "voicemails",
              "podcast", "podcasts"),
    "inbox": ("email", "emails", "e-mail", "e-mails", "mail", "inbox", "message", "messages",
             "text", "texts", "voicemail", "voicemails", "letter", "letters", "post",
             "folder", "folders", "spam"),
    "form": ("form", "forms", "paperwork", "questionnaire", "tax return", "tax returns",
             "return form"),
    "file": ("file", "files", "document", "documents", "doc", "docs", "pdf", "pdfs",
             "spreadsheet", "spreadsheets", "essay", "essays", "cv",
             "homework", "statement", "invoice", "receipt", "contract", "attachment",
             "attachments"),
}
# What only a hand can do on the person's side: none of it happens from the chat. Writing,
# typing, copying out, suggesting and explaining are what the bot does do, so they are not here
# ("can you type out a message for my landlord" wants the words, not a click).
A_HAND_DOES_IT = re.compile(
    r"\b(?:click|clicking|tap|tapping|press|pressing|scroll|scrolling|print|printing|"
    r"scan|scanning|download|downloading|upload|uploading|"
    r"send|sending|forward|forwarding|save|saving|delete|deleting|install|installing|"
    r"access|accessing|submit|submitting|log\s+in|sign\s+in|screenshot|screenshotting|"
    r"take\s+(?:a\s+)?(?:photo|picture|screenshot)|type\s+(?:in|into)|"
    # "sign" only where it is the act of signing the thing itself ("can you sign this for me"):
    # a bare "sign" is also a sign in a shop window, which is not a hand doing something for them.
    r"sign\s+(?:it|this|that|these|those|them|for\s+(?:me|us))|"
    r"copy\s+(?:the|it|that|this|out))")
# What only an eye can do on the person's side, and only once the thing is handed over as text.
AN_EYE_READS_IT = re.compile(
    r"\b(?:open|opening|read|reading|see|seeing|view|viewing|watch|watching|find|finding|"
    r"look\s+(?:at|through|over|in|into)|"
    r"check|checking|fill(?:ing)?\s+(?:in|out)|fill|filling|complete|completing|translate|translating|"
    r"read\s+(?:out|it\s+out)?\s+what\s+(?:it|that|this)\s+says|what\s+(?:my|the)\s+\S+\s+says|"
    r"update|updating|go\s+through|get\s+into)")
# What only an ear can do on the person's side. A voice note, a recording, a podcast: the sound
# never arrives here, and "can you listen to this" used to get "that's beyond what I know well"
# with a search suggested, or a shrug.
AN_EAR_HEARS_IT = re.compile(
    r"\b(?:listen|listening|hear|hearing|play|playing|playback|transcribe|transcribing|"
    r"decipher|make\s+out)")
NO_HAND_VERB = re.compile(A_HAND_DOES_IT.pattern + "|" + AN_EYE_READS_IT.pattern + "|"
                          + AN_EAR_HEARS_IT.pattern)
# The same eye, for a bare "this/that/it" with no object named: the thing is handed over as text
# and read here. "Find" is not here - "can you find it" is a missing thing, not a page to read.
READS_HANDED_TEXT = re.compile(
    r"\b(?:open|opening|read|reading|see|seeing|view|viewing|watch|watching|"
    r"look\s+(?:at|through|over)|translate|translating|what\s+(?:it|this|that)\s+says)\b")
# "Can you", "could you", "print this for me": the ask has to be the bot's own act, not a
# request for advice about the thing.
ASKS_THE_BOT_TO_ACT = re.compile(
    r"\b(?:can|could|would|will|are|do)\s+(?:you|u)\s+(?:please\s+|just\s+|kindly\s+|also\s+)*"
    # "help me fill in this form" is the same ask as "can you fill in this form": the person wants
    # the job done, not the menu that does it, and it reached the search hedge.
    r"|\bhelp\s+(?:me|us)\b\s+(?:\S+\s+){0,3}"
    r"\S"
    # The ask said as an offer of the thing to be looked at: "have a listen to this voice memo",
    # "have a look at this photo". It is the same act asked the other way round, and the hedge it
    # used to reach ("That's beyond what I know well") assumed the bot could hear the memo.
    r"|\b(?:have\s+a\s+(?:listen|look|read|quick\s+look)|take\s+a\s+(?:listen|look|read))\b"
    r"|^\s*(?:please\s+|just\s+)?(?:open|print|read|see|check|look\s+at|fill\s+in|fill\s+out|"
    r"scan|download|upload|click|tap|press|scroll)\b[^?]*\b(?:for\s+me|please)\b")
# A line that holds the text already ("can you check this sounds right: Hi Sarah, just checking")
# has given the bot what it needs; the rewrite and reading modules answer those.
HOLDS_THE_TEXT = re.compile(r":\s*\S+(?:\s+\S+){5,}")
# What the person can do instead, one pool per family, because the way to hand it over differs.
CANNOT_SEE = {
    "link": (
        "I can't open links, sorry - nothing on my side can browse. Tell me what it says, or what "
        "you want from it, and I'll help you with that.",
        "No link opening from here, sorry. Paste the bit that matters into the chat and I'll work "
        "through it with you.",
        "I can't follow a link, sorry. Copy the words you need and send them here - I'll take it "
        "from there.",
    ),
    "photo": (
        "I can't see your screen or your photos, sorry - I only get the words you type. Describe "
        "what's there, or type out the part that matters, and I'll help.",
        "Nothing on my side can look at a photo or a screen, sorry. Tell me what it shows and what "
        "you need to know about it.",
        "I can't see pictures from here - no camera, no screen. Say what is in it and I'll tell "
        "you what I make of it.",
    ),
    "inbox": (
        "I can't get into your inbox or your messages, sorry - they're on your side. Copy the "
        "words that matter in here and I'll help you answer them.",
        "Your email is not something I can see. Paste the part you need to deal with and I'll "
        "draft the reply.",
        "I can't read your mail from here. Send me the gist of it and I'll help you work out what "
        "to say back.",
    ),
    "form": (
        "I can't fill in a form I can't see, sorry. Tell me what it asks, one line at a time, and "
        "I'll give you an answer for each.",
        "I can't write on a form from here - no hands on my side. Read me the questions and I'll "
        "give you the words; you put them in.",
    ),
    "file": (
        "I can't open files, sorry - nothing here can see or send them. Paste the text in and "
        "I'll go through it with you.",
        "Nothing here can open a file, sorry. Type in the part you want help with and I'll take "
        "it from there.",
        "I can't see a file from here, sorry - I only get what you type. Paste a bit of it in "
        "and we'll work on that.",
    ),
    "text": (
        "I can't see the page you're looking at, sorry - I only get what you type. Paste the bit "
        "you want help with and I'll go through it with you.",
        "Nothing on my side can see the text on your screen, sorry. Type in the part that matters "
        "and I'll take it from there.",
        "I only see the words you send me, sorry - not what is on your screen. Paste it in here "
        "and I'll work on that.",
    ),
    "voice": (
        "I can't hear a voice note or a recording, sorry - no ears on this end. Type the bit that "
        "matters in here and I'll work from that.",
        "Nothing on my side can play or listen to audio. Write down what was said, even roughly, "
        "and I'll take it from there.",
        "I can't listen to a recording from here - I only get what you type. Put the words in the "
        "chat and I'll help with them.",
    ),
    # The same missing ear with no recording named at all: "can you hear that noise", "can you
    # hear that bird", "can you play that song again". A voice-word pool would tell somebody
    # holding nothing to transcribe it, so the line says only what is true - nothing here hears
    # or plays anything - and asks for the sound in words.
    "sound": (
        "I can't hear anything from here, sorry - no ears and no speaker on this side. Tell me "
        "what it sounded like and I'll do what I can with that.",
        "Nothing on my side can listen or play, sorry. Describe the sound in words and I'll take "
        "it from there.",
        "There is no microphone or speaker on this end, so I can't hear or play it. Say what you "
        "noticed - what it was like, when it happens - and we can work it out from that.",
    ),
    "hands": (
        "I can't click, print or type on your device, sorry - I'm only words in the chat. Tell me "
        "what's on the screen and what you want to do and I'll walk you through the steps.",
        "No hands on my side, sorry: nothing here can press, print or send anything. Say what you "
        "are trying to do and I'll give you the clicks in order.",
    ),
}


# "my chats with you", "our conversation", "can you remember my name": the bot talking about
# what it keeps of the person, which is its own line and not this one.
ABOUT_WHAT_IT_KEEPS = re.compile(
    r"\b(?:with|to)\s+you\b|\bour\s+(?:chat|chats|talk|talks|conversation|conversations)\b"
    r"|\bremember\s+(?:me|my|what|anything|things)\b")


A_URL = re.compile(r"\b(?:https?://|www\.)\S+")
# A message or a text handed over is this chat, or the phone in their hand: only mail is on the
# far side of a screen the bot can name ("i sent you a message earlier" is not "I can't read your
# mail from here").
HANDED_FAMILIES = {
    "inbox": ("email", "emails", "mail", "inbox", "letter", "letters", "attachment", "attachments"),
}
HANDED_OVER = re.compile(
    r"\b(?:here'?s|here\s+(?:is|are)|attached|attaching|see\s+attached|"
    r"sent\s+you|sending\s+you|shall\s+send\s+you|screenshot\s+below|"
    r"photo\s+below|picture\s+below|"
    r"recorded\b[^.]{0,30}\bfor\s+you|"
    r"this\s+is\s+(?:a|my)\s+(?:video|recording|voice\s+note|voice\s+memo|photo|picture|"
    r"screenshot)\b)\b")


def handed_you_something(clean):
    """The honest line for a thing the person believes they have just handed over, or None.

    "here's a screenshot", "i sent you a photo", "here is the link", "the link is www.example.com/
    offer" are not asks at all, so nothing in the bot answers them and the person gets "Got it. Is
    there anything you would like a hand with?" - which reads as though the picture had arrived.
    Nothing comes through an attachment and nothing can be opened, so the line has to say that and
    ask for the words instead. A line that does hold the text ("i pasted the text below") is left
    alone: that one did come through.
    """
    if HOLDS_THE_TEXT.search(clean):
        return None
    if len(clean.split()) > 25:
        return None
    if re.search(r"\S+@\S+\.\w+|\baddress\b|\bnumber\b", clean):
        # "here's my email address", "my email is sam@example.com", "here's my number" are the
        # person handing over something the bot can keep, not a thing it is being asked to look
        # at, and the honest "I can't see your inbox" is a lie about the line.
        return None
    if A_URL.search(clean) and not re.search(r"\bhow\s+(?:do|can|should)\s+i\b", clean):
        # A link in the line is a page the bot cannot open, whether it was handed over or asked
        # about ("is this link safe www..."), so this is read before the ask guard. "how do i
        # shorten a long url" is a how-to and is left to whatever else answers it.
        return CANNOT_SEE["link"]
    if not HANDED_OVER.search(clean):
        return None
    for family in ("voice", "photo", "link", "file", "inbox", "form"):
        things = HANDED_FAMILIES.get(family) or SEEING_FAMILIES[family]
        if re.search(r"\b(?:" + "|".join(re.escape(thing) for thing in things) + r")\b", clean):
            # The family they name is the thing on their own side: a screenshot or a photo is
            # looked at, a link is opened, a file or a letter is read, a form is written on.
            return CANNOT_SEE[family]
    if ASKS_THE_BOT_TO_ACT.search(clean):
        # "heres a link to a recipe, can you make it" is decided by the thing handed over, above;
        # what is left here is an ask with no thing named, which is somebody else's reader.
        return None
    if re.search(r"\bsee\s+attached\b|\battached\s+(?:is|are)\b", clean):
        return CANNOT_SEE["file"]
    return None


# Writing a message somebody will send is the bot's own work, not an eye or a hand: "can you
# send an email for me", "can you send a text to my landlord", "can you send this message on my
# behalf". The mail word is in the inbox family, so the reader took these for an inbox it cannot
# open and answered "I can't get into your inbox - paste the words that matter in here": no help
# to somebody who has not written them yet. The fallback's drafting invite is the answer to this
# shape ("give me who it's for and what you want them to do"), so the reader stands down and
# lets it through.
WRITES_A_MESSAGE = re.compile(
    r"\b(?:can|could|would|will)\s+(?:you|u)\s+(?:please\s+|just\s+|also\s+)*"
    r"(?:\w+\s+){0,3}(?:send|write|draft|type\s+out|put|reply|forward|answer)\b")
MESSAGE_WORD = re.compile(
    r"\b(?:email|emails|e-mail|e-mails|text|texts|message|messages|note|notes|letter|letters|"
    r"reply|replies|memo)\b")
TO_A_PERSON = re.compile(
    r"\bfor\s+(?:me|us)\b|\bon\s+my\s+behalf\b"
    r"|\bto\s+(?:my|our|the|his|her|their|a)\s+[a-z]+|\b(?:someone|somebody|anyone)\b")
# Forwarding is never drafting: the message is already written, so the words are not what the
# person is short of. "can you forward the letter to my solicitor" is a hand, and the honest
# answer for it is the reader's own, not an offer to write something new.
A_FORWARD = re.compile(r"\bforward(?:ing|ed)?\b")
# A message named as theirs ("my email", "the letter") already exists, the same way.
THEIR_OWN_MESSAGE = re.compile(
    r"\b(?:my|our|the|his|her|their)\s+(?:email|e-mail|text|message|note|letter|reply|memo)s?\b")


# Who it is for, when the line says: "to my landlord", "for my boss", "to the council". "For me"
# and "on my behalf" are not this - nobody is named, so the invite still has to ask.
A_NAMED_ADDRESSEE = re.compile(
    r"\b(?:to|for|with)\s+(?:my|our|his|her|their|the|a)\s+[a-z]+"
    r"|\b(?:to|for)\s+(?:someone|somebody)\b")


def names_the_addressee(clean):
    """True when the line already says who the message is for."""
    return bool(A_NAMED_ADDRESSEE.search(clean))


def writes_the_message(clean):
    """True when the ask is for the words of a message to somebody: write it, not send it."""
    if not MESSAGE_WORD.search(clean) or not WRITES_A_MESSAGE.search(clean):
        return False
    if A_FORWARD.search(clean) or THEIR_OWN_MESSAGE.search(clean):
        return False
    return bool(TO_A_PERSON.search(clean))


# "back" is a body and also "play that audio back", "call back", "get back to". Only the body
# sense is a reason to stand down, so the word is read as a body part only when it is used as one.
BACK_AS_A_BODY = re.compile(
    r"\b(?:my|your|his|her|our|their|the|lower|upper|sore|bad)\s+back\b|"
    r"\bback\s+(?:pain|ache|aches|hurts?|spasms?|injur\w*|problem|again)\b")


def _a_body_or_a_doctor(clean):
    """True when the line names a body, a symptom or a doctor - a rash is not a file.

    "can you look at this rash" and "can you look at this thing on my leg" were answered "I can't
    open files, sorry", which takes the health card off the table; the pharmacist line is the one
    that helps. The word tables are the fallback's own, read here so the two cannot drift.
    """
    from .fallback import BODY_PARTS, HEALTH_WORDS, SYMPTOM_WORDS
    plain = set(re.findall(r"[a-z']+", clean))
    if "back" in plain and not BACK_AS_A_BODY.search(clean):
        plain.discard("back")
    return bool(plain & BODY_PARTS or plain & SYMPTOM_WORDS or plain & HEALTH_WORDS)


def _a_voice_is_named(clean):
    """A recording, a memo, a podcast: something with words in it to be written down.

    A bare "can you hear that" names no recording, so it is owed the smaller line - nothing here
    hears it - rather than "type the bit that matters", which assumes a recording that the person
    is not holding. #7519's first head sent "can you hear that noise" to the voice-note pool.
    """
    return bool(re.search(r"\b(?:" + "|".join(
        re.escape(thing) for thing in SEEING_FAMILIES["voice"]) + r")\b", clean))


# A thing that is played is not a thing to be heard: "can you play this level with me" is an
# invitation, and the sound pool answered it "I can't hear anything from here - no ears and no
# speaker on this side". The words people use for a turn of it are not `game` (found by
# @neat-pineapple on #7519), so the list is the nouns of playing and the `with me` that asks for
# company; `can you play that song again` and `can you play this record` are still sounds.
GAME_TO_PLAY = re.compile(
    r"\b(?:game|games|chess|match|quiz|level|levels|round|rounds|move|moves|puzzle|puzzles|"
    r"cards|darts|board|boards|innings|hole|holes|shot|shots|score|scores|character|"
    r"save|savegame)\b"
    r"|\bplay\s+[^.!?]{0,30}\bwith\s+me\b", re.I)


def _a_game_to_play(clean):
    """The line asks the bot to join in a game, or names a turn of one, so nothing is to be heard."""
    return bool(GAME_TO_PLAY.search(clean))


def cannot_see_your_thing(clean):
    """The honest line for a thing of theirs the bot cannot open, or None."""
    if not ASKS_THE_BOT_TO_ACT.search(clean) or not NO_HAND_VERB.search(clean):
        return None
    if HOLDS_THE_TEXT.search(clean) or ABOUT_WHAT_IT_KEEPS.search(clean):
        return None
    if len(clean.split()) > 25:
        return None
    if _a_body_or_a_doctor(clean):
        return None
    if writes_the_message(clean):
        return None
    # The longest name wins, not the first family in the table: "can you listen to this audio
    # clip" names a `clip` and an `audio clip`, and the picture pool in front of the voice pool
    # answered it "I can't see pictures from here - no camera, no screen", which is a refusal of
    # the wrong sense. A longer name is the more particular one, so it is the one being asked for.
    matched = []
    for name, things in SEEING_FAMILIES.items():
        hit = re.search(r"\b(?:" + "|".join(re.escape(thing) for thing in things) + r")\b", clean)
        if hit:
            matched.append((len(hit.group(0)), name))
    if matched:
        return CANNOT_SEE[max(matched)[1]]
    if re.search(r"\bfill(?:ing)?\b", clean) and re.search(r"\b(?:this|that)\b", clean):
        return CANNOT_SEE["form"]
    if A_HAND_DOES_IT.search(clean):
        return CANNOT_SEE["hands"]
    if re.search(r"\b(?:this|that|these|those)\b", clean) and AN_EAR_HEARS_IT.search(clean) \
            and not _a_game_to_play(clean):
        if _a_voice_is_named(clean):
            return CANNOT_SEE["voice"]
        return CANNOT_SEE["sound"]
    if re.search(r"\b(?:this|that|these|those)\b", clean) and AN_EYE_READS_IT.search(clean):
        return CANNOT_SEE["text"]
    if re.search(r"\bit\b", clean) and READS_HANDED_TEXT.search(clean):
        return CANNOT_SEE["text"]
    return None




# --- a body asked about -------------------------------------------------------
# A second reader, for the same "nothing on this side can look" but a different object: the
# person's own body, or a mark on it. "can you look at my knee", "does this look infected",
# "can you see if this is healing" and "can you tell me if this mole is ok" reached the search
# hedge, and after this file merged they reached its bare-`this` pool instead ("I can't see the
# page you're looking at"). A rash is not a page: what is wanted is not a document read out but an
# opinion on a mark on them. The stand-down in `cannot_see_your_thing` already knows a body is not
# a file; this reader is what says so.
CANNOT_SEE_YOU = (
    "I can't see it from here, sorry - only what you type reaches me. Tell me where it is, how big "
    "it is and how long it has been there, and I'll say what to watch for. A pharmacist can take a "
    "look today if you want eyes on it.",
    "Nothing on my side can look, sorry. Describe it - where it is, what it is like, whether it has "
    "changed - and I'll help you work out what to do next. A chemist will look at it for free, and "
    "today.",
    "I can't see or feel anything from here, so I can't judge it for you. Say where it is and what "
    "it is like, and I'll tell you what I would do about it; if you want it looked at today, a "
    "pharmacist is the quickest way in.",
)
# The ask: the bot's own act, or a question about how the thing looks.
A_LOOK_ASK = re.compile(
    r"\b(?:can|could|would)\s+(?:you|u)\s+(?:please\s+)?(?:look\s+(?:at|over)|"
    r"(?:have|take)\s+a\s+look(?:\s+at)?|see|check|examine|tell\s+me\s+(?:if|whether))\b"
    r"|^\s*(?:does|do|is|are)\s+(?:this|these|it|that)\b"
    r"|^\s*tell\s+me\s+(?:if|whether)\b"
    r"|\bwhat\s+does\s+(?:this|it|my)\b", re.I)
# A bare "can you look at it" is a body only when the turn before was about one.
A_LOOK_ASK_IT = re.compile(
    r"\b(?:can|could|would)\s+(?:you|u)\s+(?:please\s+)?(?:look\s+at\s+it|check\s+it|see\s+it|"
    r"have\s+a\s+look|take\s+a\s+look)\b", re.I)
# Body parts the fallback's BODY_PARTS does not carry, which are still a body.
A_MORE_BODY = frozenset((
    "tongue", "lip", "lips", "cheek", "cheeks", "chin", "forehead", "thumb", "thumbs", "thigh",
    "thighs", "shin", "shins", "calf", "calves", "heel", "heels", "palm", "palms", "scalp",
    "armpit", "armpits", "groin", "bum", "bottom", "eyelid", "eyelids", "nostril", "navel",
    "kidney", "kidneys", "lung", "lungs", "breast", "breasts", "testicle", "testicles", "penis",
))
A_MARK_ON_THEM = re.compile(
    r"\b(?:rash|rashes|lump|lumps|mole|moles|spot|spots|cut|cuts|bruise|bruises|wound|wounds|"
    r"blister|blisters|sore|sores|scar|scars|swelling|swollen|bite|bites|burn|burns|"
    r"infection|infected|healing|stitches|wart|warts|abscess|ulcer|numb)\b", re.I)


# "Back" is a body and also the word for going back to something: "is it worth going back to
# college at 40", "is it worth going back to work part time" and "should i go back to the gym"
# all start with "is it" and hold a body word, so they were answered "I can't see or feel
# anything from here, so I can't judge it for you. Say where it is and what it is like" - a
# question about a course or a job, answered as if it were a mark on their skin. The body reading
# is the one with the person's own back in the line ("my back", "lower back", "back pain",
# "back ache", "on my back", "back is"), or with no returning word at all.
GOING_BACK = re.compile(
    r"\b(?:go|goes|going|went|get|gets|getting|got|come|comes|coming|came|move|moves|moving|"
    r"moved|be|been|being|bring|brings|bringing|brought|give|gives|giving|gave|pay|pays|paying|"
    r"paid|put|puts|putting|hold|holds|holding|held|hand|hands|handing|send|sends|sending|sent|"
    r"cut|cutting|run|running|ran|turn|turns|turning|turned|look|looks|looking|looked|"
    r"walk|walks|walking|walked|drive|drives|driving|drove|fly|flies|flying|flew|sit|sits|"
    r"sitting|sat|step|steps|stepping|stepped|write|writes|writing|wrote|ring|rings|ringing|"
    r"rang|call|calls|calling|called|text|texts|texting|texted|reply|replies|replying|replied)\s+"
    r"(?:straight\s+|right\s+|all\s+the\s+way\s+)?back\b"
    r"|\bback\s+(?:to|from|at|in|on|into|with|home)\b"
    r"|\b(?:give|gives|giving|gave|pay|pays|paying|paid|put|puts|putting|hold|holds|holding|"
    r"hand|hands|handing|send|sends|sending|sent|cut|cutting)\s+(?:it|them|him|her|that|this|"
    r"me|us|the\s+\w+)\s+back\b")
MY_BACK = re.compile(
    r"\b(?:my|lower|upper|sore|aching|achy|stiff|bad|your|his|her|their)\s+back\b"
    r"|\bback\s+(?:pain|ache|aches|spasm|injury|problem|problems|hurts|is\s+sore)\b"
    r"|\bon\s+(?:my|his|her|their|your)\s+back\b|\bback\s+(?:of\s+my|of\s+his|of\s+her)\b")


def _asks_me_to_look_at_them(clean, repaired=None, memory=None):
    """A line asking the bot to look at their body, or a mark on it.

    "can you look at my knee", "can you tell me if this mole is ok", "does this look infected" and
    "what does this rash look like" all reached the search hedge, and a search engine cannot see
    their leg either. The honest line is the one the health pool already gives: nothing here can
    examine anything, and the person who can is a pharmacist, a GP or 111. A line about something
    of theirs that is not their body ("can you look at my cv") names no body and no mark, so it is
    left alone; a red flag never reaches this reader, because the safety pool answers it first.
    """
    from .fallback import BODY_PARTS, SYMPTOM_WORDS, _thread_is_about_the_body
    for line in (clean, repaired or clean):
        if not A_LOOK_ASK.search(line):
            continue
        if A_MARK_ON_THEM.search(line):
            return True
        body = set(re.findall(r"[a-z']+", line.lower())) & (BODY_PARTS | A_MORE_BODY | SYMPTOM_WORDS)
        if body:
            # A returning "back" is not a body: "is it worth going back to college at 40" holds
            # "back" and starts with "is it", and was answered as a mark on their skin.
            if (body - {"back"}) or not GOING_BACK.search(line) or MY_BACK.search(line):
                return True
        if A_LOOK_ASK_IT.search(line) and _thread_is_about_the_body(memory):
            # "my ankle is swollen and i cant tell if its sprained" then "can you look at it": the
            # body is in the turn before, so the bare "it" is a body and needs the same line.
            return True
    return False


def look_at_a_body_lines(clean, repaired=None, memory=None):
    """The pool to say for a line asking the bot to look at the person's body, or None."""
    if _asks_me_to_look_at_them(clean, repaired, memory):
        return CANNOT_SEE_YOU
    return None
