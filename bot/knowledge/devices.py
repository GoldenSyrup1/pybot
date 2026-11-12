"""Storage on a computer: a Mac and a Windows PC are emptied in different places.

`technology`'s storage rows keyed on the bare words "storage", "space" and "free up" and
answered with Settings > General > iPhone Storage. That screen does not exist on a Mac or a
PC, so the commonest laptop question of all -

    how do i free up space on my mac      -> Settings > General > iPhone Storage ...

got a phone answer, and "i need to make room on my mac" got nothing at all. A Mac and a PC
are also not the same job: a Mac hides photos, iPhone backups and the Bin behind one Storage
pane, while Windows puts its leftovers under Temporary files and Storage Sense.

So this domain answers one question per machine, and reads the machine out of the line. It
passes on a line that names no computer, which leaves the phone rows and everything else in
`technology` exactly as they were.
"""
from .lookup import entry

ANSWERS = ("technology",)

# The words that name the machine. A Mac line names it ("mac", "macbook", "on my Mac"); a PC
# line may name it ("windows", "pc") or only its parts ("hard drive", "ssd").
MAC = ("mac", "macs", "macbook", "macbooks", "mac book", "imac", "i mac", "mac os", "macos",
       "osx", "os x", "apple computer", "apple laptop")
PC = ("windows", "pc", "pcs", "desktop", "desktops", "laptop", "laptops", "thinkpad",
      "chromebook", "surface", "computer", "computers", "hard drive", "hard disk", "ssd",
      "disk")

# How a line talks about running out of room.
ROOM = ("storage", "space", "full", "free up", "clear", "delete", "disk", "running out",
        "make room", "room", "no space", "space left", "out of space", "no room")
ASK = ("storage", "space", "full", "free up", "clear", "delete", "disk", "room", "running out",
       "out of")
# A PC line may name Windows, or only the part that is full ("my ssd is full"), or ask how much
# is left. A bare "how do i free up space on my laptop" names no machine, so it keeps the answer
# it had: this domain only takes a line that says which machine, not one that makes us guess.
PC_ASK = ("windows", "pc", "pcs", "desktop", "disk", "hard drive", "hard disk", "ssd",
          "computer", "computers", "thinkpad", "chromebook", "surface", "space left",
          "space is left", "no space", "out of space")

# "How much room have I got" is a different answer from "how do I make room": one points at the
# screen that shows the total, the other at the steps that empty it.
CHECK = ("how much", "how full", "how many gb", "how big", "space left", "space is left",
         "no space left", "enough space", "percent", "%")

# A third key, so "how much space is left on my laptop" is a storage question and not the price
# of a laptop: the words of a question about the total are not the words of one about a fault.
# "have" and "got" are not here: with `ROOM`'s "running out" they made every "i have run out
# of flour / sugar / milk / rice / money / washing powder" a full Mac disk, because "i have run
# out of sugar" carries both. A storage question says "left", "how much" or "shows" instead.
HOW_MUCH = ("space left", "is left", "left", "shows", "how much", "how full", "how many")

# "Delete an app" is uninstalling one; "delete" on its own is a storage question. The phrases
# are what stand a storage row down, so a Mac or PC line about a full disk still gets the steps.
NOT_STORAGE = ("delete an app", "delete apps", "delete a app", "deleting an app", "delete the app",
               "delete my app", "delete an application", "delete the application", "remove an app",
               "removing an app", "uninstall", "uninstalling",
               # A calorie question about macaroni cheese is a food question, not a disk: "mac"
               # in the dish name was reaching the storage row. The same words stand down the
               # PC row, because "how many calories in mac and cheese" names no machine at all.
               "calorie", "calories", "kcal", "mac and cheese", "mac n cheese",
               "macaroni and cheese", "macaroni cheese", "macaroni",
               # a program is software, not the room left on the drive: "how do i delete a
               # program from my pc" was given the Temporary files tour. "free up space" and
               # "storage" lines still name the drive, which is what this row is for.
               "program", "programs", "uninstalled", "reinstalled",
               # "windows" and "room" are both decorating words too, so "how do i paint a room
               # with no windows" reached the steps that empty a Downloads folder. These are the
               # phrases a painter says; every real disk line keeps its answer.
               "paint a room", "painting a room", "paint the room", "paint a wall",
               "paint the walls", "paint over", "painting over", "decorating", "decorate",
               "roller", "emulsion", "undercoat", "skirting", "wallpaper", "gloss paint")
# "window" and "room" are house words before they are machine words. "its a small room with no
# window" and "my living room needs a bigger window" hold "window" for Windows and "room" for the
# room left on a drive, so a decorating line got the steps that empty a Downloads folder. Only the
# forms that cannot be about a machine go here: "make room on my mac" keeps its answer.
# A window is a pane of glass before it is an operating system: "how do i clear condensation off
# the windows" held "clear" for the room left on a drive and "windows" for the OS, so a glass line
# got the steps that empty a Downloads folder. Only forms that cannot be about a machine go here.
GLASS = ("condensation", "condensation on", "condensation off", "condensed", "steamed up",
         "steaming up", "steams up", "misted up", "misting up", "fogged up", "fogging up",
         "wet windows", "windows wet", "damp on the windows", "pane", "panes", "squeegee",
         "windscreen", "windshield", "cleaning the windows", "clean the windows",
         "clean windows")
HOUSE = ("living room", "bedroom", "bedrooms", "kitchen", "bathroom", "hallway", "conservatory",
         "floorboards", "wallpaper", "skirting", "no window", "no windows", "windowless",
         "without a window", "bigger window", "curtains", "blinds") + GLASS

PHONE = ("phone", "iphone", "ipad", "android", "tablet", "handset", "sd card", "memory card",
         "usb stick", "usb drive", "external drive", "self storage", "warehouse", "garage",
         "shed", "loft", "attic", "rent")
OTHER = ("battery", "charge", "charging", "charger", "power", "slow", "sluggish", "hot",
         "overheating", "fan", "noisy", "loud", "memory", "ram", "backup", "time machine",
         "broken", "repair", "replace", "buy", "worth", "price", "cost")

MAC_SPACE = (
    "On a Mac: Apple menu > System Settings > General > Storage, click the bar and let it finish "
    "scanning - Photos and old iPhone backups are usually the two biggest. Empty the Bin, clear "
    "the Downloads folder, and turn on Optimise Mac Storage in Photos. A phone backup can be "
    "50GB on its own: Finder > your phone > Manage Backups.")
PC_SPACE = (
    "On Windows: Settings > System > Storage, then Temporary files - Windows Update leftovers and "
    "old installers are usually a few gigabytes. Turn on Storage Sense so they go on their own, "
    "then sort the Apps list by size and move photos and videos to an external drive or OneDrive. "
    "The Downloads folder is the other quiet hog.")
BOTH_SPACE = (
    "On a Mac: Apple menu > System Settings > General > Storage, then empty the Bin and clear "
    "Downloads. On Windows: Settings > System > Storage > Temporary files, and turn on Storage "
    "Sense. Photos, videos and old installers are the biggest three either way.")
BOTH_CHECK = (
    "On a Mac: Apple menu > System Settings > General > Storage. On Windows: Settings > System > "
    "Storage. Both show what is left and what is taking it, biggest first; keep 10 to 20% free.")
MAC_CHECK = (
    "Apple menu > System Settings > General > Storage shows the bar and what is taking it, biggest "
    "first. Keep about 10 to 20% free: below that a Mac slows down and updates refuse to install.")
PC_CHECK = (
    "Settings > System > Storage shows what is left and what is taking it, biggest first. Keep "
    "about 10 to 20% free: below that Windows slows down and updates fail to install.")


SD_CARD_COPY = (
    "Copy things off it before you delete anything: a card that fills up in a camera is often a "
    "confused file table, and bulk deleting on the camera loses shots. Plug the card into a "
    "laptop with a reader, drag the photos and videos to the computer or to Google Photos, then "
    "let the camera format the card from its own menu - not the computer. A bigger card is cheap: "
    "64GB is about a tenner, and take one labelled U3 or V30 if it is for video.")
SD_CARD_BUY = (
    "64GB to 128GB is plenty for photos, and 128GB or more for video, because a minute of 4K is "
    "about 400MB. Look for U3 or V30 on the label - that is a guaranteed write speed, and it is "
    "what 4K video needs - and buy from a shop you trust rather than a marketplace stall, because "
    "fake cards report more room than they have and then lose files. SanDisk, Samsung and Lexar "
    "are the safe names; a card is cheap enough to buy two.")
_BUYING_A_CARD = ("which", "what card", "what sd", "should i buy", "should i get", "recommend",
                  "best card", "best sd", "best memory", "worth buying", "how big", "what size",
                  "which size", "for video", "for a camera", "for my camera", "buying",
                  # A card's size is the buying question however it is asked: "can i put a
                  # bigger sd card in my phone" is asking how big a card to get, and it was
                  # answered with "copy things off it before you delete anything"
                  "bigger", "larger", "bigger card", "bigger sd", "bigger memory",
                  "more space", "more storage", "upgrade", "how much space")


def _sd_card(memory, understood):
    """A full card wants its photos copied off; a card being chosen wants a size and a speed."""
    text = _text(understood)
    if any(word in text for word in _BUYING_A_CARD) and not any(
            word in text for word in ("full", "no room", "no space", "running out")):
        return SD_CARD_BUY
    return SD_CARD_COPY


def _text(understood):
    return " ".join(str(part or "") for part in
                    (understood.get("text"), understood.get("clean"))).lower()


def _names_mac(understood):
    text = _text(understood)
    return any(" " + word in " " + text or text.startswith(word) for word in MAC)


def _names_pc(understood):
    text = _text(understood)
    return any(" " + word in " " + text or text.startswith(word)
               for word in PC if word != "disk")


# A disk word without an operating system is a machine's own disk: "how do i free up disk space"
# names no Mac and no PC, and it has to keep the both-paths answer.
_DISK_WORDS = ("disk", "disc", "hard drive", "hard disk", "ssd", "disk space")


def _names_a_disk(understood):
    text = _text(understood)
    return any(word in text for word in _DISK_WORDS)


def _asking_how_much(understood):
    text = _text(understood)
    return any(word in text for word in CHECK)


def _mac_space(memory, understood):
    # "we have no room in the kitchen" and "i have no space in my flat" carry two words of the
    # key ("no room", "no space") and none of its subject, so the row scored on room alone and
    # answered a kitchen with the Mac's Storage screen. The machine has to be in the line.
    if not _names_mac(understood):
        return None
    return MAC_CHECK if _asking_how_much(understood) else MAC_SPACE


def _pc_space(memory, understood):
    # The same guard as the Mac row, and the disk words count as naming a machine, so
    # "how do i free up disk space" still gets both paths.
    if not (_names_pc(understood) or _names_mac(understood) or _names_a_disk(understood)):
        return None
    how_much = _asking_how_much(understood)
    if _names_mac(understood) and not _names_pc(understood):
        return MAC_CHECK if how_much else MAC_SPACE
    if not _names_pc(understood):
        # "how do i free up disk space" names no machine at all: give both paths rather than
        # send a Mac owner to a Windows settings page.
        return BOTH_CHECK if how_much else BOTH_SPACE
    return PC_CHECK if how_much else PC_SPACE


# A storage card is a small disk, and "my sd card is full" is the room-left question, not the
# credit-card-at-its-limit one: it was answered with a payment plan. The words that name the card
# are the subject, and running out of room is the ask, so the same row covers a memory card in a
# camera, a micro SD in a phone and a usb stick.
SD_CARD = ("sd card", "sdcard", "sd cards", "sd-cards", "micro sd", "microsd", "micro sd card",
           "memory card", "memory cards", "storage card", "flash card", "camera card",
           "photo card", "card in my camera", "card in the camera", "cards in my camera",
           "card for my camera", "card for the camera")
SIM_CARD = ("sim card", "sim cards", "simcard", "simcards", "sim")
CARD_ROOM = ("full", "no room", "no space", "space", "storage", "free up", "clear", "delete",
             "copy", "move", "moving", "running out", "out of space", "fill up", "filled up",
             "filling up", "clean up", "sort out", "back up", "backup", "how much", "room left",
             "replace", "bigger", "buy")
# A sim is not a disk: it holds the number, the contacts and the texts, and it was answering the
# card question only because it carries the word. The phone-contract lines that name a sim are
# the other question and keep their own answer.
SIM_NOT_THIS = ("sim only", "sim-only", "sim deal", "sim deals", "sim contract", "esim", "e-sim",
                "pay monthly", "pay as you go", "tariff", "rolling contract", "cheapest sim",
                "best sim", "which sim", "new sim", "order a sim", "sim free", "sim-free",
                "unlock", "network", "port my number", "switch network", "data plan",
                "upgrade", "cancel", "price", "cost", "cheap", "deal")


# "Mac" is a food as well as a machine: "a big mac", "mac and cheese". The keys here are the
# machine's name, and "how many calories in a big mac" was answered with where the storage screen
# is - the steps for a full Mac disk, to somebody asking about a burger. The words of the food
# stand the machine down for that line; a real Mac line carries none of them.
_FOOD_NOT_A_MACHINE = ("big mac", "mac and cheese", "mac cheese", "macaroni", "calorie",
                       "calories", "burger", "burgers", "mcdonalds", "mcdonald", "kfc")


def _stands_down_for_food(one):
    """A Mac entry, with the food words added to its stay-away list."""
    if not any(isinstance(part, tuple) and "mac" in part for part in one.key):
        return one
    one.avoid = one.avoid + tuple(word for word in _FOOD_NOT_A_MACHINE
                                  if word not in one.avoid)
    return one


ENTRIES = [
    entry("mac-storage-full", (MAC, ROOM, HOW_MUCH),
          # The machine is in the line, so one row answers both questions a person asks
          # about a full disk: what is taking it, and how to get room back.
          _mac_space,
          # The guard is the machine. The key is storage words and "no room" is one of them, so
          # without this "we have no room in the kitchen" reached Apple's Storage pane and beat
          # the home row that answers it. A full disk is a question about a named machine: a line
          # that names none is either another machine's line (the PC row takes "disk", "laptop",
          # "ssd") or not a storage question at all.
          ask=MAC,
          bias=2,
          # A Mac line can carry "disk" or "computer" too ("my mac disk is full"), so only the
          # words that name another machine stand the Mac row down.
          # "delete" is in the key because "what can i delete on my mac" is a storage question,
          # but "delete an app" is uninstalling one, and that answer is not this one. The phrase
          # is held rather than the word, so the storage lines that talk about deleting keep it.
          avoid=PHONE + OTHER + HOUSE + ("windows", "pc", "pcs", "desktop", "desktops",
                                 "thinkpad",
                                 "chromebook", "surface",
                                 # "the wifi shows full bars but nothing loads" is a network
                                 # line: "full" and "shows" covered this row's two groups.
                                 "wifi", "wi-fi", "signal", "bars", "internet", "broadband",
                                 "loads", "loading", "browser",
                                 # A Big Mac is a burger, not the machine: "how many calories in a
                                 # big mac" was answered with the Storage pane on main `a2dbea5`.
                                 "big mac", "big macs") + NOT_STORAGE),
    entry("pc-storage-full", (PC, ROOM, HOW_MUCH),
          _pc_space,
          ask=PC_ASK,
          bias=1,
          avoid=PHONE + OTHER + HOUSE + MAC + NOT_STORAGE),
    # "what is the difference between an ssd and a hard drive" was a shrug on main: two parts
    # that nobody compares in words, so no row held them. The choice is the only question here,
    # and a disk with no room left is a different one - the storage rows answer that.
    entry("ssd-vs-hdd", (("ssd", "ssds", "solid state drive", "solid state", "nvme"),
                         ("hdd", "hdd's", "hard drive", "hard disk", "spinning disk", "disk",
                          "difference", "better", "faster", "slower", "worth", "upgrade",
                          "vs", "versus", "compare", "choose", "buy", "replace")),
          "An SSD has no moving parts, so the machine starts in seconds and apps open at once; a "
          "hard drive is a spinning disc and only wins on price for each gigabyte. For a laptop "
          "the SSD is the one upgrade that makes an old machine feel new - a 500GB one is cheap "
          "now and cloning the old disk across is a job a shop will do in an hour. Buy a big hard "
          "drive only for bulk storage and backups.",
          ask=("difference", "better", "faster", "slower", "worth", "upgrade", "upgrading",
               "upgrad", "vs", "versus",
               "compare", "choose", "buy", "replace", "what", "which", "should"),
          avoid=("space", "full", "free up", "left", "how much", "how many", "storage",
                 "make room", "no room", "running out", "clean up", "delete")),

    entry("sd-card-full", (SD_CARD, CARD_ROOM),
          _sd_card,
          ask=CARD_ROOM, bias=3,
          avoid=("credit card", "bank card", "debit card", "payment", "pay", "owe", "debt",
                 "bill", "money", "borrow", "loan", "santander", "barclays", "halifax",
                 "gift card", "voucher", "birthday card", "christmas card", "greeting card",
                 "playing card", "card game", "loyalty card", "store card", "nectar",
                 "clubcard")),
    # A sim card is full of messages, never photos: it stores the number, the contacts and the
    # texts. Same shelf as the sd card, and a different answer, so it is its own row.
    entry("sim-card-full", (SIM_CARD, CARD_ROOM + ("messages", "texts", "contacts", "numbers")),
          "A sim holds your number, your contacts and your texts, not photos, so what fills it "
          "is old messages. Delete the old texts first, and picture messages go first because "
          "they are big. Copy the contacts to the phone itself or to a Google or Apple account so "
          "they do not live on the card, then back up the texts you want to keep - a new sim "
          "does not bring the old messages with it.",
          ask=CARD_ROOM + ("messages", "texts", "contacts", "numbers"),
          bias=2,
          avoid=SIM_NOT_THIS + ("sim card slot", "sim tray", "no sim", "sim card is not",
                                "insert sim", "sim not working")),
]

ENTRIES = [_stands_down_for_food(one) for one in ENTRIES]
