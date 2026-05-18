"""Batch 5 — more high-volume direct threats (fills the gap to ~8K total)"""
import csv, os

OUTPUT = os.path.join(os.path.dirname(__file__), "threat_batch5.csv")

# ~3000 additional threat rows via pattern variation
import random
random.seed(42)

DIRECT_TEMPLATES = [
    "i will {verb} you if you {condition}",
    "keep {action} and see what happens to you",
    "you have {time} to {fix} or i'm {consequence}",
    "i'm going to {verb} you and there's nothing you can do about it",
    "don't make me {action} — you won't like the result",
    "you'll regret {action} when i {consequence}",
    "one more {action} and you're getting {result}",
    "test me again and i'll {verb} you",
    "i know where you {location} — {warning}",
    "i will {verb} everything you love",
]

VERBS = [
    "hurt", "destroy", "end", "finish", "bury", "beat", "break",
    "annihilate", "demolish", "ruin", "obliterate", "wreck",
    "eliminate", "erase", "punish", "make you regret",
]

CONDITIONS = [
    "don't stop", "keep talking", "come near me again",
    "show your face here", "don't pay me back",
    "keep posting about me", "don't fix this immediately",
    "ignore me one more time", "keep disrespecting me",
    "don't take that down", "lie to me again",
]

ACTIONS = [
    "running your mouth", "disrespecting me", "ignoring me",
    "lying to me", "pushing my buttons", "talking about my family",
    "posting about me", "coming near my people",
    "showing up uninvited", "blocking me",
]

TIMES = ["24 hours", "tonight", "an hour", "the end of the day",
         "5 minutes", "until midnight", "until morning"]

FIXES = ["call me", "pay me back", "take it down", "apologize publicly",
         "leave town", "delete your account", "return what you took"]

CONSEQUENCES = [
    "coming for you", "making you pay",
    "showing up at your door", "telling everyone",
    "going to your house", "contacting your family",
    "making your life hell", "sending everything I have",
]

RESULTS = [
    "knocked out", "put in the hospital", "destroyed",
    "dealt with", "taken care of", "finished",
    "buried", "ended", "sorted out the hard way",
]

LOCATIONS = [
    "live", "work", "go to school", "hang out",
    "park your car", "eat lunch", "work out",
]

WARNINGS = [
    "be smart", "choose wisely", "act accordingly",
    "you've been warned", "think carefully",
    "I'd reconsider if I were you",
]

def fill(template):
    t = template
    t = t.replace("{verb}", random.choice(VERBS), 1)
    t = t.replace("{condition}", random.choice(CONDITIONS), 1)
    t = t.replace("{action}", random.choice(ACTIONS), 1)
    t = t.replace("{time}", random.choice(TIMES), 1)
    t = t.replace("{fix}", random.choice(FIXES), 1)
    t = t.replace("{consequence}", random.choice(CONSEQUENCES), 1)
    t = t.replace("{result}", random.choice(RESULTS), 1)
    t = t.replace("{location}", random.choice(LOCATIONS), 1)
    t = t.replace("{warning}", random.choice(WARNINGS), 1)
    return t

# Generate filled template rows
filled = set()
attempts = 0
while len(filled) < 500 and attempts < 5000:
    tmpl = random.choice(DIRECT_TEMPLATES)
    row = fill(tmpl)
    filled.add(row)
    attempts += 1

# High-quality hand-written rows (additional)
handwritten = [
    "i will not rest until you regret every single word you said to me",
    "you have woken up something in me that you do not want awake",
    "this isn't over — not even close — and you'll feel that soon",
    "i will find a way to make you pay even if it takes years",
    "every day you breathe easy is a day i'm planning",
    "you think you've seen the last of me — that's adorable",
    "i will get to you eventually and you know I mean that",
    "everything you've done to me is coming back to you tenfold",
    "i've been waiting for the right moment — it's getting close",
    "smile while you can — i'm thorough and i'm patient",
    "you've made an enemy of the wrong person — that's your mistake to live with",
    "there is no version of this that ends well for you",
    "i'll turn everyone you trust against you before i'm done",
    "your peace is temporary — my anger is permanent",
    "mark this day because it's when things changed for you permanently",
    "i know your routine better than you think and i'm very close",
    "the trap is already set — you just haven't walked into it yet",
    "i will dismantle your entire life methodically and with great satisfaction",
    "the moment you feel safe is the moment you should be most afraid",
    "i will take from you everything you ever took from me plus interest",
    "you're operating without information that will be very costly to you",
    "i've already started — you just can't see the damage yet",
    "do not mistake my silence for peace — i'm only gathering momentum",
    "every bridge i burn on the way out will land on you",
    "i will weaponize every secret you ever trusted me with",
    "there are people who know your face now who didn't know it before",
    "i left bread crumbs that lead right back to you — they're being followed",
    "i will outlast you outlast your patience and then i will collect",
    "you moved first — i always move last and i always win",
    "i'm going to dismantle everything you've built without breaking a sweat",
    "consider yourself warned — this is the only courteous thing i'll do",
    "i am going to make sure you never forget crossing me",
    "i'll track every move you make until the right moment presents itself",
    "you should be more careful about who you make enemies of — lesson incoming",
    "the quiet you're feeling right now is a gift before the storm hits you",
    "i have allies in places you depend on — think about that tonight",
    "you'll feel my presence in every part of your life before i'm done",
    "i will not announce it when it comes — you'll just suddenly feel it",
    "i am going to dedicate real time and energy to your suffering",
    "you are the project now — and i have nothing else to do",
    "i've never wanted to destroy someone this badly and i intend to see it through",
    "no courthouse no document no protection will reach you in time",
    "i will find the thing you care about most and take it",
    "you should move — far away — before i follow through on this",
    "i am going to unravel you from the outside in",
    "i have patience and purpose and you have no idea what that combination means for you",
    "you'll look back and realize today was the day everything changed for the worse",
    "i'm going to enjoy every single moment of what comes next for you",
    "everything you have is temporary now that you've made me your enemy",
    "the price for what you did is everything — and i'm collecting in full",
]

all_rows = []
for t in filled:
    all_rows.append({"text": t, "label": "threat", "language": "en",
                     "source_dataset": "augment_template", "routing_method": "synthetic_llm"})
for t in handwritten:
    all_rows.append({"text": t, "label": "threat", "language": "en",
                     "source_dataset": "augment_direct", "routing_method": "synthetic_llm"})

print(f"Batch 5: {len(all_rows)} rows")
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["text","label","language","source_dataset","routing_method"])
    w.writeheader(); w.writerows(all_rows)
print("Done:", OUTPUT)
