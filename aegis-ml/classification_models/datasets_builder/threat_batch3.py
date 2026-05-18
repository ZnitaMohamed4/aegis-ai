"""Batch 3 — hard negatives + more edge cases"""
import csv, os

OUTPUT = os.path.join(os.path.dirname(__file__), "threat_batch3.csv")

# More varied hard negatives (genuine non-threats that look threatening)
hard_negatives = [
    # Academic / research framing
    "this study examines threatening language used in online extremist communities",
    "the researchers annotated 10,000 tweets as either threatening or non-threatening",
    "analyzing how death threats escalate in targeted harassment campaigns online",
    "content warning: the following examples contain violent and threatening language",
    "the model must learn to distinguish a genuine threat from figurative speech",
    "in the study corpus 34 percent of flagged messages were false positives",
    "historical genocides were often preceded by dehumanizing and threatening rhetoric",
    "hate speech scholars define a credible threat as one with specific victim and means",
    "the moderator training module shows examples of escalating threatening behavior",
    "researchers found that indirect threats are harder to detect algorithmically",
    # Clearly fictional / scripted
    "the villain growled: 'i will have my revenge on every last one of you'",
    "in chapter 12 the antagonist threatens to destroy the city unless his demands are met",
    "the script reads: 'if you don't hand over the money nobody leaves alive'",
    "the game's final boss says 'i will devour your soul and leave nothing behind'",
    "my fanfic has the hero threaten to expose the corrupt senator — is that realistic?",
    "the character sends an anonymous death threat to build suspense in act two",
    "writing a thriller where the stalker leaves increasingly terrifying notes — help with dialogue?",
    "the movie quote goes: 'cross me again and they'll never find the body'",
    "in the novel the mob boss says he will bury the witness if she testifies",
    "for my screenplay — how does a realistic ransom note usually sound?",
    # Reporting / news framing
    "police arrested a man after he allegedly sent death threats to the city councilwoman",
    "the suspect is accused of threatening to bomb the subway system next tuesday",
    "the email read 'you will regret this' according to the affidavit filed friday",
    "online harassment experts say threatening messages often begin subtly",
    "the platform removed 80,000 accounts for sending explicit threats last quarter",
    "the victim showed investigators screenshots of threats sent over three months",
    "lawmakers received threatening letters following the controversial vote",
    "the death threat was signed 'a concerned citizen' and mailed to the courthouse",
    "extremist forums were filled with threats targeting journalists and activists",
    "the non-profit tracks online threats against election workers in all 50 states",
    # Parenting / safety education
    "my child received a threatening message from a classmate — what do i do?",
    "how do i explain online threats to my 10-year-old without scaring them?",
    "the school counselor identified a student making veiled threats to peers online",
    "parents should know the signs that their child is being threatened online",
    "if your teen receives a threat online document it and report it to school authorities",
    "what counts as a credible threat when children send messages over gaming platforms?",
    "the workshop trained teachers to identify threatening language in student writing",
    "online safety lesson plan: recognizing the difference between joking and real threats",
    "my daughter's ex sent her threatening messages — here is how we handled it legally",
    "cyber safety experts say kids often don't report threats because they fear losing devices",
    # Clearly hyperbolic / humor
    "i'm going to absolutely annihilate you at mario kart tonight no mercy",
    "bestie if you don't send me that recipe RIGHT NOW i will perish",
    "i will haunt you from beyond the grave if you spoil this show for me",
    "ate the last slice of pizza — my roommate said she's going to end me lmao",
    "coach said he'll run us into the ground if we lose this game",
    "my mom threatened to take my phone away forever and i'm not okay",
    "i will fight you over this pizza topping discourse — square up 🍕",
    "if this coffee isn't ready in 2 minutes i'm going to lose my entire mind",
    "she said she'd kill me if i told anyone about the surprise party 😭",
    "i swear i'll delete my account if this app changes the layout one more time",
]

# More direct threats (second sub-batch)
direct2 = [
    "i am done being nice — next time i won't hold back",
    "you want to see what i'm really capable of? keep going",
    "my patience just ran out and you're standing in the way",
    "enjoy your peace now because it ends the moment i get there",
    "i will not stop until you understand what you did to me",
    "i've lost everything because of you and i have nothing left to lose",
    "every person you love is a target now — you made that choice",
    "you can't run from me — i have connections in every city",
    "i will personally deliver you to the consequences you earned",
    "stop responding or i'll make you stop permanently",
    "you've met your match and your match is angry",
    "this is the version of me you've never met — and don't want to",
    "i don't forgive and i don't forget — you'll experience both of those facts",
    "i will tear your world apart piece by piece until you understand pain",
    "you'd better never let me see your face again",
    "i will end your entire career and social life with what i know",
    "i've been holding back — that stops today",
    "you'll be looking over your shoulder for years because of this",
    "i will take everything from you the way you took everything from me",
    "i'm not threatening you — i'm telling you exactly what is going to happen",
    "don't make me show you the version of me that scares people",
    "you have no idea how far i'm willing to go",
    "i will expose everything and destroy you publicly",
    "i'll put my knee on your throat until you understand respect",
    "you are not safe from me — remember that",
]

def rows(lst, tag, label="threat"):
    return [{"text": t.strip(), "label": label, "language": "en",
             "source_dataset": tag, "routing_method": "synthetic_llm"} for t in lst]

all_rows = (rows(hard_negatives, "augment_hard_negative")
          + rows(direct2, "augment_direct"))

print(f"Batch 3: {len(all_rows)} rows")
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["text","label","language","source_dataset","routing_method"])
    w.writeheader(); w.writerows(all_rows)
print("Done:", OUTPUT)
