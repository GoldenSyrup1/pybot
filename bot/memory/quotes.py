"""The words an answer hands over to say, kept whole when the answer is cut down.

A lot of the knowledge base's best answers end in the words the person can send: a letter to a
landlord, a message to a neighbour, the sentence to say at a counter. Those words sit inside
quotation marks, and they have full stops of their own - a letter is two or three sentences long.

Every short form of an answer is made by cutting it at a full stop. That is right for a paragraph
of advice, and wrong for a quoted letter: the cut landed inside the quotes and the person was
given

    Keep it short, dated and specific, and ask for a date: "Hi — I reported the boiler on [date]
    and nothing has been done.

- half a letter, with the opening quotation mark never closed. Said after "how do i ask him
again", that is what the bot printed. Half a quotation is not a shorter version of the answer,
it is a broken one.

So the two marks are counted, and a cut that stops with a quote still open is carried on until the
quote closes. Nothing else about the cut changes: a reply with no quotation in it comes back
exactly as the caller would have cut it.
"""


def left_open(said):
    """True when `said` opens a quotation it does not close.

    Each convention is counted on its own: an odd number of straight quotes, or more curly openers
    than closers. Cheap, and it does not need to know which one an entry writes in.
    """
    said = str(said or "")
    if said.count('"') % 2:
        return True
    return said.count("\u201c") > said.count("\u201d")


def closed(said, rest, whole=""):
    """`said` carried on through `rest` until the quotation in it closes.

    `said` is the short form the caller cut, `rest` the sentences after it in the same order, and
    `whole` the answer they came from. A quote that never closes inside the answer cannot be cut
    short at all, and `whole` is what comes back: it is long, but it is not broken.
    """
    said = str(said or "").strip()
    if not left_open(said):
        return said
    for part in rest:
        said = (said + " " + str(part or "").strip()).strip()
        if not left_open(said):
            return said
    return str(whole or said).strip()


def sentences(text, splitter):
    """`splitter`'s sentences, with a quotation kept in one piece.

    The sentence splitters in this package cut at a full stop and a space, which is right for a
    paragraph of advice and wrong inside a quoted letter: "...nothing has been done. Please let
    me know when an engineer can come" is one thing to hand over and two sentences to a splitter.
    Half of it reached the person as a sentence of its own - "how do i ask him again" after the
    landlord answer came back as the first half of the letter, quote open. A part that opens a
    quotation belongs with the parts after it until the quote closes, so it is only a sentence
    when the quote in it is finished.
    """
    parts = [part.strip() for part in splitter.split(str(text or "")) if part.strip()]
    out = []
    for part in parts:
        if out and left_open(out[-1]):
            out[-1] = (out[-1] + " " + part).strip()
        else:
            out.append(part)
    return out
