"""Lexicons used for interpretive tagging.

These drive emotion / intent / valence attribution, contradiction detection and
the methodology-specific readings (narrative arc cues, grounded-theory paradigm
slots, IPA experiential dimensions). Kept as plain data so a researcher can
audit and extend them.
"""

# --- affect --------------------------------------------------------------

EMOTIONS = {
    "frustration": """frustrat annoy irritat exasperat fed-up hassle tedious bureaucra
        runaround pointless nonsense stuck endless repeat chase chasing nightmare
        infuriat maddening tiresome""",
    "anxiety": """anxious anxiety worried worry nervous scared afraid fear panic dread
        stress stressed tense uneasy apprehensive terrif frighten overwhelm""",
    "sadness": """sad upset unhappy cried crying tears grief griev lonely alone
        isolated hopeless despair miserable low depress heartbreak""",
    "anger": """angry anger furious rage mad outrage livid resent bitter blame fault
        unfair unjust disgrace appalling""",
    "relief": """relief relieved reassur calm settled easier lifted weight-off better
        finally sorted resolved comfort soothe""",
    "hope": """hope hopeful optimis looking-forward positive improve progress promising
        encourag confident faith believe future""",
    "gratitude": """grateful gratitude thankful thanks appreciate blessing kindness
        generous supportive lovely wonderful brilliant""",
    "pride": """proud pride achievement accomplish managed succeed success capable
        strong resilient determined overcame""",
    "confusion": """confus unclear puzzl baffl lost muddl complicated jargon
        contradictory ambiguous mixed-messages did-not-understand misunderstand""",
    "trust": """trust trusted reliable dependable honest transparent listened heard
        respected believed taken-seriously safe""",
    "distrust": """distrust mistrust suspicious dismissed ignored fobbed patronis
        condescend not-listened dismissive brushed sceptic doubt lied""",
    "resignation": """resigned accept gave-up given-up nothing-i-can-do inevitable
        just-how-it-is put-up-with tolerate cope endure""",
}

EMOTION_VALENCE = {
    "frustration": -0.7, "anxiety": -0.7, "sadness": -0.8, "anger": -0.85,
    "relief": 0.7, "hope": 0.8, "gratitude": 0.85, "pride": 0.8,
    "confusion": -0.45, "trust": 0.75, "distrust": -0.75, "resignation": -0.4,
    "neutral": 0.0,
}

POSITIVE = set("""good great excellent helpful useful supportive kind clear easy quick
smooth fast efficient reliable friendly warm respectful safe better best improve
improved improving benefit benefits advantage strong success successful happy pleased
satisfied comfortable confident empowered valued included fair""".split())

NEGATIVE = set("""bad poor terrible awful useless unhelpful rude slow delay delayed
delays difficult hard hardest struggle struggled struggling problem problems issue
issues barrier barriers obstacle broken fail failed failure wrong worse worst pain
painful expensive costly confusing complicated impossible refused denied rejected
excluded ignored dismissed unsafe risk risky burden burdensome overwhelming""".split())

NEGATORS = {"not", "no", "never", "none", "nobody", "nothing", "cannot", "can't",
            "don't", "didn't", "doesn't", "won't", "wouldn't", "isn't", "aren't",
            "wasn't", "weren't", "hardly", "barely", "without", "lack", "lacked",
            "lacking", "failed", "refused", "denied"}

HEDGES = {"maybe", "perhaps", "possibly", "probably", "might", "may", "could",
          "seems", "seemed", "sort", "kind", "somewhat", "fairly", "guess",
          "suppose", "unsure", "not-sure", "i-think", "apparently", "arguably"}

# Verbs that make a poor start to a code label ("remember walking" -> "walking").
VERBS = set("""went gone going go goes came come coming rang ring rung called calling
said says saying told telling tell asked asking ask started starting start stopped
stopping kept keeping keep remember remembered remembering walking walked walk
thought thinking think knew knowing know felt feeling feel made making make got
getting get gave given give giving took taken taking take put putting wrote writing
write written waited waiting wait tried trying try decided deciding decide turned
turning turn looked looking look seen saw see seeing heard hearing hear did doing
done need needed needs want wanted wants let letting lets sent sending send""".split())

# Words too generic or purely calendrical to name a code after.
LOW_CONTENT = set("""january february march april may june july august september october
november december monday tuesday wednesday thursday friday saturday sunday week weeks
day days month months year years time times morning afternoon evening night people
person thing things stuff way ways bit part number end start point place case
four five six seven eight nine ten eleven twelve fifteen twenty thirty forty fifty
hundred thousand first second third man woman men women guy lady chap
now then here there today tomorrow yesterday anything everything something anyone
everyone someone sure fine okay course course lot""".split())

INTENSIFIERS = {"very", "extremely", "incredibly", "really", "so", "totally",
                "absolutely", "completely", "utterly", "hugely", "massively",
                "deeply", "profoundly", "terribly", "awfully", "particularly"}

# --- discourse intent ----------------------------------------------------

INTENTS = {
    "recounting": ["then", "after that", "the next day", "when i", "we went", "i went",
                   "i had", "at first", "eventually", "in the end", "one day"],
    "evaluating": ["was good", "was bad", "the best", "the worst", "i think it",
                   "in my opinion", "it works", "it doesn't work", "helpful",
                   "useless", "worth", "value"],
    "comparing": ["whereas", "compared", "than", "unlike", "similar to", "the same as",
                  "different from", "on the other hand", "before that", "used to"],
    "justifying": ["because", "since", "that's why", "the reason", "so that",
                   "in order to", "otherwise", "which is why"],
    "recommending": ["should", "need to", "ought", "they must", "it would help",
                     "i'd like", "would be better", "my advice", "recommend"],
    "contrasting": ["but", "however", "although", "though", "even though", "yet",
                    "on the contrary", "instead"],
    "hypothesising": ["if", "would have", "might have", "could have", "suppose",
                      "imagine", "what if", "unless"],
    "describing": ["there is", "there are", "it is", "they are", "usually", "normally",
                   "typically", "generally"],
}

# --- narrative analysis (Labov & Waletzky) -------------------------------

NARRATIVE_CUES = {
    "orientation": ["at the time", "back then", "i was", "we lived", "i had been",
                    "originally", "in those days", "before all this", "i worked",
                    "when i was"],
    "complication": ["then suddenly", "but then", "that's when", "it went wrong",
                     "everything changed", "the problem started", "one day",
                     "out of nowhere", "collapsed", "broke down"],
    "evaluation": ["i felt", "it was terrifying", "i realised", "looking back",
                   "the worst part", "what struck me", "i couldn't believe",
                   "it made me", "i remember thinking"],
    "resolution": ["in the end", "eventually", "finally", "we managed", "it settled",
                   "sorted out", "we got through", "since then", "now i"],
    "coda": ["these days", "nowadays", "now", "today", "so that's", "that's how",
             "which is where i am", "ever since"],
}

TEMPORAL_MARKERS = ["before", "after", "then", "now", "later", "earlier", "since",
                    "until", "while", "when", "first", "next", "finally",
                    "eventually", "yesterday", "today", "years ago", "months ago",
                    "at the start", "in the end", "these days"]

AGENCY_ACTIVE = ["i decided", "i chose", "i made", "i pushed", "i insisted",
                 "i asked", "i took", "i refused", "i fought", "i organised",
                 "i arranged", "we decided", "i started"]
AGENCY_PASSIVE = ["i was told", "they made me", "i had to", "we were sent",
                  "i was given", "it was decided", "they put me", "i was left",
                  "nothing i could", "out of my hands", "i was placed"]

# --- grounded theory paradigm model --------------------------------------

GT_PARADIGM = {
    "causal_conditions": ["because", "due to", "caused by", "as a result of",
                          "the reason", "started when", "led to", "triggered",
                          "brought on", "stems from"],
    "phenomenon": ["what happens", "the situation", "it is", "this is", "the issue",
                   "the experience", "what it's like", "the reality"],
    "context": ["at the hospital", "at work", "at home", "in the clinic", "during",
                "in that setting", "where i live", "in my area", "the system",
                "the department", "the service"],
    "intervening_conditions": ["although", "unless", "except", "if only", "depending on",
                               "when there is", "without", "provided that", "as long as"],
    "strategies": ["i tried", "we had to", "i started", "what i do", "i learned to",
                   "the way i cope", "i make sure", "i keep", "i avoid", "i chase",
                   "i push", "workaround"],
    "consequences": ["so now", "as a result", "which meant", "that led", "ended up",
                     "the effect", "consequently", "in turn", "meant that",
                     "the outcome"],
}

# --- IPA experiential dimensions -----------------------------------------

IPA_DIMENSIONS = {
    "embodied": ["body", "pain", "ache", "tired", "exhausted", "sleep", "breath",
                 "heart", "stomach", "physically", "energy", "weight", "shaking",
                 "numb", "sick"],
    "temporal": ["waiting", "wait", "months", "years", "days", "delay", "since",
                 "future", "past", "before", "after", "forever", "endless",
                 "eventually", "time"],
    "relational": ["family", "friends", "partner", "husband", "wife", "children",
                   "colleagues", "team", "doctor", "nurse", "staff", "people",
                   "together", "alone", "support", "relationship"],
    "existential": ["identity", "who i am", "meaning", "purpose", "life", "death",
                    "future", "faith", "myself", "person", "changed me", "sense of",
                    "worth", "dignity"],
    "spatial": ["room", "home", "ward", "office", "building", "corridor", "distance",
                "travel", "far", "journey", "place", "space"],
}

# --- content analysis a-priori categories --------------------------------

CONTENT_CATEGORIES = {
    "access": ["access", "waiting", "appointment", "referral", "availability",
               "booking", "queue", "eligibility", "distance", "transport"],
    "communication": ["told", "explained", "information", "letter", "email", "call",
                      "listened", "language", "jargon", "update", "communication"],
    "quality": ["quality", "care", "standard", "thorough", "rushed", "mistake",
                "error", "safe", "competent", "attentive"],
    "cost": ["cost", "money", "pay", "paid", "expensive", "afford", "fee", "price",
             "insurance", "financial", "budget"],
    "staff": ["doctor", "nurse", "receptionist", "consultant", "staff", "team",
              "manager", "gp", "therapist", "clinician"],
    "systems": ["system", "process", "policy", "form", "paperwork", "portal",
                "software", "record", "admin", "department", "procedure"],
    "outcomes": ["better", "worse", "improved", "recovery", "result", "outcome",
                 "diagnosis", "treatment", "resolved", "progress"],
    "support": ["support", "help", "helped", "carer", "family", "group", "charity",
                "advocate", "peer", "network"],
}

# --- framework analysis a-priori dimensions ------------------------------

FRAMEWORK_DIMENSIONS = [
    ("Expectations", ["expected", "thought it would", "assumed", "hoped", "anticipated",
                      "was told it would", "imagined"]),
    ("Experience of the process", ["process", "steps", "procedure", "how it worked",
                                   "what happened", "went through", "stages"]),
    ("Barriers", ["barrier", "obstacle", "difficult", "blocked", "couldn't", "refused",
                  "problem", "delay", "struggle", "no one"]),
    ("Enablers", ["helped", "made it easier", "supported", "thanks to", "because of",
                  "worked well", "made a difference", "enabled"]),
    ("Relationships", ["relationship", "trust", "rapport", "listened", "respect",
                       "dismissed", "communication", "connection"]),
    ("Impact", ["impact", "affected", "changed", "consequence", "meant that", "result",
                "since then", "effect on"]),
    ("Suggestions for change", ["should", "would help", "need", "recommend", "better if",
                                "my advice", "improve", "if only they"]),
]


def _expand(spec: str):
    return [w for w in spec.split()]


EMOTION_STEMS = {name: _expand(spec) for name, spec in EMOTIONS.items()}
