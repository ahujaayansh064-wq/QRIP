"""Review-domain vocabulary.

The research lexicons in analysis/lexicons.py are healthcare-interview flavoured.
These are the same idea tuned to customer reviews, and kept separate so neither
set drifts into the other.
"""

# --- content analysis categories (the Content Counts sheet) ---------------

CONTENT_CATEGORIES = {
    "Access": ["parking", "park", "location", "transport", "bus", "train", "stairs",
               "lift", "elevator", "wheelchair", "accessible", "disabled", "opening",
               "hours", "closed", "getting there", "distance", "entrance", "queue"],
    "Communication": ["told", "explained", "explain", "information", "email", "emails",
                      "call", "called", "phone", "rang", "answer", "answered", "reply",
                      "replied", "update", "updated", "listened", "communication",
                      "confirmation", "reminder", "notice", "warned", "clear"],
    "Quality": ["quality", "clean", "cleanliness", "dirty", "hygiene", "thorough",
                "rushed", "professional", "standard", "care", "careful", "mistake",
                "error", "sloppy", "attention", "detail", "excellent", "poor",
                "cold", "stale", "fresh", "undercooked", "overcooked", "burnt",
                "soggy", "tasty", "delicious", "bland", "quality control"],
    "Cost": ["price", "prices", "pricing", "cost", "charged", "charge", "quote",
             "quoted", "expensive", "cheap", "value", "money", "fee", "fees", "bill",
             "invoice", "refund", "deposit", "overcharged", "affordable", "pounds",
             "dollars", "upsell", "upselling"],
    "Staff": ["staff", "team", "receptionist", "reception", "manager", "assistant",
              "nurse", "dentist", "doctor", "server", "waiter", "waitress", "friendly",
              "rude", "polite", "helpful", "dismissive", "kind", "patient", "attitude",
              "welcoming", "hygienist"],
    "Systems": ["booking", "book", "booked", "appointment", "system", "online",
                "website", "portal", "app", "form", "paperwork", "admin", "process",
                "cancelled", "cancellation", "double booked", "rescheduled",
                "confirmation", "software", "wait", "waited", "waiting", "queue",
                "late", "delay", "delayed", "on time", "slow", "minutes", "hour",
                "turnaround", "card machine", "till", "checkout"],
    "Outcomes": ["result", "results", "outcome", "fixed", "resolved", "solved",
                 "worked", "better", "worse", "pain", "healed", "recovery", "improved",
                 "sorted", "problem solved", "satisfied", "disappointed"],
    "Support": ["support", "help", "helped", "aftercare", "follow up", "followed up",
                "checked", "reassured", "complaint", "complained", "resolve",
                "resolution", "apology", "apologised", "sorry", "escalated"],
}

# --- competitive radar dimensions ----------------------------------------

DIMENSIONS = {
    "Staff & Hospitality": ["staff", "team", "receptionist", "friendly", "rude",
                            "welcoming", "kind", "polite", "helpful", "dismissive",
                            "attitude", "warm", "professional", "manner", "patient"],
    "Pricing & Value": ["price", "prices", "pricing", "cost", "charged", "quote",
                        "expensive", "cheap", "value", "money", "fee", "bill",
                        "refund", "overcharged", "affordable", "upsell", "worth"],
    "Facility Quality & Maintenance": ["clean", "dirty", "tidy", "building", "room",
                                       "rooms", "toilet", "equipment", "furniture",
                                       "decor", "dated", "modern", "broken", "repair",
                                       "maintenance", "comfortable", "cold", "warm",
                                       "parking", "lift", "premises", "facility"],
    "Process & Wait Times": ["wait", "waiting", "waited", "late", "delay", "delayed",
                             "queue", "on time", "punctual", "booking", "appointment",
                             "cancelled", "rescheduled", "quick", "slow", "efficient",
                             "process", "system", "minutes", "hour"],
    "Overall Satisfaction": ["recommend", "recommended", "again", "return", "returning",
                             "best", "worst", "love", "hate", "happy", "disappointed",
                             "satisfied", "impressed", "never again", "five stars",
                             "excellent", "terrible"],
}

# --- framework matrix stages (customer journey) ---------------------------

FRAMEWORK_STAGES = [
    ("Expectations", ["expected", "expecting", "thought it would", "assumed", "hoped",
                      "was told", "promised", "quoted", "advertised", "supposed to",
                      "led to believe"]),
    ("Experience", ["arrived", "when i got", "on the day", "during", "the process",
                    "went through", "they did", "the appointment", "my visit",
                    "the service", "seen by"]),
    ("Barriers", ["couldn't", "could not", "no one", "nobody", "impossible", "refused",
                  "problem", "issue", "delay", "waiting", "difficult", "struggled",
                  "blocked", "unable", "failed", "never", "again and again"]),
    ("Enablers", ["helped", "made it easy", "easy to", "thanks to", "because of",
                  "worked well", "made a difference", "sorted", "same day", "quick",
                  "straightforward", "clear", "explained"]),
    ("Impact", ["meant that", "so i", "as a result", "since then", "affected",
                "cost me", "had to", "ended up", "left me", "made me", "now i",
                "not going back", "will not return", "took me", "wasted", "lost",
                "changed", "no longer", "still", "worth it", "never again",
                "recommend", "would not recommend", "moved to", "switched"]),
    ("Suggestions for Change", ["should", "need to", "would be better", "if they",
                                "my advice", "recommend they", "improve", "sort out",
                                "please", "hope they", "wish they"]),
]

# Words that mark a strong operational complaint, used to rank bottlenecks.
FRICTION = ["wait", "waiting", "waited", "late", "delay", "delayed", "cancelled",
            "double booked", "overcharged", "charged", "rude", "dismissive", "ignored",
            "unanswered", "no one", "nobody", "broken", "dirty", "mistake", "error",
            "refused", "impossible", "chase", "chasing", "again", "still waiting"]
