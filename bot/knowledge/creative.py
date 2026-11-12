"""Writing craft: why a draft feels flat, and how to get a story moving.

The verse requests are already answered (`bot/knowledge/entertainment.py` has the poem, limerick,
haiku and rhyme tables), so nothing here writes anything for you. What was still a shrug is the
craft question underneath: "how do i make my writing less boring" came back as "I'd rather not
guess", and "how do i start a story" got a sample story rather than the thing that makes one run.

Two entries only, both about the writing rather than the subject, and both pass (return None) on
anything that names a subject to write about, so entertainment.py keeps every verse request.
"""

from .lookup import entry

ANSWERS = ("creative", "language-and-writing")


def _story(memory, understood):
    """A story that holds up: the engine, and what makes a detail believable."""
    return ("Build it from a want, a wall and a turn: what the character wants in the first "
            "scene, what stops them, and the one thing that changes the plan. A plot that sounds "
            "far-fetched is usually missing the practical steps - the key, the alibi, the person "
            "who noticed - so make the method vague and the aftermath exact: the cup half drunk, "
            "the dog still alive, the wrong person blamed. If you want a villain's plan to be "
            "believable, give them one small mistake a careful reader could spot on a second "
            "read, and let a minor character be the one who spots it.")


def _prose(memory, understood):
    """How to make flat writing less flat, in the order that changes the most per minute."""
    return ("Cut the adverbs and put one thing a reader can see in every paragraph: not 'the "
            "kitchen was messy' but 'the bin was full of cereal boxes'. Then vary the sentence "
            "length - short where it is tense, longer where it is calm - and read it aloud, "
            "because the sentence you stumble on is the one to fix. That is three passes, and "
            "they fix most flat writing.")


def _naming(memory, understood):
    """A name for a shop, a band, a stall: the method, with the examples that show it."""
    return ("Name the thing, not the idea: a bakery called Crust, a cafe called The Second Cup, "
            "a band called The Rosy Hours. Two short words joined - place plus trade, your own "
            "name plus what you sell - beats anything clever, because people have to say it out "
            "loud and spell it down a phone. Say it with 'I'm just going to' in front of it, check "
            "that the domain and the social handle are free before you fall in love with it, and "
            "check Companies House for the limited company: a name can be yours to trade under "
            "and still be taken as a company.")


ENTRIES = [
    entry("story-craft",
          (("story", "stories", "plot", "novel", "script", "screenplay", "character", "fiction",
            "villain", "chapter"),
           ("stuck", "idea", "ideas", "start", "where do i start", "believable", "realistic",
            "convincing", "plot", "plan", "help me", "help", "how do i write", "what should",
            "make it work", "going nowhere")),
          _story, bias=1,
          # A request for a story, or for a book to read, is not a question about how stories
          # work: entertainment.py writes the sample and the recommendation entries pick the book.
          # The verb in an avoid list is matched loosely, so "write a story" also turned away
          # "im writing a story where the villain poisons the king" - the very line this entry
          # is for. Only the request shapes are listed.
          avoid=("write me a story", "write us a story", "tell me a story", "make up a story",
                 "read next", "recommend", "suggest", "should i read", "to read", "book for",
                 "gift", "present", "book club", "audio book", "audiobook")),
    entry("make-writing-better",
          # "how do i make my essay more interesting" is answered by the essay-plan entry, and
          # that plan-first answer is the better one for it, so "essay" stays out of this key.
          (("writing", "prose", "description", "paragraph", "paragraphs", "draft", "blog post"),
           ("boring", "flat", "dull", "better", "improve", "punchier", "livelier", "read better",
            "less boring", "more interesting", "tighten", "bland")),
          _prose, bias=1,
          # "how do i make my writing smaller" is a handwriting question, and a spelling or
          # grammar question is language.py's.
          avoid=("handwriting", "smaller", "neater", "pen", "spelling", "grammar", "font",
                 "size")),

    entry("name-a-business",
          # "suggest a name for a small bakery" and "name ideas for a band" were honest passes.
          # The thing named sits in the second arm so the first can stay about naming.
          (("name", "names", "naming", "call it", "called", "what to call"),
           # a band, a group, a duo is `band-name` in entertainment.py, which already answers it;
           # this row is the shop on the corner
           ("business", "shop", "bakery", "cafe", "caf", "restaurant", "company", "brand",
            "team", "podcast", "blog", "stall", "startup", "start up", "etsy", "pub",
            "salon", "studio", "brand name", "small business", "side hustle", "market stall",
            "youtube channel", "newsletter")),
          _naming, bias=1,
          # asking for the name of a shop they already have, or a name for a pet or a baby, is
          # another module's question
          avoid=("puppy", "kitten", "dog", "cat", "hamster", "rabbit", "guinea", "parrot",
                 "budgie", "horse", "pony", "tortoise", "baby", "baby name", "baby names",
                 "what is it called", "whats it called", "what is the name of", "called again"),
          ask=("suggest", "suggestion", "suggestions", "ideas", "idea", "any", "good",
               "help me", "come up with", "think of", "what should i", "what could i",
               "what would you", "how do i name", "name for", "name ideas", "pick a name",
               "choose a name", "shortlist")),
]
