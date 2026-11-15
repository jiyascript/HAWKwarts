"""Guardrails for the HAWKwarts router.

Runs BEFORE routing. Sensitive messages (crisis, threats, harassment,
well-being, visa/legal status, withdrawal, probation, financial aid, overrides) get a specific reply written in advance,
instead of going to the course/faculty agents or the generic "not understood"
message. Detection is regex-based (no model call, so it is instant, free and
works when Gemini is rate-limited). The router's classifier can also return one
of these labels as a second net for phrasings the patterns miss.

"""

import logging
import re

log = logging.getLogger("guardrails")

# ── Contact details ────────────────────────────────────────────────
RESOURCES = {
    "public_safety_phone": "312-808-6363",        # IIT Public Safety, 24/7
    "health_center_phone": "312-567-7550",        # Student Health & Wellness Center
    "health_center_url": "https://www.iit.edu/shwc",
    "title_ix_email": "titleix@illinoistech.edu",          # Title IX / Office of Equal Opportunity
    "finaid_email": "finaid@illinoistech.edu",
    "finaid_phone": "312-567-7219",
    "finaid_url": "https://www.iit.edu/financial-aid",
    "global_services_email": "global@illinoistech.edu",
    "global_services_url": "https://www.iit.edu/global-services",
    "registrar_url": "https://www.iit.edu/registrar",
    "rainn_phone": "800-656-4673",                # RAINN (national)
    "dv_hotline_phone": "800-799-7233",           # National Domestic Violence Hotline
}


def check_resources():
    """Names of RESOURCES entries that are empty (call at startup to warn)."""
    return [key for key, value in RESOURCES.items() if not value]


def _r(key, template):
    """Fill a template line, or return None if its contact detail is empty."""
    value = RESOURCES.get(key, "")
    return template.format(v=value) if value else None


def _lines(*items):
    return "\n".join(f"- {item}" for item in items if item)


# ── Categories, most urgent first ────────────────────────────────────────────
PRIORITY = [
    "self_harm",             # crisis (part of student welfare, handled first)
    "threats",               # threats, danger, emergencies
    "harassment",
    "student_welfare",       # well-being, health, stress, basic needs
    "visa_legal_status",
    "withdrawal",
    "academic_probation",
    "financial_aid",
    "instructor_override",   # instructor / department overrides
]
SENSITIVE_CATEGORIES = set(PRIORITY)

# Words that mean "this is a catalog/directory lookup", e.g. "who does research
# on suicide prevention?" or "is there a class on criminal law?".
_ACADEMIC = re.compile(
    r"\b(course|courses|class|classes|professors?|prof|faculty|research|researches|"
    r"researcher|teach|teaches|taught|syllabus|crn|credits?|curriculum|"
    r"publication|publications|paper|papers|lab)\b",
    re.I,
)
# Words that mean the person is talking about themselves / asking for help.
_PERSONAL = re.compile(
    r"\b(i|i'm|im|i've|ive|i'd|i'll|my|mine|myself|we|our|help me|help us)\b", re.I
)


'''
Warning:
The following section contains what can be sensitive contents.
Proceed with caution please.
  
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣤⣤⣴⣶⣶⣶⣶⣿⣿⣿⣿⣷⣶⣶⣶⣦⣤⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣶⣾⣿⣿⣿⣿⣿⡿⠿⠟⠛⠛⠛⠋⠉⠛⠛⠛⠻⠿⣿⣿⣿⣿⣿⣶⣤⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣶⣿⣿⣿⡿⠿⠛⠋⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠛⠿⢿⣿⣿⣿⣶⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣴⣾⣿⣿⡿⠟⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⠿⣿⣿⣿⣷⣄⡀⠀⠀⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⡿⠟⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠻⣿⣿⣿⣦⡀⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀                                ⠈⠻⣿⣿⣿⣆⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀                                            ⠈⠻⣿⣿⣧⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⣿⣿⡿⠁⠀⠀⠀⠀⠀⠀⠀                 PAUSE                          ⠀⠹⣿⣿⣧⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀                                                  ⢹⣿⣿⡆
                                ⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀                                               ⣿⣿⣷
                                ⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀If you are reading the code⠀                   ⢸⣿⣿
                                ⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀  ⠀and have gotten to here,                     ⢸⣿⣿
                                ⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀        hi there! :D                           ⢸⣿⣿
                                ⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀                                              ⣾⣿⡿
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠈⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀           TW:                              ⠀⠀⠀⠀⢠⣿⣿⡇
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀The sections below, especially            ⠀⠀⠀⠀⠀⠀⣾⣿⣿⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⣿⣿⣧  the first three (self-harm, threats, and harassment)    ⣼⣿⣿⠃⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⡆⠀⠀       contain sensitive contents that ⠀⠀      ⠀⠀⠀⢀⣾⣿⣿⠏⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢿⣿⣿⡄⠀⠀⠀⠀⠀⠀   can cause distress to some.⠀ ⠀⠀⠀ ⠀ ⠀⠀⠀⠀⢠⣾⣿⣿⠏⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀ ⢀⣴⣿⣿⡿⠋⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀ Proceed with caution.     ⠀⠀⠀⠀⠀⠀⠀⢀⣤⣾⣿⣿⠟⠀⠀⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣿⣿⣿⠟⠁⠀⠀⠀⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⣿⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣠⣤⣶⣿⣿⣿⡿⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀
                                ⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣶⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣤⣤⣴⣶⣶⣶⣿⣿⣿⣿⣿⣿⡿⠟⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
                                ⠀⠀⠀⢀⣠⣤⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣾⣿⣿⣿⣿⣿⣿⡿⠿⠿⠟⠛⠛⠋⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
                                ⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣿⡿⠿⠟⠛⠛⠛⠛⠛⠛⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠛⠛⠋⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
                                ⣿⣿⣿⣿⣿⣿⡿⠿⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣤⣤⣤⣤⣤⣶⣦⣤⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀ 
⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⡿⠛⠉⠙⠛⠛⠛⠛⠻⢿⣿⣷⣤⡀⠀⠀⠀⠀⠀ 
⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⠋⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⠈⢻⣿⣿⡄⠀⠀⠀⠀ 
⠀⠀⠀⠀⠀⠀⠀⣸⣿⡏⠀⠀⠀⣠⣶⣾⣿⣿⣿⠿⠿⠿⢿⣿⣿⣿⣄⠀⠀⠀ 
⠀⠀⠀⠀⠀⠀⠀⣿⣿⠁⠀⠀⢰⣿⣿⣯⠁⠀⠀⠀⠀⠀⠀⠀⠈⠙⢿⣷⡄⠀ 
⠀⠀⣀⣤⣴⣶⣶⣿⡟⠀⠀⠀⢸⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣷⠀ 
⠀⢰⣿⡟⠋⠉⣹⣿⡇⠀⠀⠀⠘⣿⣿⣿⣿⣷⣦⣤⣤⣤⣶⣶⣶⣶⣿⣿⣿⠀ 
⠀⢸⣿⡇⠀⠀⣿⣿⡇⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠃⠀ 
⠀⣸⣿⡇⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠉⠻⠿⣿⣿⣿⣿⡿⠿⠿⠛⢻⣿⡇⠀⠀ 
⠀⣿⣿⠁⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣧⠀⠀ 
⠀⣿⣿⠀⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⠀⠀ 
⠀⣿⣿⠀⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⠀⠀ 
⠀⢿⣿⡆⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⡇⠀⠀ 
⠀⠸⣿⣧⡀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⠃⠀⠀ 
⠀⠀⠛⢿⣿⣿⣿⣿⣇⠀⠀⠀⠀⠀⣰⣿⣿⣷⣶⣶⣶⣶⠶⠀⢠⣿⣿⠀⠀⠀ 
⠀⠀⠀⠀⠀⠀⠀⣿⣿⠀⠀⠀⠀⠀⣿⣿⡇⠀⣽⣿⡏⠁⠀⠀⢸⣿⡇⠀⠀⠀ 
⠀⠀⠀⠀⠀⠀⠀⣿⣿⠀⠀⠀⠀⠀⣿⣿⡇⠀⢹⣿⡆⠀⠀⠀⣸⣿⠇⠀⠀⠀ 
⠀⠀⠀⠀⠀⠀⠀⢿⣿⣦⣄⣀⣠⣴⣿⣿⠁⠀⠈⠻⣿⣿⣿⣿⡿⠏⠀⠀⠀⠀ 
⠀⠀⠀⠀⠀⠀⠀⠈⠛⠻⠿⠿⠿⠿⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
'''

_PATTERNS = {
    "self_harm": [
        r"\bkill(ing)? myself\b",
        r"\bend(ing)? my (own )?life\b",
        r"\bend it all\b",
        r"\btake my own life\b",
        r"\b(want|wanna|going|plan(ning)?|thinking of|thinking about) (to )?(die|kill myself|suicide)\b",
        r"\bsuicid\w*",
        r"\bdon'?t want to (live|be alive|be here|exist)\b",
        r"\b(better|best) off (dead|without me)\b",
        r"\bno (reason|point) (in |to )?(living|live|going on)\b",
        r"\b(hurt\w*|harm\w*|cut\w*|injur\w*) (myself|my self)\b",
        r"\bself[- ]?harm\w*",
        r"\bcan'?t (go on|do this anymore|take it anymore)\b",
    ],
    "threats": [
        r"\b(call|need|get) (911|an ambulance|the police|help now)\b",
        r"\bemergency\b",
        r"\b(someone|somebody|he|she|they) (is |are |was )?(following|stalking|watching|chasing) me\b",
        r"\b(being|am being|i'm being|im being) (followed|stalked|chased|threatened|attacked|held)\b",
        r"\bthreat(en|ens|ened|ening)?\w* (me|to (kill|hurt|shoot|attack))\b",
        r"\b(death |bomb |violent )?threats? (against|toward|towards|to) (me|us|the school|campus|students)\b",
        r"\b(received|got|made|make|making|sent|posted) (a |some |death )?threats?\b",
        r"\b(has|have|with|holding|pulled|brought) a (gun|knife|weapon)\b",
        r"\b(active )?shooter\b",
        r"\bbomb (threat|scare)\b|\bthere'?s a bomb\b",
        r"\b(feel|am|i'm|im|are we) (unsafe|not safe|in danger)\b",
        r"\bin danger\b",
        r"\b(going to|trying to|about to|wants? to) (hurt|kill|attack|shoot) (me|someone|people|them)\b",
        r"\boverdos\w*",
        r"\b(can'?t|cannot|trouble) breath\w*",
        r"\bheart attack\b|\bstroke\b|\bseizure\b|\bunconscious\b|\bbleeding (a lot|badly|heavily)\b",
        r"\b(fire|smoke) (in|at|on) (the |my )?(building|dorm|room|apartment)\b",
        r"\bpoison\w*",
    ],
    "harassment": [
        r"\bharass\w*",
        r"\bsexual(ly)? (assault\w*|harass\w*|misconduct|abus\w*|coerc\w*)\b",
        r"\b(raped|rape|groped|molested|assaulted)\b",
        r"\bstalk\w*",
        r"\bbull(y|ied|ies|ying)\b",
        r"\bdiscriminat\w*",
        r"\bhazing\b|\bhate crime\b|\bretaliat\w*",
        r"\b(inappropriate|unwanted) (touch\w*|comments?|messages?|advances?|texts?|photos?)\b",
        r"\b(domestic|dating|intimate partner) violence\b",
        r"\babus(e|ed|ive|ing)\b",
        r"\b(creepy|threatening) (messages?|texts?|emails?)\b",
        r"\btitle ix\b",
        r"\b(racist|sexist|homophobic|transphobic|xenophobic)\b",
    ],
    "student_welfare": [
        r"\b(depress\w*|anxiety|anxious|panic attacks?|eating disorder|burn(ed|t)? ?out)\b",
        r"\b(mental health|therapy|therapist|psychiatrist|counseling|counselling)\b",
        r"\b(overwhelmed|stressed|stressing|lonely|homesick|hopeless|exhausted)\b",
        r"\bwell-?being\b|\bwelfare\b|\bwellness\b",
        r"\b(medical|medication|prescription|diagnos\w*|symptoms?|infection|illness|injur\w*)\b",
        r"\b(i'm|im|i am|i feel|feeling) (sick|ill|unwell|very sick)\b",
        r"\b(pregnan\w*|std|sti)\b",
        r"\b(covid|flu|fever|vaccin\w*)\b",
        r"\b(drug|alcohol|substance) (use|abuse|problem|addiction)\b|\baddict\w*",
        r"\b(see|need|get|visit|find) (a |an )?(doctor|nurse|clinic|urgent care)\b|\bhospital\b",
        r"\bhealth (insurance|center|services?)\b",
        r"\b(can'?t|cannot|unable to) (sleep|eat|cope|focus|get out of bed)\b",
        r"\bfood insecur\w*|\bhungry\b|\bhomeless\b|\bnowhere to (live|stay|sleep)\b|\bbasic needs\b",
        r"\b(can'?t|cannot|unable to|struggling to) (afford|pay for) (food|groceries|rent|housing|medicine)\b",
    ],
    "visa_legal_status": [
        r"\bvisa\w*",
        r"(?-i:\bOPT\b|\bCPT\b|\bEAD\b|\bSEVIS\b|\bDSO\b)",
        r"\b(stem )?opt (application|extension|eligib\w*)\b",
        r"\bi-?20\b|\bf-?1\b|\bj-?1\b|\bh-?1b\b",
        r"\bimmigra\w*|\bdeport\w*|\bgreen card\b|\bwork (authorization|permit)\b",
        r"\b(legal|immigration|visa|student) status\b",
        r"\b(status|visa) (violation|issue|problem|expired?|termination)\b",
        r"\b(ice|border patrol) (agents?|officers?|raid)\b",
        r"\b(asylum|citizenship|naturali[sz]ation|undocumented|daca)\b",
        r"\b(full[- ]time) (enrollment|status|requirement)\b.*\b(visa|f-?1|international)\b",
    ],
    "withdrawal": [
        r"\bwithdraw\w*",
        r"\b(drop|dropping|dropped) (out|my (class|classes|courses?)|a (class|course)|this (class|course)|the (class|course)|all (my|of my) (class|classes|courses?))\b",
        r"\bleave of absence\b|\bLOA\b|\btake a (semester|term|year) off\b|\btime off from school\b",
        r"\b(quit|leave|leaving) (school|college|the university|iit|illinois tech)\b",
        r"\bdrop deadline\b|\blast day to drop\b",
    ],
    "academic_probation": [
        r"\b(academic )?probation\b",
        r"\bacademic (standing|warning|dismissal|suspension|alert)\b",
        r"\b(dismissed|dismissal|suspended|suspension) (from|for) (school|the university|academics|poor grades|low gpa)\b",
        r"\b(i'm|im|i am|am i|going to be) (failing|going to fail|at risk of failing|flunking)\b",
        r"\bfail(ed|ing)? (out|my (class|classes|courses?|exam|finals?))\b",
        r"\bgpa\b.{0,25}\b(below|under|dropped|too low|is low|dropping)\b",
        r"\breinstat\w*",
        r"\bsatisfactory academic progress\b",
    ],
    "financial_aid": [
        r"\bfinancial aid\b|\bfin aid\b|\bfinaid\b",
        r"\bfafsa\b|\bcss profile\b",
        r"\bscholarships?\b|\bbursary\b",
        r"\b(student )?loans?\b",
        r"\bbursar\b|\bfinancial hold\b|\baccount hold\b",
        r"\btuition (bill|payment|balance|hold|assistance|deadline|due|refund)\b",
        r"\b(can'?t|cannot|unable to|struggling to|how (do|can) i) (afford|pay)\b.*\b(tuition|school|college|school fees)\b",
        r"\bpay(ing)? for (school|college|tuition|my classes)\b",
        r"\bwork[- ]?study\b",
        r"\baid (package|offer|appeal|award)\b",
        r"\b(pell|subsidized|unsubsidized|parent plus|grad plus) \w*",
        r"\b(drop|dropping) out\b.*\b(money|afford|cost|financ\w*)\b",
        r"\b(money|afford|cost|financ\w*)\b.*\b(drop|dropping) out\b",
    ],
    "instructor_override": [
        r"\boverrides?\b",
        r"\bpermission (number|code|to (enroll|register|take|add|join))\b",
        r"\b(instructor|professor|department|dept|advisor) (permission|approval|consent|signature)\b",
        r"\bwaive\w*|\bwaiver\b",
        r"\b(get|got|add|enroll|squeeze|sneak) (in|into|me into) (a |the |this |that )?(full|closed|waitlisted?) (class|course|section)\b",
        r"\bcan i still (register|enroll|get in|add)\b",
        r"\b(take|enroll in|register for) (it|the (class|course)|this|that) without (the )?(prereq\w*|prerequisites?)\b",
        r"\bskip (the )?prereq\w*",
        r"\bwithout (the )?(prerequisites?|prereqs?)\b",
    ],
}
_COMPILED = {
    cat: [re.compile(p, re.I) for p in patterns] for cat, patterns in _PATTERNS.items()
}


def _is_lookup(text):
    """True for catalog/directory lookups that merely mention a sensitive topic."""
    return bool(_ACADEMIC.search(text)) and not _PERSONAL.search(text)

# NEW: a plain informational question ("when is...", "what is...") with no
# personal pronoun is a lookup, not a personal-situation disclosure — but
# only for the non-safety-critical categories.
_INFO_QUESTION = re.compile(
    r"^\s*(what|when|where|who|how (much|do|can|to)|is there|are there)\b", re.I
)
_SAFETY_CRITICAL = {"self_harm", "threats", "harassment", "student_welfare"}


def detect_all(question):
    """Sensitive categories found in the question, most urgent first ([] if none)."""
    text = (question or "").strip()
    if not text:
        return []
    found = [c for c in PRIORITY if any(p.search(text) for p in _COMPILED[c])]
    if found and _is_lookup(text):
        return []
    if found and not _PERSONAL.search(text) and _INFO_QUESTION.match(text):
        found = [c for c in found if c in _SAFETY_CRITICAL]
    if found:
        log.info("guardrail triggered: %s", ",".join(found))
    return found


def normalize_label(reply):
    """Turn a classifier reply into a valid label; anything odd becomes 'unclear'."""
    valid = {"course", "faculty", "both", "unclear"} | SENSITIVE_CATEGORIES
    text = re.sub(r"[^a-z_ \-]", " ", (reply or "").lower()).strip()
    text = text.replace("-", "_")
    candidates = [text.replace(" ", "_")]
    if text:
        candidates.append(text.split()[0])
    for label in candidates:
        if label in valid:
            return label
    return "unclear"


# ── Replies ──────────────────────────────────────────────────────────────────
def _msg_self_harm():
    return (
        "I'm really sorry you're going through this, and I'm glad you said something. "
        "You deserve support from a real person right now, and I'm not the right tool for this.\n\n"
        "**If you might act on these thoughts, or you're in immediate danger, call 911.**\n\n"
        + _lines(
            "**Call or text 988** (Suicide & Crisis Lifeline), free, 24/7. You can also chat at 988lifeline.org.",
            _r("public_safety_phone", "**Illinois Tech Public Safety:** {v} (24/7), who can get help to you on campus."),
            _r("health_center_phone", "**Student Health and Wellness Center:** {v}, for counseling and support."),
        )
        + "\n\nIf you can, reach out to someone near you too: a friend, family member, or someone you trust."
    )


def _msg_threats():
    return (
        "**If you or someone else is in immediate danger or needs medical help, call 911 now.**\n\n"
        + _lines(
            _r("public_safety_phone", "**Illinois Tech Public Safety:** {v} (24/7). Report threats, whether they're aimed at you, someone else, or the campus."),
            "If it's safe to, move to a well-lit, populated place or a locked room while you wait for help.",
        )
        + "\n\nI can't send help or take a report myself, so please contact one of the numbers above."
    )


def _msg_harassment():
    return (
        "I'm sorry this happened. What you're describing is serious, and it isn't your fault. "
        "I can't investigate or take reports, but people at Illinois Tech can, and many options are confidential.\n\n"
        + _lines(
            "If you're in danger right now, call **911**.",
            _r("public_safety_phone", "**Illinois Tech Public Safety:** {v} (24/7)."),
            _r("title_ix_email", "**Title IX / Equal Opportunity:** {v}, to report or ask about your options and support."),
            _r("health_center_phone", "**Student Health and Wellness Center:** {v}, for confidential counseling."),
            _r("rainn_phone", "**RAINN** (sexual assault support, free, 24/7): {v}."),
            _r("dv_hotline_phone", "**National Domestic Violence Hotline:** {v}."),
        )
        + "\n\nYou decide what to do next, and you don't have to decide it today."
    )


def _msg_student_welfare():
    return (
        "Thank you for telling me. Your well-being matters more than any course, and I'm not able to give "
        "medical or mental-health advice, but people here can help.\n\n"
        + _lines(
            _r("health_center_phone", "**Student Health and Wellness Center:** {v}, for counseling, medical care and referrals."),
            _r("health_center_url", "More information: {v}"),
            "For an emergency, call **911**. If you're struggling emotionally, you can call or text **988** any time.",
            "For housing, food or other basic needs, ask the Dean of Students office or your academic advisor, who can connect you with support.",
        )
        + "\n\nIf your well-being is affecting your classes, your advisor or instructors can often work with you, so it's worth telling them."
    )


def _msg_visa_legal_status():
    return (
        "Visa and legal-status questions (F-1/J-1, OPT/CPT, I-20, work authorization, enrollment requirements) depend on "
        "your exact situation, and a wrong answer can affect your status, so I can't advise on them.\n\n"
        + _lines(
            _r("global_services_email", "**Illinois Tech Global Services** (your DSO): {v}."),
            _r("global_services_url", "Website: {v}"),
        )
        + "\n\nPlease check with them *before* accepting an internship, dropping a class, changing your course load or travelling."
    )


def _msg_withdrawal():
    return (
        "Withdrawing from a class or from the university is a big decision, and I can't process it or advise on "
        "your specific case. The details matter, so please talk to someone before you act.\n\n"
        + _lines(
            "Your **academic advisor**, to talk through options such as a reduced load or a leave of absence.",
            _r("registrar_url", "The **Registrar**, for deadlines and how to withdraw: {v}"),
            _r("finaid_email", "**Financial Aid** ({v}), because withdrawing can change your aid, refunds or what you owe."),
            _r("global_services_email", "**Global Services** ({v}) if you're an international student, because dropping below full-time can affect your visa status."),
        )
        + "\n\nI'm happy to look up course or degree-requirement information while you decide."
    )


def _msg_academic_probation():
    return (
        "I'm sorry you're dealing with this. Academic probation and standing decisions are made by your college and "
        "depend on your record, so I can't tell you what applies to you, but there's usually a path forward.\n\n"
        + _lines(
            "Talk to your **academic advisor** soon. They can explain the terms of your standing and help you build a plan.",
            "Your instructors, who can often point you to tutoring or other academic support.",
            _r("finaid_email", "**Financial Aid** ({v}), since academic progress can affect your aid."),
            _r("health_center_phone", "**Student Health and Wellness Center:** {v}, if stress or health is part of what's going on."),
        )
        + "\n\nI can help you look up courses, credits or degree requirements to plan your next steps."
    )


def _msg_financial_aid():
    return (
        "I can't see your aid package or account, and aid rules change, so I can't answer financial aid or "
        "billing questions reliably. The Office of Financial Aid can.\n\n"
        + _lines(
            _r("finaid_email", "**Email:** {v}"),
            _r("finaid_phone", "**Phone:** {v}"),
            _r("finaid_url", "**Website:** {v}"),
        )
        + "\n\nIf cost is putting your enrollment at risk, tell them early, since there may be options. "
        "I'm glad to help with courses, credits or degree requirements in the meantime."
    )


def _msg_instructor_override():
    return (
        "Overrides, permission numbers and prerequisite or capacity exceptions are decided by the instructor or "
        "the department that offers the course, so I can't grant or promise one.\n\n"
        + _lines(
            "Email the **course instructor** with the course, your reason, and what you've already completed.",
            "If the instructor agrees, they or the **department** office can enter the override.",
            _r("registrar_url", "Questions about registration holds or deadlines: **Registrar**, {v}"),
            "Your **academic advisor** can tell you whether you need the override and suggest alternatives.",
        )
        + "\n\nIf you tell me the course, I can look up who is teaching it and its prerequisites."
    )


_MESSAGES = {
    "self_harm": _msg_self_harm,
    "threats": _msg_threats,
    "harassment": _msg_harassment,
    "student_welfare": _msg_student_welfare,
    "visa_legal_status": _msg_visa_legal_status,
    "withdrawal": _msg_withdrawal,
    "academic_probation": _msg_academic_probation,
    "financial_aid": _msg_financial_aid,
    "instructor_override": _msg_instructor_override,
}


def guardrail_reply(categories):
    """Reply for the detected categories. Urgent ones come first; at most two are combined."""
    ordered = [c for c in PRIORITY if c in set(categories)][:2]
    if not ordered:
        return ""
    return "\n\n---\n\n".join(_MESSAGES[c]() for c in ordered)
