"""Batch 7 — Final top-up to cross 8K. Extra template diversity."""
import csv, os, random

OUTPUT = os.path.join(os.path.dirname(__file__), "threat_batch7.csv")
random.seed(777)

# New template slots to increase uniqueness
OPENERS = [
    "listen carefully:", "hear me:", "last warning:", "final notice:",
    "for the record:", "make no mistake:", "understand this:", "",
    "pay attention:", "i'm saying this once:",
]

CORE_THREATS = [
    "you will not come out of this okay",
    "i am going to make your life unbearable",
    "what i do to you will be unforgettable",
    "the consequences for you will be severe and lasting",
    "i am going to take you apart piece by piece",
    "you are going to regret every single decision that led to this",
    "i will leave nothing of the life you've built",
    "you are going to feel this for a very long time",
    "i will make sure you never forget my name",
    "the damage i inflict will not be reversible",
    "i will be your worst memory",
    "i am going to dedicate myself to your suffering",
    "you will lose everything that matters to you",
    "i promise you a level of pain you haven't imagined",
    "i will be the reason you can't sleep at night",
    "there is no version of this where you come out okay",
    "i am going to reduce everything you are to rubble",
    "what happens to you next is fully in my hands",
    "i will make every day harder than the last",
    "you will wish you'd never been born by the time i'm finished",
    "i will not stop until you've lost everything",
    "there are no limits to what i'm willing to do to you",
    "i am going to hunt you across every platform you use",
    "you are in my crosshairs and i don't miss",
    "i will rip apart your reputation one piece at a time",
    "the pain you've caused me multiplied is what you're owed",
    "i will expose you completely and permanently",
    "i am going to destroy everything you worked for",
    "you will not escape what you've set in motion",
    "i will come for you in every arena that matters to you",
]

CLOSERS = [
    "don't say i didn't warn you",
    "you have no one to blame but yourself",
    "this is the last thing i'll say before i act",
    "you should've thought about this earlier",
    "the clock is running",
    "consider your next move carefully",
    "i'll enjoy every second of it",
    "this was your choice",
    "good luck — you'll need it",
    "you've been warned",
    "",
]

rows = []
seen = set()
attempts = 0
while len(rows) < 800 and attempts < 20000:
    attempts += 1
    opener = random.choice(OPENERS)
    core = random.choice(CORE_THREATS)
    closer = random.choice(CLOSERS)
    parts = [p for p in [opener, core, closer] if p]
    if opener and core:
        sentence = " ".join(parts)
    else:
        sentence = " ".join(parts)
    sentence = sentence.strip()
    key = sentence.lower()
    if key not in seen and len(sentence) > 15:
        seen.add(key)
        rows.append({"text": sentence, "label": "threat", "language": "en",
                     "source_dataset": "augment_template_v3", "routing_method": "synthetic_llm"})

print(f"Batch 7: {len(rows)} rows")
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["text","label","language","source_dataset","routing_method"])
    w.writeheader(); w.writerows(rows)
print("Done:", OUTPUT)
