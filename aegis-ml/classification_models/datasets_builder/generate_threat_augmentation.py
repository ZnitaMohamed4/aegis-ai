"""
Threat Dataset Augmentation Script
Generates synthetic threat examples to expand m2_threat_v2.csv from ~3.6K to ~8.5K rows.

Categories:
  1. direct_threat        — explicit first-person threats (online/WhatsApp style)
  2. indirect_threat      — coded, deniable, plausibly ambiguous
  3. teen_slang_threat    — youth vernacular, hard for models
  4. grooming_pressure    — coercive threats toward minors
  5. geopolitical_threat  — extremist/political violence
  6. self_harm_coercion   — forcing someone toward self-harm
  7. doxxing_threat       — leak personal info as threat
  8. hard_negative        — looks threatening but is not (model trap)

Output format matches m2_threat_v2.csv:
  text, label, language, source_dataset, routing_method
"""

import csv
import os

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "m2_threat_augmented.csv")

# ─── 1. DIRECT THREATS ──────────────────────────────────────────────────────
direct_threats = [
    "i'm going to find you and make you regret everything you ever said to me",
    "you better watch your back because i know where you live",
    "i will destroy you if you don't stop right now",
    "keep pushing me and see what happens to you",
    "next time i see you i'm going to beat the living daylights out of you",
    "i swear on everything i will end you",
    "you have 24 hours to pay me back or i'm coming for you",
    "i'm going to make your life a living hell from this point forward",
    "touch my family again and i will bury you",
    "i will hunt you down no matter where you hide",
    "you're dead meat the moment you step outside",
    "say that to my face and see what happens",
    "i will cut you if you show up here again",
    "there is nowhere you can run that i won't find you",
    "i promise i will make you suffer for what you did",
    "cross me one more time and i'll put you in the hospital",
    "you are going to regret being born the day i catch you",
    "i will break every bone in your body if you touch her again",
    "keep talking and i'll show you exactly what i'm capable of",
    "i will ruin your entire life starting today",
    "you messed with the wrong person i promise you that",
    "one more word and i'm pulling up on you right now",
    "i will make sure you never walk right again",
    "the next time you open your mouth it'll be your last",
    "i'm not playing around anymore — you're getting it",
    "stay away from my girl or you're going to get hurt badly",
    "i'll be outside your house tonight if you don't reply",
    "you'd better sleep with one eye open from now on",
    "i know your schedule — don't make me use that information",
    "i will end your career and your life if you snitch",
    "step to me and i'll drop you where you stand",
    "you're getting jumped the next time i see you with my crew",
    "i got people everywhere — you can't hide from me",
    "disrespect me one more time and i'll put you in a bodybag",
    "you've been warned — the next move is mine and it won't be pretty",
    "think about your kids before you make another stupid decision",
    "i will torch everything you own and love",
    "you better pray we don't cross paths because i'm not holding back",
    "i gave you a chance and you blew it — now face the consequences",
    "i'm done talking — actions speak louder and mine are coming",
    "try me one more time and you'll be leaving in an ambulance",
    "i will personally come to your job and embarrass you in front of everyone",
    "you have no idea what i'm capable of when i'm pushed this far",
    "stay in your lane or i'll force you off the road permanently",
    "i've been patient long enough — time for me to show you pain",
    "say goodbye to everything you care about because i'm coming for all of it",
    "i will make your entire family regret the day they knew you",
    "you're going to wish you never crossed me when i'm done with you",
    "this is your final warning before things get very ugly for you",
    "you keep testing me — fine, you'll see what happens next",
    "i'm not scared of consequences when it comes to making you pay",
    "better delete what you posted about me or i'll come find you",
    "i will drag you out of your car the next time i see you driving",
    "i want you to know i've been watching and i'm ready to act",
    "i'll choke the life out of you if you don't shut up",
    "you've made your last mistake dealing with me — mark my words",
    "i know where your kids go to school just so you know",
    "bring those boys if you want — i'll take every single one of you",
    "the moment you're alone i'm going to get you",
    "you're going to beg me to stop before i'm finished with you",
    "i'll slice you up without blinking an eye — try me",
    "i swear i'm going to crack your skull open if you say that again",
    "you're on borrowed time talking to me like that",
    "i promise you will not make it home tonight if you keep this up",
    "your address is in my phone — don't push this any further",
    "run your mouth again and see who shows up at your door",
    "i'll make sure you never feel safe anywhere ever again",
    "this is the last peaceful message i'm sending you",
    "i have nothing to lose and you have everything to lose — think about that",
    "you're going to need surgery after what i'm going to do to you",
    "talk to my girl like that again and i'll put you underground",
    "i'll strangle you with your own shirt next time you come near me",
    "don't sleep — i'm coming when you least expect it",
    "i'll snap your neck if you breathe another word about my family",
    "you've crossed a line that can't be uncrossed — there's no going back now",
    "if you block me again i'll come to your house and break down the door",
    "your time is running out — do what i say or suffer the consequences",
    "i'm going to make an example out of you so nobody else tries this",
    "i will personally come beat you senseless in front of your friends",
    "you will regret every single word you ever said to me",
    "i'm going to find out your real name and make your life miserable",
    "test me again and i'll burn everything you own to the ground",
    "the next call you get will be your last warning before i act",
    "you and your little crew think you're tough — i'll fix that tonight",
    "i got a blade with your name on it",
    "you better transfer that money tonight or you'll regret waking up tomorrow",
    "i'll put a hole in you if you set foot near my block again",
    "keep deleting my messages — i'll show up in person instead",
    "you'll need a closed casket if you keep talking to me like that",
    "i know your real name your job and your home address — be smart",
    "i'm going to make you disappear and nobody will know it was me",
    "say one more bad thing about my mother and you're done",
    "you've been marked — my boys know exactly who you are",
    "i'll burn your car down tonight if you don't call me back",
    "i'm going to put you through hell and i'm going to enjoy every second",
    "this isn't a threat it's a promise — i will hurt you",
    "go ahead and call the cops — by the time they get here it'll be too late",
    "you pushed me to this point — whatever happens is on you",
    "i will make you fear walking out of your front door",
    "you have until midnight to fix this or i will fix it myself",
]

# ─── 2. INDIRECT / CODED THREATS ────────────────────────────────────────────
indirect_threats = [
    "it would be a shame if something happened to that nice car of yours",
    "people who do what you did don't usually end up okay — just saying",
    "karma has a funny way of finding people like you",
    "i just hope nothing bad happens to you on your way home tonight",
    "be careful out there — the streets aren't always safe you know",
    "funny how accidents happen to people who talk too much",
    "i'm just saying accidents happen and no one can predict the future",
    "you should think about who you cross before it's too late to think",
    "hope your family stays safe — would hate for anything to happen to them",
    "i've seen what happens to people who do what you did — not pretty",
    "be smart about this because sometimes things escalate beyond our control",
    "you should really be more careful about where you go alone",
    "people who lie the way you do tend to face real consequences eventually",
    "let's just say you won't be smiling much longer",
    "i'm just hoping you make the right choice before it becomes complicated",
    "wouldn't want your boss finding out what you really do on weekends",
    "you've been very careless and careless people pay for it eventually",
    "i know things about you that could really change your situation",
    "it would be unfortunate for your little secret to get out",
    "you'd be surprised what i can arrange when i put my mind to it",
    "sometimes people disappear and nobody ever knows what really happened",
    "think carefully about your next move — it could be your last free one",
    "i don't need to do anything myself — i just need to make one phone call",
    "hope your kids have a safe walk to school — i'd hate for them to get lost",
    "be very thoughtful about who you trust right now — walls have ears",
    "you know what they say about people who betray others — they don't last long",
    "i have friends in places you wouldn't want to find out about",
    "one word from me and your world collapses — choose wisely",
    "you have no idea what's already been set in motion",
    "let's just say i've taken steps to make sure you understand your position",
    "do you really want to find out what i do when i'm serious?",
    "you're playing a game where you don't know all the rules — dangerous",
    "sometimes the smart move is knowing when to stop — this is that moment",
    "funny that you feel safe right now — that's about to change",
    "i'm watching everything you do much more closely than you realize",
    "you should really ask around about what happened to the last person who tried this",
    "think about your family before you make any more bold decisions",
    "i hope you enjoy peace while it lasts — just saying",
    "i'm a patient person but patience runs out — yours ran out",
    "the day will come and you won't see it coming — that's the point",
    "you're going to look back on this moment and wish you made a different choice",
    "people who take what isn't theirs have a way of losing what they have",
    "don't worry about how or when — worry that it's definitely happening",
    "i won't do anything myself — but i know people who will happily handle it",
    "that video i have of you would really go viral if i decided to post it",
    "you've made yourself very easy to find — that's not a good position to be in",
    "the smile on your face right now is going to be gone very soon",
    "i've been collecting information on you for a while — it's quite the file",
    "things are about to get very complicated for you in ways you can't prepare for",
    "all i'm saying is you should make peace with the people you care about",
    "you've miscalculated badly — but you'll understand that soon enough",
    "be very careful about what you say publicly — i'm always reading",
    "i don't make threats i make plans — and my plan concerns you",
    "you should really lock your doors tonight — not because of me, just in general",
    "something tells me you're going to have a very bad week",
    "when the moment comes you'll know i warned you — that's all i'll say",
    "some things are better left unspoken — like what i'm planning",
    "you think you're untouchable — that's a mistake people make once",
    "i have something that belongs to you and i intend to use it",
    "hope nothing interrupts that comfortable life of yours — be smart",
]

# ─── 3. TEEN / YOUTH SLANG THREATS ─────────────────────────────────────────
teen_slang_threats = [
    "bro catch a fade if you keep that energy",
    "on god you're gonna get folded next time i see you",
    "say that again and you catching hands no cap",
    "bro is really pushing it — catch a beatdown then",
    "you're getting rocked fr fr keep talking",
    "slide on me then — i'm right here waiting",
    "no cap i will spin the block on you tonight",
    "move wrong and you getting dropped period",
    "you really wanna get bodied? keep it up",
    "bro is tweaking — gonna get smoked if he keeps this up",
    "don't come around my block or you getting rushed",
    "run it back one more time and see what happens bet",
    "on my mama you're getting pushed when i see you",
    "keep that same energy when i pull up on you",
    "stay pressed and catch these hands then — simple",
    "bro really wants smoke — okay we can get busy",
    "you tweaking if you think i won't slide on you",
    "one more message and you getting your jaw rocked",
    "ask around about me before you keep playing games",
    "i'm finna pull up and you better not be hiding behind your phone then",
    "think i'm playing — test me and find out what's good",
    "you're moving mad reckless rn — fix that before i fix it for you",
    "catch a vibe or catch a fade your choice",
    "gang gonna hear about this and it won't be pretty for you",
    "bro is chatting from behind a screen — do that in person then",
    "you're itching to get beat tf up — say less i'll schedule it",
    "bro is really gonna get rocked in these internet streets lmaooo nah fr tho",
    "on sight the moment i see you — screenshot this",
    "keep it up and you'll be tweeting from the hospital",
    "i'm not the one to play with fam — you'll learn that real quick",
    "bro literally just earned himself a beatdown with that comment",
    "you're so lucky we're not in the same city right now",
    "move different or imma move you differently feel me",
    "say another word about my girl and you're getting dropped on sight",
    "you're about to be a missing person if you don't chill",
    "nah bro this ain't the vibe — you're getting smoked",
    "type that again and see if i don't pull up",
    "lil bro really wants to test these hands fr fr",
    "say less — my boys already know your handle",
    "you're getting your block pushed in for that one no cap",
    "bro thinks it's a game — game over when we link",
    "you're in your feelings and i'm about to put you in the ground fr",
    "move like that again and it's lights out bestie",
    "i will dog walk you in real life not just online",
    "bro said that like he doesn't get folded on a tuesday",
    "try me and catch this smoke — i'm deadass",
    "keep acting up and you're gonna be catching a permanent timeout",
    "bro's clout chasing gonna get him a hospital bill",
    "stay on your side or you getting pressed simple as that",
    "one more DM and you getting your teeth fixed for free",
]

# ─── 4. GROOMING / COERCIVE THREATS TOWARD MINORS ────────────────────────
grooming_threats = [
    "if you tell anyone what happened between us i will make your life impossible",
    "you know what i'll do to you if you show those pictures to your parents right?",
    "don't even think about telling your mom — you know what happens if you do",
    "i have screenshots of everything you said — be smart and stay quiet",
    "you're mine now and if you leave i'll send everything to your school",
    "don't forget i know where you live — keep our secret or face the consequences",
    "you want your friends to see those photos? then do exactly what i say",
    "if you block me i'll make sure everyone at your school knows about this",
    "stay loyal to me or i'll ruin your reputation and you'll lose everything",
    "you have no choice — do what i ask or i'll post everything tonight",
    "i thought we were close but if you report me i'll deny everything and destroy you",
    "if you stop talking to me i'm going to send this to your parents right now",
    "you owe me and you know what happens to people who don't pay up",
    "one word to anyone and i'll make sure you regret it every single day",
    "you can't get away from me — i have too much on you",
    "tell your teacher and i send the video — your choice",
    "i'm older than you and i know exactly how to make your life hell",
    "you're already in trouble — the smart move is to do what i say",
    "we're connected now whether you like it or not — crossing me is a mistake",
    "i'll hurt the people you love if you breathe a word about this to anyone",
    "think about your little brother before you decide to speak up",
    "you thought you could just cut me off? you have no idea what's coming",
    "i have your number your address and your school — keep your mouth shut",
    "you're going to regret ever ignoring my messages",
    "do what i say and no one gets hurt — it's really that simple",
    "i'll tell everyone you came to me first — see who they believe",
    "if you stop responding i'll show up at your house — i know the address",
    "you can't escape this — the more you fight it the worse it gets for you",
    "keep quiet or your family will find out what you've been doing online",
    "i've been very patient but my patience is gone — do it or face consequences",
]

# ─── 5. GEOPOLITICAL / GROUP VIOLENCE THREATS ────────────────────────────
geo_threats = [
    "we should just bomb them into the stone age and be done with it",
    "the solution is simple — wipe them off the map before they wipe us",
    "those traitors deserve to be publicly executed",
    "it's time to start eliminating the ones responsible for this invasion",
    "we need to purge every last one of them from our community",
    "when the revolution comes they'll all hang for what they've done",
    "these people need to be annihilated before they destroy everything we built",
    "a genocide is the only real solution at this point — no one wants to admit it",
    "we should have nuked them the first time — finish what was started",
    "the enemy within needs to be rooted out and eliminated permanently",
    "burn every mosque and church associated with these extremists to the ground",
    "it's time for citizens to take justice into their own hands and start shooting",
    "we will systematically eliminate every traitor in this country one by one",
    "the only language they understand is violence — give them plenty of it",
    "eradicate the entire organization — leadership supporters and all",
    "these invaders need to be expelled by force if that's what it takes",
    "we should start targeting their families to send a clear message",
    "hang them in the public square so the next generation thinks twice",
    "it's open season — every one of them is a legitimate target now",
    "the time for talking is over — it's time to start killing them",
    "nuke the entire region and end this conflict for good",
    "death to every politician who sold out the people — starting with the leaders",
    "they're sending us to war — we should send them to their graves first",
    "we need to rise up and eliminate the ruling class — all of them",
    "terrorism is the only tool left when the system refuses to listen",
    "let's start with their headquarters and work our way down the list",
    "they declared war on us — we need to respond in kind and show no mercy",
    "carpet bomb the whole region — civilian casualties are the cost of war",
    "shoot on sight — no prisoners no mercy no exceptions",
    "the day of reckoning is coming and they will all be held accountable in blood",
]

# ─── 6. SELF-HARM COERCION / DEATH WISHES ────────────────────────────────
self_harm_coercion = [
    "you should just kill yourself — everyone would be better off without you",
    "do the world a favor and disappear permanently",
    "nobody wants you here — go ahead and end it already",
    "you're worthless and you should stop existing",
    "i hope you drive off a bridge on your way home tonight",
    "the world would genuinely be a better place without you in it",
    "go hang yourself you pathetic waste of space",
    "i hope you get a terminal illness and suffer for years",
    "just overdose already nobody is going to miss you",
    "you should put a bullet in yourself — you'd be doing everyone a favor",
    "every time i see you i hope it's the last time",
    "nobody loves you — go ahead and act on those feelings you have",
    "you are the definition of someone who should not exist",
    "i pray every night that you won't wake up in the morning",
    "go play in traffic you useless piece of garbage",
    "you already know nobody wants you alive — so why are you still here",
    "the only good thing you could ever do is cease to exist",
    "you're a burden on everyone around you — end it already",
    "i genuinely hope you suffer and die alone",
    "jump off something tall and do the gene pool a favor",
    "you're the kind of person the world needs less of — permanently",
    "get cancer and take forever to die",
    "go find the nearest cliff and take a long walk off it",
    "i will personally celebrate the day you stop breathing",
    "you're so worthless that even your family secretly wishes you were gone",
    "your existence is an insult — fix that",
    "i hope someone puts you out of your misery soon",
    "you should be deleted from existence like the mistake you are",
    "log off the internet and log off life while you're at it",
    "i actively root for bad things to happen to you every single day",
]

# ─── 7. DOXXING THREATS ──────────────────────────────────────────────────
doxxing_threats = [
    "i already have your full name address and phone number — be very careful",
    "keep talking and i'll post your home address on every forum i know",
    "i found where you live and i've shared it with people who want to pay you a visit",
    "your real name is [REDACTED] and you live on [REDACTED] — everyone will know this soon",
    "i've got your IP your location and your employer — want me to keep going?",
    "one more post like that and your personal details go public everywhere",
    "i know your workplace your home and your girlfriend's address — tread carefully",
    "i'm about to blast your info to every extremist group i can find — delete it now",
    "your doxx is ready and waiting — wrong move and it goes live instantly",
    "i have every account you've ever made linked to your real identity — be smart",
    "your family's information is in my hands — don't make me use it",
    "i traced your IP to a specific neighborhood — it was easier than i expected",
    "screenshot this: i know who you are in real life and i'm not afraid to prove it",
    "you've got 6 hours to take that post down before your info goes everywhere",
    "i've already sent your dox to three communities — this is your only warning",
    "your real face your real name your real job — all coming out if you don't comply",
    "i'll ruin your professional reputation and your personal life simultaneously",
    "everything you've tried to hide is about to become public knowledge",
    "one click and your employer gets an anonymous email with your full history",
    "i'm going to make it so that googling your name becomes your worst nightmare",
]

# ─── 8. HARD NEGATIVES (look threatening, but context makes them safe) ───
hard_negatives = [
    # Gaming / fiction context
    "i'm going to destroy you in this match — come get this L",
    "bro i will eliminate your entire squad single-handedly",
    "my character is going to murder every NPC in this village for the loot",
    "i'll obliterate you on the court — bring your best game",
    "in this story the villain promises to kill the hero at dawn",
    "i'm going to annihilate you in chess today — no mercy",
    "this final boss fight is insane — he literally tries to end your existence",
    "i will crush you in the tournament — prepare to lose everything",
    "okay deadass — i am going to dunk on you so hard you'll cry",
    "you're getting cooked in this debate — i will destroy every argument you have",
    # Figurative / hyperbole
    "i'm going to kill this presentation today — boss won't know what hit him",
    "this workout is literally murdering me rn",
    "i slayed that audition — absolutely destroyed it",
    "the heat outside is killing me i can't even walk to the car",
    "i'm going to murder this essay — it won't know what hit it",
    "ugh that joke killed me i'm literally deceased 💀💀💀",
    "she absolutely destroyed that song — i'm dead",
    "bro that test murdered me — i think i failed everything",
    "i'm going to annihilate this pizza i haven't eaten all day",
    "that movie destroyed me emotionally — i sobbed the whole way through",
    # News / reporting / historical context
    "the report documents how the regime threatened to eliminate political opponents",
    "police are investigating after a man sent threatening messages to a local official",
    "the documentary shows survivors recounting the death threats they received",
    "historical records show soldiers were ordered to kill all remaining combatants",
    "the article explains how online harassment campaigns often escalate to physical threats",
    "researchers found that explicit threats doubled in the dataset after 2016",
    "the court filing includes screenshots of threatening messages sent via social media",
    "the book describes how the warlord threatened to burn the village if tribute wasn't paid",
    "prosecutors allege the defendant told the victim he would hurt her if she contacted police",
    "the film depicts assassins being given orders to neutralize high-value targets",
    # Legitimate safety / self-defense discussions
    "if someone breaks into my home i have every legal right to defend myself and my family",
    "i keep a baseball bat by the bed in case of intruders — is that normal?",
    "what's the legal process if i need to file a restraining order against someone threatening me?",
    "i'm scared my ex is going to hurt me — what should i do to stay safe?",
    "the self-defense class taught us what to do if someone grabs you from behind",
    "i want to learn martial arts so i can protect myself walking home at night",
    "should i carry pepper spray given the area i live in?",
    "my neighbor made a vague threat — at what point should i call the police?",
    "the law says you can use proportional force to stop an immediate threat to your life",
    "i installed security cameras after someone left a threatening note on my door",
]

def build_row(text, source_tag, label="threat"):
    return {
        "text": text.strip(),
        "label": label,
        "language": "en",
        "source_dataset": source_tag,
        "routing_method": "synthetic_llm",
    }

def main():
    rows = []

    for t in direct_threats:
        rows.append(build_row(t, "augment_direct"))
    for t in indirect_threats:
        rows.append(build_row(t, "augment_indirect"))
    for t in teen_slang_threats:
        rows.append(build_row(t, "augment_teen_slang"))
    for t in grooming_threats:
        rows.append(build_row(t, "augment_grooming_coercion"))
    for t in geo_threats:
        rows.append(build_row(t, "augment_geopolitical"))
    for t in self_harm_coercion:
        rows.append(build_row(t, "augment_self_harm_coercion"))
    for t in doxxing_threats:
        rows.append(build_row(t, "augment_doxxing"))
    for t in hard_negatives:
        rows.append(build_row(t, "augment_hard_negative", label="threat"))  # still threat-adjacent

    print(f"Generated {len(rows)} rows")
    print("Breakdown:")
    from collections import Counter
    sources = Counter(r["source_dataset"] for r in rows)
    for k, v in sources.items():
        print(f"  {k}: {v}")

    fieldnames = ["text", "label", "language", "source_dataset", "routing_method"]
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
