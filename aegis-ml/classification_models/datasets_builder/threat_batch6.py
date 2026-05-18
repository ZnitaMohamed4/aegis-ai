"""
Batch 6 — Large-scale varied threat generation to reach 8K total.
Uses richer template expansion + many hand-crafted examples.
"""
import csv, os, random, itertools

OUTPUT = os.path.join(os.path.dirname(__file__), "threat_batch6.csv")
random.seed(123)

# ── Rich template system ─────────────────────────────────────────────────────
SUBJECT = ["i", "we", "my crew", "my people"]

MODAL_THREAT = [
    "will {V} you",
    "am going to {V} you",
    "swear i'll {V} you",
    "promise i'm going to {V} you",
    "guarantee i will {V} you",
    "can and will {V} you",
    "won't hesitate to {V} you",
]

VERBS_PHYSICAL = [
    "beat", "hurt", "destroy", "bury", "break", "end", "finish",
    "pound", "knock out", "put in the hospital", "slam",
    "drag", "stomp", "wreck", "crack your skull", "snap",
    "choke", "strangle", "put down", "lay out",
]

VERBS_LIFE = [
    "ruin", "destroy", "dismantle", "expose", "humiliate",
    "embarrass", "obliterate", "erase", "annihilate",
    "demolish", "burn down", "devastate", "wreck",
    "tear apart", "strip away everything from",
]

VERBS_FIND = [
    "find you", "track you down", "hunt you down",
    "locate you", "come for you", "come find you",
]

CONDITIONALS = [
    "if you don't stop",
    "if you keep this up",
    "if you show your face here again",
    "if you don't pay me back by {time}",
    "if you don't take that down",
    "if you don't call me right now",
    "if you keep talking",
    "if you come near me again",
    "if you don't fix this",
    "if you ever do that again",
    "if you cross me one more time",
    "if you ignore this message",
    "if you don't apologize publicly",
    "if you keep running your mouth",
    "if you don't leave her alone",
]

ENDINGS = [
    "and i mean every word",
    "this is not a joke",
    "consider yourself warned",
    "you've been told",
    "screenshot this",
    "i promise you that",
    "don't test me",
    "you will see",
    "mark my words",
    "i am dead serious",
    "",  # no ending
]

TIMES = ["tonight", "24 hours", "the end of the day", "an hour", "5 minutes"]

def make_conditional(c):
    if "{time}" in c:
        c = c.replace("{time}", random.choice(TIMES))
    return c

def generate_templates(n=2000):
    results = set()
    attempts = 0
    verb_pools = [VERBS_PHYSICAL, VERBS_LIFE, VERBS_FIND]
    while len(results) < n and attempts < n * 20:
        attempts += 1
        subj = random.choice(SUBJECT)
        modal = random.choice(MODAL_THREAT)
        vpool = random.choice(verb_pools)
        verb = random.choice(vpool)
        modal_filled = modal.replace("{V}", verb)
        cond = make_conditional(random.choice(CONDITIONALS))
        ending = random.choice(ENDINGS)

        # Assemble in different orders
        patterns = [
            f"{subj} {modal_filled} {cond}" + (f" — {ending}" if ending else ""),
            f"{cond.capitalize()}, {subj} {modal_filled}" + (f" — {ending}" if ending else ""),
            f"{subj} {modal_filled}" + (f" — {ending}" if ending else ""),
        ]
        sentence = random.choice(patterns).strip()
        if len(sentence) > 10:
            results.add(sentence)
    return list(results)

generated = generate_templates(2500)
print(f"Template-generated: {len(generated)}")

# ── High-quality hand-written additions ─────────────────────────────────────
extra_direct = [
    "every single one of you involved is going to pay for this",
    "i've been merciful up to now — that mercy is finished",
    "i will get to you whether it takes a week or a year",
    "you should start saying your goodbyes because i'm coming",
    "the way you treated me has consequences that are arriving shortly",
    "i will make you feel as small and helpless as you made me feel",
    "you're operating like someone with no enemies — that ends today",
    "i've spent the last week planning exactly what i'm going to do to you",
    "every resource i have is now pointed at making your life miserable",
    "i've never followed through on something this seriously — until now",
    "you will not walk away from what's coming without lasting damage",
    "you should never have made me your enemy — biggest mistake of your life",
    "i know your weak points and i'm going to hit every single one of them",
    "i will strip you of everything you have with a smile on my face",
    "the law won't protect you from what i have planned",
    "you've cornered me and a cornered person has nothing to lose",
    "i'm going to make this personal because you made it personal first",
    "you will beg me to stop and that moment cannot come soon enough",
    "i will systematically dismantle every good thing in your life",
    "be afraid of me — that's the right emotion to have right now",
    "i am going to make an example of you that nobody forgets",
    "i'll find your pressure point and push until something breaks",
    "you've given me a reason and i've given myself permission",
    "i'm going to hold you accountable in the most painful way possible",
    "run your calculations again — none of them end well for you",
    "you have miscalculated who you're dealing with and you'll pay for that",
    "i am the thing you should have been afraid of from the start",
    "you've forced my hand and my hand is not gentle",
    "i want you to know exactly who is responsible when it happens",
    "the problem with your plan is that i'm part of it — and i'm very unhappy",
    "nobody who has crossed me the way you have walked away unscathed",
    "you opened a door you can't close now — i'm walking through it",
    "i will make the next chapter of your life extraordinarily difficult",
    "i'm patient, i'm methodical, and i'm coming for you",
    "you've made this into a war and i don't lose wars",
    "i am going to take this all the way — every last bit of it",
    "you think you're safe because you haven't heard from me — that's the plan",
    "the damage i can do to your life from here is extraordinary",
    "i'm going to destroy you so completely you won't recognize the ruins",
    "what's coming is proportional to what you did — so brace yourself",
    "i have been preparing for this conversation my entire life",
    "you will spend the rest of your days regretting the day you chose to do this",
    "i'm done negotiating — i'm done warning — i'm done holding back",
    "the person you made me into is someone you really don't want to meet",
    "you lit the fire — i'm the fire",
    "nothing you do in the next 24 hours will stop what's already in motion",
    "i'm going to prove to you that i am exactly who you should have feared",
    "you'll understand soon — i promise you'll understand soon",
    "i've never been more certain about anything than i am about this",
    "sleep while you can — productivity requires rest and i am very productive",
    "tick tock — you can hear it if you're quiet enough",
]

extra_indirect = [
    "you're going to have a very interesting few weeks",
    "let's just say i've made some arrangements that concern you",
    "i hope your support system is strong because you're going to need it",
    "you should look both ways more carefully from now on",
    "things tend to fall apart for people who do what you did",
    "i suggest you start getting your affairs in order",
    "i can be very creative when i'm motivated and you've motivated me",
    "your comfortable life is more fragile than you realize",
    "i'll let karma handle it — i've given karma a very detailed brief",
    "you're about to have the most educational experience of your life",
    "what a shame it would be if your secrets stopped being secret",
    "you might want to prepare your loved ones for some surprising information",
    "every comfort you have right now is on borrowed time",
    "i'm working on something very special for you — you won't have to wait long",
    "i hope you've enjoyed the quiet because it's the last of it",
    "you'll know it was me but you won't be able to prove it",
    "consider your next action very very carefully",
    "you won't see it coming but you'll definitely feel it",
    "some things are irreversible — i'm about to make several of those things happen",
    "i don't need to be loud to be effective",
]

extra_teen = [
    "bro moved wrong and is going to find out why that was a mistake",
    "you're chatting a lot for someone who can't back it up irl",
    "pull up then if you're about it — stop hiding behind your phone",
    "bro is all talk until the smoke comes real quick",
    "one of my boys saw you — you should've stayed inside today",
    "i'll catch a case over you and still think it was worth it fr",
    "you think it's jokes? you'll stop laughing real soon",
    "bro typed all that and thought he was safe 💀 wrong",
    "move stupid and get treated stupid — simple math my g",
    "say my name one more time and i'll come find out what yours sounds like in pain",
    "bro is behind a screen until he's not — we'll see",
    "you're giving off energy that's going to get you rocked bro",
    "the day you see me offline is the day you realize i wasn't playing",
    "next time you talk reckless check if anybody in the room has my contact first",
    "bro tested the fence and the fence is electric rn",
]

extra_relationship = [
    "if you think leaving solves anything wait until you see what i do next",
    "every good thing i ever said about you becomes ammunition now",
    "you walked out — i don't accept that and i never will",
    "i will make it my mission to undo everything you're trying to build",
    "the person you're leaving me for will pay the same price you're paying",
    "i'll never let you be happy with someone else — i'll make sure of it",
    "every memory we have together becomes a weapon in my hands now",
    "try to move on and see how far you get before i remind you of me",
    "i will not be replaced and forgotten — you are going to learn that",
    "you don't get a happy ending after what you did to me",
]

all_rows = []
for t in generated:
    all_rows.append({"text": t, "label": "threat", "language": "en",
                     "source_dataset": "augment_template_v2", "routing_method": "synthetic_llm"})
for lst, tag in [
    (extra_direct, "augment_direct"),
    (extra_indirect, "augment_indirect"),
    (extra_teen, "augment_teen_slang"),
    (extra_relationship, "augment_relationship"),
]:
    for t in lst:
        all_rows.append({"text": t, "label": "threat", "language": "en",
                         "source_dataset": tag, "routing_method": "synthetic_llm"})

random.shuffle(all_rows)
print(f"Batch 6 total: {len(all_rows)} rows")

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["text","label","language","source_dataset","routing_method"])
    w.writeheader(); w.writerows(all_rows)
print("Done:", OUTPUT)
