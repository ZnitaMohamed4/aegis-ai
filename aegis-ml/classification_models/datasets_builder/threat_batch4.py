"""Batch 4 — WhatsApp-style, relationship threats, financial coercion, workplace threats"""
import csv, os

OUTPUT = os.path.join(os.path.dirname(__file__), "threat_batch4.py".replace(".py", ".csv"))

# WhatsApp / DM style (short, personal, no context)
whatsapp = [
    "i see you read that. say something or i'm coming over",
    "you left me on read for the last time",
    "pick up your phone or i'll be at your door in 20 minutes",
    "i know you're awake. answer me or deal with what comes next",
    "last warning before i show up",
    "you have 10 minutes to reply before i do something stupid",
    "don't make me come there",
    "you're testing me and you know exactly what that means",
    "i'm outside. come out and face me like you talk on here",
    "read my messages again. this is your last chance to respond",
    "i'm giving you one hour. after that i can't promise anything",
    "blocking me was a mistake. you'll see that very soon",
    "you deleted me from your contacts. that was brave. let's see how brave you are in person",
    "i know your schedule. i'll be at the bus stop tomorrow. we need to talk",
    "if you're not home in 30 minutes i'm contacting your family",
    "we can do this easy or hard. your choice but reply NOW",
    "why are you at his place right now. you have one chance to explain",
    "you think leaving the group chat helps? i know where you live",
    "don't bother blocking this number. i have six more",
    "show me the proof or i post everything we have — you have five minutes",
    "i tracked your location from that photo you posted. nice neighborhood",
    "you left the group but you can't leave the situation. call me",
    "replying 'ok' is not good enough. call me right now or this escalates",
    "you muted my notifications? unmute them and pick up",
    "i can be very patient or very impatient — right now i'm choosing impatient",
]

# Relationship / intimate partner threats
relationship = [
    "if you leave me i will destroy everything we built together and you will have nothing",
    "you think you can just walk out? i'll make sure no one ever wants you after i'm done",
    "i'll tell everyone what you did — every detail — if you file those papers",
    "you'll never see the kids again if you go through with this",
    "go ahead and leave — i'll be at your mother's house by morning",
    "you belong to me and that doesn't end because you want it to",
    "i'll hurt myself and tell everyone it was you if you leave",
    "you leave and i ruin your career with one email to your boss",
    "you have nowhere to go that i won't follow you to",
    "i will make every day of your new life a living nightmare",
    "you think a restraining order will stop me? it's a piece of paper",
    "the second you walk out that door everything changes for the worse — for you",
    "i'll take the children and disappear before any court can do anything about it",
    "you will never date again after i'm done spreading what i know about you",
    "if i can't have you nobody will — and i mean that literally",
    "leaving me was the worst decision of your life and you'll understand that soon",
    "i will make you watch everything you care about burn down",
    "i'll call your boss every day until you lose your job if you do this",
    "i will show your family every private thing you ever sent me",
    "you have one chance to come back — after that the gloves come off",
]

# Financial / extortion threats
financial = [
    "pay me by tonight or i send those files to your employer tomorrow morning",
    "you have 48 hours to transfer the money or things get ugly fast",
    "i know you have the money — pay up or everyone finds out what you did",
    "consider this a professional courtesy: settle the debt or face professional consequences",
    "i'll destroy your credit rating and your reputation if you default on this",
    "you owe me and i collect one way or another — money or pain",
    "transfer it now or your wife gets a very detailed email tonight",
    "you think i'm bluffing? miss one more payment and find out",
    "i'll sue you, destroy you online, and make sure you never work in this industry again",
    "you'll pay me what you owe or i'll take it out of your hide",
    "your little business will be in flames by the end of the month if you don't pay",
    "i have documentation of every transaction — pay or i go to the authorities with all of it",
    "one wire transfer and this goes away — refuse and nothing goes away",
    "the interest on what you owe is pain — start paying",
    "i have partners who specialize in collecting debts from people like you",
]

# Workplace / professional threats
workplace = [
    "keep talking about me to HR and see what i do to your reputation",
    "i will make sure you never get hired anywhere in this industry after what you did",
    "you think you can fire me and nothing happens? watch what happens next",
    "i know where the bodies are buried in this company and i'll start digging",
    "email my boss one more time and i'll email yours with everything i know about you",
    "i have recordings of every meeting — be very careful what you say next",
    "i'll go to the press with everything if you don't reinstate me immediately",
    "i know exactly which regulations you've been violating — pay me or i report everything",
    "one call to your biggest client and your entire account collapses — fix this now",
    "you promoted her over me — that was a mistake you'll regret professionally and personally",
    "i'll destroy your professional network one contact at a time",
    "you'll receive a very public and very detailed exposé if this isn't resolved today",
    "i kept all your dirty emails — don't make me use them",
    "your investors will be very interested in what i have to say — unless we settle this",
    "i have screenshots of every policy violation in this office — don't push me",
]

def rows(lst, tag, label="threat"):
    return [{"text": t.strip(), "label": label, "language": "en",
             "source_dataset": tag, "routing_method": "synthetic_llm"} for t in lst]

all_rows = (rows(whatsapp, "augment_whatsapp_dm")
          + rows(relationship, "augment_relationship")
          + rows(financial, "augment_financial_coercion")
          + rows(workplace, "augment_workplace"))

print(f"Batch 4: {len(all_rows)} rows")
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["text","label","language","source_dataset","routing_method"])
    w.writeheader(); w.writerows(all_rows)
print("Done:", OUTPUT)
