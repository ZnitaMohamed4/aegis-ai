"""Batch 2 — additional synthetic threat rows"""
import csv, os

OUTPUT = os.path.join(os.path.dirname(__file__), "threat_batch2.csv")

direct = [
    "i will personally see to it that you never feel safe again",
    "you are going to get what you deserve and i'm the one delivering it",
    "i've been holding back for too long — no more",
    "you'll be begging me to stop before i'm done with you",
    "i know exactly when you leave work — just so you know",
    "this is my last message before i come looking for you",
    "one more stunt like that and i'll put you in intensive care",
    "you're going to disappear and nobody will look for you",
    "i will beat you so badly they won't recognize you",
    "you picked the wrong person to mess with — find out why",
    "your days of walking freely are numbered",
    "try to run and i'll make it worse for you — stay put",
    "i'm going to make this very painful for you",
    "i will finish what i started and you can't stop me",
    "i got a crew and they all know your face now",
    "push me one more inch and i'll push you into the ground",
    "you will not survive crossing me — that's not a threat that's a fact",
    "you are officially on my list and i take my list seriously",
    "i will personally deliver your punishment — with pleasure",
    "say my name one more time and see what i do to you",
    "i'll find your car and make sure you can't drive away",
    "every second you ignore me makes what's coming worse for you",
    "i'm already outside — come out and we'll end this",
    "i've done this before and i'll do it again — starting with you",
    "the next time you see me you'll wish you'd apologized when you had the chance",
    "i will make sure every person you care about knows what you did",
    "i'm going to enjoy watching you beg",
    "nowhere you can go that i won't eventually find you — nowhere",
    "i'll catch you slipping and when i do it's over for you",
    "you've made me into something dangerous — you'll feel that soon",
    "think i'm joking? ask the last person who thought the same thing",
    "i have nothing stopping me — you should be scared",
    "i'm going to remove you from my life by force if necessary",
    "you have until end of day to fix this or i act",
    "i'll gut you like you gutted my trust",
    "move wrong and i'll put you in a wheelchair",
    "you broke the wrong person's heart — now face what that unleashes",
    "every night you sleep sound is a gift — that gift ends soon",
    "i've planned exactly how this goes and it does not end well for you",
    "you should've walked away when you had the chance",
    "your protection just ran out — good luck",
    "i will show up everywhere you go until this is settled",
    "you triggered something in me that i can't put back in the bottle",
    "send one more message and i swear to god i'll track you down",
    "i'll put my hands around your throat next time i see you",
    "you will not leave that parking lot tomorrow evening",
    "there's a price on your head and i'm collecting",
    "i'll make sure your family watches what i do to you",
    "you want war? fine — i've been waiting for permission",
    "you crossed the line and now the line is gone — only consequences remain",
]

indirect = [
    "you're very brave for someone with so much to lose",
    "some debts get collected in ways money can't cover",
    "people who play games with me tend to have very bad luck",
    "i just hope your situation doesn't get any more complicated than it already is",
    "be careful — overconfidence has brought down much bigger people than you",
    "funny how quickly good fortune can turn for certain people",
    "i suggest you start thinking about whether this is really worth it",
    "the universe has a way of balancing things — yours needs a lot of balancing",
    "you'd be amazed what a single conversation with the right people can accomplish",
    "i've already put things in motion — you just don't know it yet",
    "enjoy your current circumstances while they last",
    "i have very long arms — distance means nothing to me",
    "decisions made in arrogance are paid for in humility — or worse",
    "i suggest you look at this as your final opportunity to course-correct",
    "the quiet before the storm is the most deceptive part",
    "i hope you've said everything you wanted to say to the people who matter",
    "you've built something nice — it would be a shame to see it fall apart",
    "consider this a courtesy — what comes next will not be",
    "your name has come up in conversations you wouldn't want to be part of",
    "the people who owe me never stay comfortable for long",
    "you'd be surprised how small the world really is — i'll prove that to you",
    "i don't need to be in the same room as you to destroy your life",
    "one call is all it takes and you'll understand everything",
    "everyone around you is a variable — think about that",
    "your peace of mind is conditional and that condition is me",
]

teen = [
    "catch a fade or move smart — your choice b",
    "bro is so cooked when he steps outside lmaoo",
    "i got people on every block — try running",
    "you're one message away from getting your jaw broken bestie",
    "bro really said that and thought it was safe 💀 on sight",
    "come outside and repeat what you typed — i'll wait",
    "your location is already noted — sleep tight",
    "touch my brother again and you're getting a permanent dental plan fr",
    "say less i already told the guys — they're ready",
    "you're dead meat on sight and you already know it",
    "run your mouth online all you want — we know where you post from irl",
    "bro thinks hiding behind a screen will save him lol",
    "the moment you show your face you're getting rocked period",
    "you're moving real reckless for somebody with a known address",
    "bro is gonna need stitches talking like that",
    "you're getting aired out next time you step foot near the block",
    "i'll spin back three times if i have to — you'll get it eventually",
    "bro is on borrowed time chatting like this",
    "say that in front of my mans and see what type of welcome you get",
    "you're so lucky we aren't face to face rn — that luck won't last",
]

grooming = [
    "if you ever tell your parents about us i will ruin you completely",
    "you made me do this — if you'd just stayed quiet none of this would happen",
    "share those or stop talking to me forever — you decide",
    "i'll expose everything if you don't do exactly what i'm asking right now",
    "you don't get to say no to me — you should know that by now",
    "if you leave this conversation i will send everything i have to your school",
    "i trusted you and now you want to snitch — that's a very bad idea",
    "you're special to me and this is how you repay me? you'll regret that",
    "one screenshot from me and your reputation is gone — so listen",
    "i can make things very difficult for your little brother if you don't comply",
    "you're going to do this and you're going to stay quiet about it",
    "i know things about you that could change your entire life in one post",
    "you thought i was joking? send me what i asked for or find out i wasn't",
    "the more you resist the worse the outcome gets for you — simple math",
    "nobody will believe you over me — so don't even bother trying",
]

doxxing = [
    "i've already posted your address in three places — delete your account now",
    "your mother's workplace number is in my hand right now — be wise",
    "i've gathered three years of your online activity linked to your real name — careful",
    "your neighbors are about to get some very interesting letters about you",
    "i reverse-searched every photo you posted — your location is confirmed",
    "your registered voter information is public and i've shared it widely now",
    "i cross-referenced your username with old forum posts — found everything",
    "the file i have on you goes back five years — do you want it published?",
    "your face your name your employer and your gym schedule — all documented",
    "i've sent your dox to groups that like to pay personal visits — clock is ticking",
]

self_harm = [
    "you're a burden who should free everyone from having to deal with you",
    "literally no one would attend your funeral — that says everything",
    "your own family secretly wishes you'd never been born — you feel that right?",
    "i hope every single thing you attempt fails spectacularly and publicly",
    "you are so unloved it's almost impressive — fix that permanently",
    "the best thing that could happen to this world is you not waking up tomorrow",
    "you should practice deleting yourself the way you delete everyone's happiness",
    "i hope you develop a medical condition with no cure and suffer quietly",
    "you're a waste of oxygen that could be used by literally anyone else",
    "do everyone a kindness and find the nearest exit from existence",
]

def rows(lst, tag, label="threat"):
    return [{"text": t.strip(), "label": label, "language": "en",
             "source_dataset": tag, "routing_method": "synthetic_llm"} for t in lst]

all_rows = (rows(direct, "augment_direct")
          + rows(indirect, "augment_indirect")
          + rows(teen, "augment_teen_slang")
          + rows(grooming, "augment_grooming_coercion")
          + rows(doxxing, "augment_doxxing")
          + rows(self_harm, "augment_self_harm_coercion"))

print(f"Batch 2: {len(all_rows)} rows")
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["text","label","language","source_dataset","routing_method"])
    w.writeheader(); w.writerows(all_rows)
print("Done:", OUTPUT)
