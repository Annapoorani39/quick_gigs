import re
from copy import deepcopy


SKILL_TAXONOMY = {
    "housekeeping": {
        "aliases": [
            "housekeeping", "clean rooms", "cleaning rooms", "room cleaning", "cleaned rooms",
            "clean room", "sweeping", "mopping", "laundry", "sanitizing", "room service",
            "அறை சுத்தம்", "சுத்தம் செய்தேன்", "சுத்தம்", "அறைகள் சுத்தம்"
        ],
        "category": "Housekeeping",
    },
    "customer service": {
        "aliases": [
            "customer service", "helped customers", "served customers", "handled customers",
            "front desk", "welcomed customers", "supporting customers", "booking help",
            "வாடிக்கையாளர் சேவை", "கிளையண்ட் சேவை", "வாடிக்கையாளர்களுக்கு உதவ", "மக்கள் உதவி"
        ],
        "category": "Customer Service",
    },
    "basic billing": {
        "aliases": [
            "billing", "cash handling", "cash billing", "handled billing", "transactions",
            "basic accounting", "bookkeeping", "invoice", "cash collection",
            "பில்லிங்", "கேஷ்", "பில்", "பில்லிங் உதவி"
        ],
        "category": "Basic Accounting",
    },
    "communication": {
        "aliases": [
            "communication", "speaking", "talking", "greeting customers", "explaining",
            "மொழி", "பேச்சு", "வாடிக்கையாளர்களுடன் பேச்சு", "தொடர்பு"
        ],
        "category": "Communication",
    },
    "hospitality": {
        "aliases": [
            "hotel", "hospitality", "guest support", "hotel staff", "front office",
            "ஹோட்டல்", "ஹோட்டலில்", "விருந்தினர் உதவி", "ஹோட்டல் பணியாளர்"
        ],
        "category": "Hospitality",
    },
    "tailoring": {
        "aliases": [
            "tailoring", "sewing", "stitching", "blouse stitching", "dress making", "embroidery",
            "தையல்", "குத்துதல்", "போல்டரிங்", "தையல் வேலை"
        ],
        "category": "Tailoring",
    },
    "electrical repair": {
        "aliases": [
            "electrical repair", "repair wiring", "switch repair", "fixing wires", "wiring",
            "மின் பழுது", "வயரிங்", "சுவிட்ச் பழுது"
        ],
        "category": "Technical Repair",
    },
    "delivery": {
        "aliases": [
            "delivery", "delivered food", "food delivery", "using maps", "navigation app",
            "டெலிவரி", "சாப்பாடு விநியோகம்", "நேவிகேஷன்"
        ],
        "category": "Driving and Delivery",
    },
    "caregiving": {
        "aliases": [
            "caregiving", "taking care of elderly", "elder care", "home care", "nursing support",
            "பராமரிப்பு", "மூத்தோர் பராமரிப்பு", "வீட்டு பராமரிப்பு"
        ],
        "category": "Caregiving",
    },
    "farming": {
        "aliases": [
            "farming", "field work", "irrigation", "harvesting", "crop work", "agriculture",
            "விவசாயம்", "மண்ணடித்தல்", "பயிர் வேலை"
        ],
        "category": "Agriculture",
    },
    "data entry": {
        "aliases": [
            "data entry", "typing", "excel", "spreadsheet", "entry work", "records maintenance",
            "டேட்டா என்ட்ரி", "எக்செல்", "ஸ்பிரெட்ஷீட்", "பதிவு"
        ],
        "category": "Digital Literacy",
    },
    "inventory management": {
        "aliases": [
            "inventory", "stock management", "stock checking", "store keeping", "inventory management",
            "இன்வென்டரி", "ஸ்டாக்", "கிடங்கு மேலாண்மை"
        ],
        "category": "Management",
    },
    "booking management": {
        "aliases": [
            "booking management", "managed bookings", "reservations", "booked rooms", "booking",
            "புக்கிங்", "ரிசர்வேஷன்", "தங்கும் இட புக்கிங்"
        ],
        "category": "Management",
    },
    "sales": {
        "aliases": [
            "sales", "retail sales", "shop sales", "customer buying", "merchandising",
            "விற்பனை", "கடைக்காரர்", "வாடிக்கையாளர் விற்பனை"
        ],
        "category": "Sales",
    },
    "construction": {
        "aliases": [
            "construction", "site work", "masonry", "plumbing", "painting", "helper work",
            "கட்டுமானம்", "சேவை வேலை", "சுவர் வேலை"
        ],
        "category": "Construction",
    },
}

LEARNING_RESOURCES = {
    "housekeeping": [
        "https://www.coursera.org/courses?query=housekeeping",
        "https://www.youtube.com/results?search_query=hotel+housekeeping+training",
    ],
    "customer service": [
        "https://www.coursera.org/courses?query=customer+service",
        "https://www.youtube.com/results?search_query=customer+service+training",
    ],
    "communication": [
        "https://www.coursera.org/courses?query=communication+skills",
        "https://www.youtube.com/results?search_query=workplace+communication+skills",
    ],
    "basic billing": [
        "https://www.youtube.com/results?search_query=basic+billing+training",
        "https://www.coursera.org/courses?query=bookkeeping",
    ],
    "tailoring": [
        "https://www.youtube.com/results?search_query=basic+tailoring+for+beginners",
        "https://www.skillshare.com/search?query=tailoring",
    ],
    "caregiving": [
        "https://www.coursera.org/courses?query=caregiver+training",
        "https://www.youtube.com/results?search_query=elderly+care+training",
    ],
    "data entry": [
        "https://www.youtube.com/results?search_query=data+entry+training",
        "https://www.coursera.org/courses?query=data+entry",
    ],
    "sales": [
        "https://www.coursera.org/courses?query=sales+skills",
        "https://www.youtube.com/results?search_query=retail+sales+training",
    ],
    "delivery": [
        "https://www.youtube.com/results?search_query=delivery+route+training",
        "https://www.coursera.org/courses?query=logistics",
    ],
    "electrical repair": [
        "https://www.youtube.com/results?search_query=electric+repair+basic+training",
        "https://www.coursera.org/courses?query=electrician",
    ],
    "inventory management": [
        "https://www.youtube.com/results?search_query=inventory+management+basics",
        "https://www.coursera.org/courses?query=inventory+management",
    ],
}

JOB_DATA = [
    {
        "title": "Housekeeping Associate",
        "location": "Bengaluru",
        "language": "English",
        "required_skills": ["housekeeping", "customer service", "communication"],
        "preferred_skills": ["basic billing", "booking management"],
        "description": "Support hotel rooms, cleaning schedules, and guest support for a busy property.",
        "experience": "Entry-level hospitality experience preferred.",
    },
    {
        "title": "Retail Sales Associate",
        "location": "Chennai",
        "language": "English",
        "required_skills": ["sales", "customer service"],
        "preferred_skills": ["communication", "basic billing"],
        "description": "Help customers, arrange products, and maintain a friendly shop floor.",
        "experience": "Retail or service experience preferred.",
    },
    {
        "title": "Delivery Partner",
        "location": "Bengaluru",
        "language": "Tamil",
        "required_skills": ["delivery", "communication"],
        "preferred_skills": ["navigation", "customer service"],
        "description": "Deliver food, manage routes, and support customers on the road.",
        "experience": "A valid delivery setup and route familiarity are useful.",
    },
    {
        "title": "Tailor / Stitching Assistant",
        "location": "Coimbatore",
        "language": "Tamil",
        "required_skills": ["tailoring"],
        "preferred_skills": ["customer service", "sales"],
        "description": "Prepare garments, repair items, and support fit and finishing work.",
        "experience": "Hands-on stitching experience preferred.",
    },
    {
        "title": "Caregiver Support Worker",
        "location": "Madurai",
        "language": "Tamil",
        "required_skills": ["caregiving", "communication"],
        "preferred_skills": ["housekeeping"],
        "description": "Support elderly and dependent clients with hygiene, comfort, and daily needs.",
        "experience": "Compassionate home care or caregiving experience is preferred.",
    },
    {
        "title": "Junior Data Entry Clerk",
        "location": "Hyderabad",
        "language": "English",
        "required_skills": ["data entry", "communication"],
        "preferred_skills": ["basic billing"],
        "description": "Manage records, data updates, and basic clerical support in a small office.",
        "experience": "Basic computer and spreadsheet familiarity is useful.",
    },
]


def normalize_skill(value):
    if value is None:
        return ""
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_text(value):
    if value is None:
        return ""
    text = str(value).lower()
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9\s\u0b80-\u0bff]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def skill_candidates():
    ordered = []
    for canonical, metadata in SKILL_TAXONOMY.items():
        ordered.append((canonical, metadata["aliases"]))
    return ordered


def extract_skills(text):
    if not text or not str(text).strip():
        return []

    normalized = normalize_text(text)
    found = []
    seen = set()

    for canonical, aliases in skill_candidates():
        canonical_key = canonical.lower()
        alias_variants = [normalize_text(alias) for alias in aliases]
        for alias in alias_variants:
            if alias and alias in normalized:
                if canonical_key not in seen:
                    found.append(canonical)
                    seen.add(canonical_key)
                break

    if "hotel" in normalized or "ஹோட்டல்" in normalized or "ஹோட்டலில்" in normalized:
        if "hospitality" not in found:
            found.append("hospitality")
    if any(word in normalized for word in ["helped", "served", "greeted", "spoke", "talked", "உதவ", "பேச"]):
        if "communication" not in found:
            found.append("communication")
    if any(word in normalized for word in ["work", "experience", "worked", "அனுபவம்"]):
        if "hospitality" not in found:
            found.append("hospitality")

    return found[:6]


def calculate_match_score(required_skills, user_skills, preferences=None, job_location=None, job_language=None):
    if preferences is None:
        preferences = {}

    user_set = {normalize_skill(skill) for skill in user_skills if skill}
    required = [normalize_skill(skill) for skill in required_skills if skill]
    if not required:
        return 0

    matched_required = sum(1 for skill in required if skill in user_set)
    preferred = []
    if isinstance(preferences, dict):
        preferred = [normalize_skill(skill) for skill in preferences.get("preferred_skills", []) if skill]
    matched_preferred = sum(1 for skill in preferred if skill in user_set)

    required_weight = 2
    preferred_weight = 1
    total_weight = sum(required_weight for _ in required)
    if preferred:
        total_weight += sum(preferred_weight for skill in preferred if skill in user_set)
    if total_weight == 0:
        total_weight = 1

    weighted_score = (
        (matched_required * required_weight) + (matched_preferred * preferred_weight)
    ) / total_weight * 100

    if job_location and preferences.get("location"):
        if normalize_skill(job_location) == normalize_skill(preferences.get("location")):
            weighted_score += 10

    if job_language and preferences.get("language"):
        if normalize_skill(job_language) == normalize_skill(preferences.get("language")):
            weighted_score += 10

    weighted_score = min(100, max(0, weighted_score))
    return round(weighted_score)


def recommend_jobs(user_skills, location=None, preferred_language="English"):
    normalized_user_skills = {normalize_skill(skill) for skill in user_skills if skill}
    scored = []

    for job in JOB_DATA:
        job_required = [normalize_skill(skill) for skill in job["required_skills"]]
        job_preferred = [normalize_skill(skill) for skill in job.get("preferred_skills", [])]
        matched_required = [skill for skill in job_required if skill in normalized_user_skills]
        matched_preferred = [skill for skill in job_preferred if skill in normalized_user_skills]

        score = calculate_match_score(
            required_skills=job_required,
            user_skills=user_skills,
            preferences={"location": location, "language": preferred_language},
            job_location=job["location"],
            job_language=job["language"],
        )

        scored.append({
            "title": job["title"],
            "location": job["location"],
            "language": job["language"],
            "description": job["description"],
            "match_score": score,
            "matched_skills": matched_required,
            "missing_skills": [skill for skill in job_required if skill not in normalized_user_skills],
            "preferred_skills": matched_preferred,
            "experience": job["experience"],
        })

    scored.sort(key=lambda item: (-item["match_score"], item["title"]))
    return scored


def build_resume_from_experience(experience_text, profile=None):
    profile = profile or {}
    skills = extract_skills(experience_text)
    cleaned = (experience_text or "").strip()

    summary = ""
    cleaned_text = (experience_text or "").lower()
    if "hotel" in cleaned_text or "hospitality" in cleaned_text or "guest" in cleaned_text:
        summary = "Friendly hospitality worker with experience in guest support, cleanliness, and daily service responsibilities."
    elif "tailor" in cleaned_text or "stitching" in cleaned_text or "sewing" in cleaned_text:
        summary = "Skilled sewing and tailoring worker with hands-on experience in garment work and finishing tasks."
    elif "delivery" in cleaned_text or "food" in cleaned_text:
        summary = "Reliable worker experienced in delivery support, customer interaction, and route-based service tasks."
    elif skills:
        summary = f"Experienced worker with practical skills in {', '.join(skills[:3])}."
    else:
        summary = "Dependable worker ready to contribute with practical experience and a strong service mindset."

    return {
        "full_name": profile.get("full_name") or "",
        "phone": profile.get("phone") or "",
        "location": profile.get("location") or "",
        "professional_summary": summary,
        "skills": skills,
        "experience": [
            {
                "role": "Practical Experience",
                "details": cleaned[:220] if cleaned else "User experience summary pending confirmation.",
            }
        ],
        "languages": ["English"] if "english" in (profile.get("language") or "").lower() else ["Tamil", "English"],
    }


def build_skill_gap_analysis(user_skills, target_job, preferences=None):
    if preferences is None:
        preferences = {}
    if not target_job:
        return {
            "title": "No target job",
            "match_score": 0,
            "matched_skills": [],
            "missing_skills": [],
            "improvement_skills": [],
            "priority_missing": [],
            "explanation": "Add skills or choose a job to generate a gap analysis.",
            "resources": [],
        }

    required_skills = [normalize_skill(s) for s in target_job.get("required_skills", []) if s]
    preferred_skills = [normalize_skill(s) for s in target_job.get("preferred_skills", []) if s]
    user_skill_set = {normalize_skill(skill) for skill in user_skills if skill}
    matched = [skill for skill in required_skills if skill in user_skill_set]
    missing = [skill for skill in required_skills if skill not in user_skill_set]
    partial = [skill for skill in preferred_skills if skill in user_skill_set]

    score = calculate_match_score(
        required_skills,
        user_skills,
        preferences={**preferences, "preferred_skills": preferred_skills},
        job_location=target_job.get("location"),
        job_language=target_job.get("language"),
    )

    priority_missing = missing[:3]
    resources = []
    for skill in priority_missing:
        resources.append({
            "skill": skill,
            "links": LEARNING_RESOURCES.get(skill, ["https://www.youtube.com/results?search_query=" + skill]),
        })

    explanation = (
        f"You match {len(matched)} of {len(required_skills)} core requirements for {target_job.get('title', 'this role')}. "
        f"The strongest next improvements are {', '.join(priority_missing[:2]) if priority_missing else 'your overall experience and confidence'} "
        f"so the profile becomes better aligned for this job."
    )

    return {
        "title": target_job.get("title", "Target role"),
        "match_score": score,
        "matched_skills": matched,
        "missing_skills": missing,
        "improvement_skills": partial,
        "priority_missing": priority_missing,
        "explanation": explanation,
        "resources": resources,
    }


def simulate_skill_growth(user_skills, selected_skill, location=None, preferred_language="English"):
    skill_set = set(normalize_skill(skill) for skill in user_skills if skill)
    skill_set.add(normalize_skill(selected_skill))
    base = recommend_jobs(list(skill_set), location=location, preferred_language=preferred_language)
    before = recommend_jobs(list(user_skills), location=location, preferred_language=preferred_language)
    before_best = before[0]["match_score"] if before else 0
    after_best = base[0]["match_score"] if base else 0
    return {
        "before": before_best,
        "after": after_best,
        "selected_skill": selected_skill,
        "jobs_now_eligible": [job["title"] for job in base if job["match_score"] >= 70],
        "improvement": max(0, after_best - before_best),
    }
