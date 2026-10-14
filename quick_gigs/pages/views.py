import json
import math
import re
import zipfile
from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from functools import wraps
from io import BytesIO
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required as django_login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Avg, Q
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (
    UserProfile,
    VerificationDocument,
    Gig,
    SkillLearningProgress,
    Application,
    Rating,
)
from .skillmatch import (
    LEARNING_RESOURCES,
    extract_skills,
    normalize_skill,
)


def verified_login_required(view_func):
    @django_login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile and profile.verification_status != "approved":
            return redirect("verification_status")
        return view_func(request, *args, **kwargs)

    return wrapped


# -------------------------
# Home
# -------------------------
def home(request):
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile and profile.verification_status != "approved":
            return redirect("verification_status")

    context = {}

    if request.user.is_authenticated and hasattr(request.user, "profile"):
        user_type = (request.user.profile.account_type or "").lower()

        if user_type in ["employer", "both"]:
            accepted_apps = (
                Application.objects.filter(gig__employer=request.user, status="accepted")
                .select_related("gig", "applicant", "applicant__profile")
                .order_by("-applied_at")
            )
            context["active_sessions"] = accepted_apps

            completed_apps = (
                Application.objects.filter(gig__employer=request.user, status="completed")
                .select_related("gig", "applicant", "applicant__profile")
                .order_by("-applied_at")[:10]
            )
            context["completed_jobs"] = completed_apps

            hired_workers = (
                Application.objects.filter(gig__employer=request.user, status="completed")
                .values("applicant")
                .distinct()
            )

            hired_workers_list = []
            for row in hired_workers:
                worker = User.objects.get(id=row["applicant"])

                completed_count = Application.objects.filter(
                    gig__employer=request.user,
                    applicant=worker,
                    status="completed",
                ).count()

                ratings_qs = Rating.objects.filter(
                    rating_type="employer_to_worker",
                    rater=request.user,
                    rated_user=worker,
                )

                hired_workers_list.append({
                    "worker": worker,
                    "completed_count": completed_count,
                    "avg_rating": ratings_qs.aggregate(avg=Avg("stars"))["avg"],
                    "rating_count": ratings_qs.count(),
                })

            context["hired_workers"] = hired_workers_list

        elif user_type == "worker":
            accepted_gigs = (
                Application.objects.filter(applicant=request.user, status="accepted")
                .select_related("gig", "gig__employer")
                .order_by("-applied_at")
            )
            context["active_sessions"] = accepted_gigs

            completed_apps = (
                Application.objects.filter(applicant=request.user, status="completed")
                .select_related("gig", "gig__employer")
                .order_by("-applied_at")[:10]
            )
            context["completed_jobs"] = completed_apps

    return render(request, "index.html", context)



# -------------------------
# Auth
# -------------------------
def signup(request):
    if request.method == "POST":
        try:
            with transaction.atomic():
                full_name = (request.POST.get("full_name") or "").strip()
                email = (request.POST.get("email") or "").strip()
                username = (request.POST.get("username") or "").strip()
                phone = (request.POST.get("phone") or "").strip()
                password = request.POST.get("password") or ""
                confirm_password = request.POST.get("confirm_password") or ""
                account_type = (request.POST.get("account_type") or "").strip().lower()
                skills = (request.POST.get("skills") or "").strip()

                if not email or not username or not password:
                    messages.error(request, "Email, username and password are required.")
                    return render(request, "signup.html")

                if password != confirm_password:
                    messages.error(request, "Passwords do not match.")
                    return render(request, "signup.html")

                if User.objects.filter(email__iexact=email).exists():
                    messages.error(request, "Email already registered!")
                    return render(request, "signup.html")

                if User.objects.filter(username__iexact=username).exists():
                    messages.error(request, "Username already taken!")
                    return render(request, "signup.html")

                if account_type not in ("worker", "employer", "both"):
                    messages.error(request, "Please select a valid account type.")
                    return render(request, "signup.html")

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=full_name.split()[0] if full_name else "",
                    is_active=False,
                )

                profile = UserProfile.objects.create(
                    user=user,
                    full_name=full_name,
                    phone_number=phone,
                    account_type=account_type,
                    skills=skills,
                    verification_status="pending",
                )

                if "aadhaar_front" in request.FILES:
                    VerificationDocument.objects.create(
                        user_profile=profile,
                        document_type="aadhaar_front",
                        file=request.FILES["aadhaar_front"],
                    )

                if "aadhaar_back" in request.FILES:
                    VerificationDocument.objects.create(
                        user_profile=profile,
                        document_type="aadhaar_back",
                        file=request.FILES["aadhaar_back"],
                    )

                if "skill_documents" in request.FILES:
                    for f in request.FILES.getlist("skill_documents"):
                        VerificationDocument.objects.create(
                            user_profile=profile,
                            document_type="skill_certificate",
                            file=f,
                        )

                if "profile_photo" in request.FILES:
                    profile.profile_photo = request.FILES["profile_photo"]
                    profile.save(update_fields=["profile_photo"])

                messages.success(
                    request,
                    "Application submitted successfully! You'll receive an email once verified."
                )
                return redirect("login")

        except Exception as e:
            messages.error(request, f"Registration failed: {e}")
            return render(request, "signup.html")

    return render(request, "signup.html")


def login_view(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""

        if not email or not password:
            messages.error(request, "Email and password are required.")
            return render(request, "login.html")

        users = User.objects.filter(email__iexact=email).order_by("-id")
        if not users.exists():
            messages.error(request, "Invalid email or password.")
            return render(request, "login.html")

        auth_user = None
        for candidate in users:
            auth_user = authenticate(
                request,
                username=candidate.username,
                password=password,
            )
            if auth_user:
                break

            if candidate.check_password(password):
                profile = UserProfile.objects.filter(user=candidate).first()
                if profile:
                    return render(
                        request,
                        "verification-status.html",
                        {
                            "profile": profile,
                            "account_inactive": not candidate.is_active,
                        },
                    )

        if auth_user is None:
            messages.error(request, "Invalid email or password.")
            return render(request, "login.html")

        profile = UserProfile.objects.filter(user=auth_user).first()
        if profile is None:
            messages.error(request, "Profile not found. Please contact support.")
            return render(request, "login.html")

        if profile.verification_status != "approved":
            return render(
                request,
                "verification-status.html",
                {"profile": profile, "account_inactive": not auth_user.is_active},
            )

        auth_login(request, auth_user)
        messages.success(request, f"Welcome back, {profile.full_name}!")
        return redirect("home")

    return render(request, "login.html")


def verification_status(request):
    if not request.user.is_authenticated:
        return redirect("login")

    profile = UserProfile.objects.filter(user=request.user).first()
    if profile is None or profile.verification_status == "approved":
        return redirect("home")

    return render(
        request,
        "verification-status.html",
        {"profile": profile, "account_inactive": not request.user.is_active},
    )


def logout_view(request):
    auth_logout(request)
    messages.success(request, "You have been logged out successfully")
    return redirect("home")


def skill_dashboard(request):
    profile = UserProfile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    user_skills = split_skills(profile.skills if profile else "")
    open_jobs = Gig.objects.filter(status__in=["open", "urgent"]).order_by("-created_at")
    if request.user.is_authenticated:
        open_jobs = open_jobs.exclude(employer=request.user)
    jobs = [match_gig_to_skills(gig, user_skills) for gig in open_jobs]
    jobs.sort(key=lambda item: (
        item["match_score"] is None,
        -(item["match_score"] or 0),
        -item["gig"].created_at.timestamp(),
    ))
    selected_job = None
    requested_job_id = request.GET.get("job_id")
    if requested_job_id and requested_job_id.isdigit():
        selected_job = next(
            (item for item in jobs if item["gig"].id == int(requested_job_id)),
            None,
        )
    completed_skill_keys = (
        list(SkillLearningProgress.objects.filter(
            user=request.user,
            completed=True,
        ).values_list("skill_key", flat=True))
        if request.user.is_authenticated else []
    )
    completed_keys = {normalize_skill(key) for key in completed_skill_keys}
    selected_missing = selected_job["missing_skills"] if selected_job else []
    return render(request, "skillmatch-dashboard.html", {
        "jobs": jobs,
        "user_skills": user_skills,
        "profile_ready": profile is not None and bool(user_skills),
        "selected_job": selected_job,
        "completed_skill_keys": completed_skill_keys,
        "selected_skill_progress": {
            "completed": sum(normalize_skill(skill) in completed_keys for skill in selected_missing),
            "total": len(selected_missing),
        },
        "learning_resources": LEARNING_RESOURCES,
    })


def get_saved_profile_skills(user):
    if not user.is_authenticated:
        return []
    profile = UserProfile.objects.filter(user=user).only("skills").first()
    return split_skills(profile.skills if profile else "")


def job_matches(request):
    profile = UserProfile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    default_skills = split_skills(profile.skills if profile else "")
    requested_skills = request.GET.get("skills")
    user_skills = split_skills(requested_skills) if requested_skills is not None else default_skills
    open_jobs = Gig.objects.filter(status__in=["open", "urgent"]).select_related("employer").order_by("-created_at")
    if request.user.is_authenticated:
        open_jobs = open_jobs.exclude(employer=request.user)
    jobs = [match_gig_to_skills(gig, user_skills) for gig in open_jobs]
    jobs.sort(key=lambda item: (
        item["match_score"] is None,
        -(item["match_score"] or 0),
        -item["gig"].created_at.timestamp(),
    ))
    match_scores = [item["match_score"] for item in jobs if item["match_score"] is not None]
    matched_skill_count = len({
        normalize_skill(skill)
        for item in jobs
        for skill in item["matched_skills"]
    })
    skills_to_learn_count = len({
        normalize_skill(skill)
        for item in jobs
        for skill in item["missing_skills"]
    })
    completed_skill_keys = (
        list(SkillLearningProgress.objects.filter(
            user=request.user,
            completed=True,
        ).values_list("skill_key", flat=True))
        if request.user.is_authenticated else []
    )
    return render(request, "job-matches.html", {
        "jobs": jobs,
        "user_skills": ", ".join(user_skills),
        "profile_ready": profile is not None,
        "has_saved_skills": bool(default_skills),
        "available_jobs_count": len(jobs),
        "best_match_score": max(match_scores, default=None),
        "matched_skill_count": matched_skill_count,
        "skills_to_learn_count": skills_to_learn_count,
        "completed_skill_keys": completed_skill_keys,
        "learning_resources": LEARNING_RESOURCES,
    })


def resume_builder(request):
    profile = UserProfile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    return render(request, "resume-builder.html", {
        "profile_name": profile.full_name if profile else "",
        "profile_phone": profile.phone_number if profile else "",
        "profile_email": request.user.email if request.user.is_authenticated else "",
        "profile_skills": profile.skills if profile else "",
    })


def voice_demo(request):
    return render(request, "voice-demo.html", {"demo_transcript": ""})


def split_skills(value):
    if isinstance(value, (list, tuple)):
        candidates = value
    else:
        candidates = re.split(r"[,;\n]+", str(value or ""))
    seen = set()
    skills = []
    for candidate in candidates:
        skill = str(candidate).strip()[:100]
        key = normalize_skill(skill)
        if key and key not in seen:
            skills.append(skill)
            seen.add(key)
        if len(skills) == 50:
            break
    return skills


def match_gig_to_skills(gig, candidate_skills):
    required_skills = split_skills(gig.skills)
    normalized_candidate = {normalize_skill(skill) for skill in candidate_skills}
    matched = [skill for skill in required_skills if normalize_skill(skill) in normalized_candidate]
    missing = [skill for skill in required_skills if normalize_skill(skill) not in normalized_candidate]
    score = round(len(matched) / len(required_skills) * 100) if required_skills else None
    return {
        "gig": gig,
        "required_skills": required_skills,
        "matched_skills": matched,
        "missing_skills": missing,
        "match_score": score,
        "explanation": (
            f"{len(matched)} of {len(required_skills)} listed required skills match."
            if required_skills else "No listed skill requirements; a match percentage cannot be calculated."
        ),
        "resources": [
            {"skill": skill, "links": LEARNING_RESOURCES.get(
                normalize_skill(skill),
                ["https://www.youtube.com/results?search_query=" + skill.replace(" ", "+")],
            )}
            for skill in missing
        ],
    }


def api_health(request):
    return JsonResponse({
        "status": "ok",
        "service": "SkillMatch AI",
        "mode": "deterministic-demo",
        "timestamp": "2026-10-10",
    })


def api_extract_skills(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    text = str(payload.get("text") or "")
    return JsonResponse({
        "skills": extract_skills(text),
        "source": "deterministic skill dictionary",
        "summary": "Recognized skills based on the user-provided experience.",
    })


@verified_login_required
@require_POST
def api_save_profile_skills(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Skills must be submitted as a JSON object."}, status=400)
    skills = split_skills(payload.get("skills") or [])
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.get_full_name() or request.user.username,
            "phone_number": "",
            "account_type": "worker",
        },
    )
    skills = split_skills([*split_skills(profile.skills), *skills])
    profile.skills = ", ".join(skills)
    profile.save(update_fields=["skills", "updated_at"])
    return JsonResponse({"skills": skills, "status": "saved"})


@verified_login_required
@require_POST
def api_save_learning_progress(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Progress must be submitted as a JSON object."}, status=400)

    skill_name = str(payload.get("skill") or "").strip()[:100]
    skill_key = normalize_skill(skill_name) or re.sub(r"\s+", " ", skill_name.casefold()).strip()
    completed = payload.get("completed")
    if not skill_key:
        return JsonResponse({"error": "A skill is required."}, status=400)
    if not isinstance(completed, bool):
        return JsonResponse({"error": "Completion must be true or false."}, status=400)

    progress, _ = SkillLearningProgress.objects.update_or_create(
        user=request.user,
        skill_key=skill_key,
        defaults={"skill_name": skill_name, "completed": completed},
    )
    return JsonResponse({
        "skill": progress.skill_name,
        "completed": progress.completed,
        "status": "saved",
    })


@require_POST
def api_extract_resume(request):
    resume_file = request.FILES.get("resume")
    if resume_file is None:
        return JsonResponse({"error": "Choose a PDF or DOCX resume to upload."}, status=400)
    if resume_file.size > 5 * 1024 * 1024:
        return JsonResponse({"error": "Resume files must be 5 MB or smaller."}, status=400)

    extension = resume_file.name.rsplit(".", 1)[-1].lower() if "." in resume_file.name else ""
    if extension not in {"pdf", "docx"}:
        return JsonResponse({"error": "Unsupported file type. Upload a PDF or DOCX file."}, status=400)

    try:
        from docx.opc.exceptions import PackageNotFoundError
        from pypdf.errors import PdfReadError
        if extension == "pdf":
            from pypdf import PdfReader
            reader = PdfReader(resume_file)
            if reader.is_encrypted:
                return JsonResponse({"error": "Password-protected PDFs are not supported. Upload an unlocked copy."}, status=400)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            from docx import Document
            document = Document(resume_file)
            text_parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
            for table in document.tables:
                text_parts.extend(
                    " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    for row in table.rows
                )
            text = "\n".join(part for part in text_parts if part)
    except (OSError, ValueError, PdfReadError, PackageNotFoundError, zipfile.BadZipFile):
        return JsonResponse(
            {"error": f"Could not read this {extension.upper()} file. Try exporting it again or enter your details manually."},
            status=400,
        )

    if not text.strip():
        return JsonResponse({
            "error": "No selectable text was found. Scanned resumes need OCR; you can enter your details manually."
        }, status=400)

    section_names = {
        "education": {"education", "academic background", "கல்வி"},
        "projects": {"projects", "project experience"},
        "experience": {"experience", "work experience", "employment history"},
        "certifications": {"certifications", "certificates", "licenses"},
        "languages": {"languages", "language"},
    }
    sections = {}
    active_section = None
    for line in text.splitlines():
        normalized_line = re.sub(r"[:\s]+$", "", line.strip().lower())
        matched_section = next(
            (key for key, labels in section_names.items() if normalized_line in labels),
            None,
        )
        if matched_section:
            active_section = matched_section
            sections.setdefault(active_section, [])
        elif active_section and line.strip():
            sections[active_section].append(line.strip())

    sections = {key: "\n".join(value) for key, value in sections.items() if value}
    return JsonResponse({
        "text": text[:30000],
        "skills": extract_skills(text),
        "sections": sections,
        "source": "text extracted from uploaded resume; review before use",
        "stored": False,
    })


def api_experience_analyze(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    text = str(payload.get("text") or "")
    skills = extract_skills(text)
    if request.user.is_authenticated:
        skills = split_skills([*get_saved_profile_skills(request.user), *skills])
    gigs = Gig.objects.filter(status__in=["open", "urgent"]).order_by("-created_at")
    if request.user.is_authenticated:
        gigs = gigs.exclude(employer=request.user)
    recommendations = [
        {
            "id": item["gig"].id,
            "title": item["gig"].title,
            "location": item["gig"].location,
            "match_score": item["match_score"],
            "matched_skills": item["matched_skills"],
            "missing_skills": item["missing_skills"],
            "explanation": item["explanation"],
        }
        for item in (match_gig_to_skills(gig, skills) for gig in gigs)
    ]
    return JsonResponse({
        "skills": skills,
        "recommendations": recommendations,
        "confidence": "deterministic skill dictionary",
    })


def api_generate_resume(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "The resume data must be a JSON object."}, status=400)

    text = str(payload.get("experience_text") or "").strip()
    limits = {
        "full_name": 200, "email": 254, "phone": 30, "location": 200,
        "target_job": 200, "objective": 2000, "education": 4000, "projects": 4000,
        "experience": 10000, "certifications": 4000, "languages": 500,
    }
    if any(len(str(payload.get(field) or "")) > limit for field, limit in limits.items()):
        return JsonResponse({"error": "One or more resume fields exceed the allowed length."}, status=400)
    if len(text) > 10000:
        return JsonResponse({"error": "Experience text must be 10,000 characters or fewer."}, status=400)
    supplied_skills = split_skills(payload.get("skills") or [])
    resume = {
        "full_name": str(payload.get("full_name") or "").strip(),
        "email": str(payload.get("email") or "").strip(),
        "phone": str(payload.get("phone") or "").strip(),
        "location": str(payload.get("location") or "").strip(),
        "professional_summary": str(payload.get("objective") or "").strip(),
        "education": str(payload.get("education") or "").strip(),
        "projects": str(payload.get("projects") or "").strip(),
        "experience": str(payload.get("experience") or text).strip(),
        "certifications": str(payload.get("certifications") or "").strip(),
        "languages": str(payload.get("languages") or "").strip(),
        "target_job": str(payload.get("target_job") or "").strip(),
        "skills": supplied_skills or extract_skills(text),
    }
    return JsonResponse({
        "resume": resume,
        "status": "generated",
        "source": "user-provided information only",
    })


@require_POST
def api_resume_pdf(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "The resume data must be a JSON object."}, status=400)
    limits = {
        "full_name": 200, "email": 254, "phone": 30, "location": 200,
        "target_job": 200, "objective": 2000, "education": 4000, "projects": 4000,
        "experience": 10000, "experience_text": 10000, "certifications": 4000, "languages": 500,
    }
    if any(len(str(payload.get(field) or "")) > limit for field, limit in limits.items()):
        return JsonResponse({"error": "One or more resume fields exceed the allowed length."}, status=400)
    fields = [
        ("Name", payload.get("full_name")),
        ("Email", payload.get("email")),
        ("Phone", payload.get("phone")),
        ("Location", payload.get("location")),
        ("Career objective", payload.get("objective")),
        ("Education", payload.get("education")),
        ("Skills", ", ".join(split_skills(payload.get("skills") or []))),
        ("Projects", payload.get("projects")),
        ("Experience", payload.get("experience") or payload.get("experience_text")),
        ("Certifications", payload.get("certifications")),
        ("Languages", payload.get("languages")),
        ("Target job", payload.get("target_job")),
    ]
    if any(
        ord(character) > 255
        for _, value in fields
        for character in str(value or "")
    ):
        return JsonResponse({
            "error": "This server PDF renderer cannot shape Tamil or other non-Latin scripts. Use your browser's Print / Save as PDF option from the resume preview."
        }, status=400)
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    page_width, page_height = letter
    y = page_height - 54
    name = str(payload.get("full_name") or "Resume").strip()
    pdf.setTitle(name[:120])
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, name.encode("latin-1", "replace").decode("latin-1")[:80])
    y -= 30
    for label, value in fields[1:]:
        content = str(value or "").strip()
        if not content:
            continue
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, label)
        y -= 16
        pdf.setFont("Helvetica", 10)
        for paragraph in content.splitlines():
            safe_paragraph = paragraph.encode("latin-1", "replace").decode("latin-1")
            words = safe_paragraph.split()
            line = ""
            for word in words:
                candidate = f"{line} {word}".strip()
                if pdf.stringWidth(candidate, "Helvetica", 10) > page_width - 100 and line:
                    pdf.drawString(50, y, line)
                    y -= 14
                    line = word
                else:
                    line = candidate
                if y < 50:
                    pdf.showPage()
                    y = page_height - 54
                    pdf.setFont("Helvetica", 10)
            if line:
                pdf.drawString(50, y, line)
                y -= 14
        y -= 7
        if y < 50:
            pdf.showPage()
            y = page_height - 54
    pdf.save()
    response = HttpResponse(output.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="skillmatch-resume.pdf"'
    response["Cache-Control"] = "no-store"
    return response


def api_job_recommendations(request):
    requested_skills = request.GET.get("skills")
    skills = (
        split_skills(requested_skills)
        if requested_skills is not None
        else get_saved_profile_skills(request.user)
    )
    jobs = Gig.objects.filter(status__in=["open", "urgent"]).select_related("employer")
    if request.user.is_authenticated:
        jobs = jobs.exclude(employer=request.user)
    matches = [match_gig_to_skills(gig, skills) for gig in jobs]
    matches.sort(key=lambda item: (
        item["match_score"] is None,
        -(item["match_score"] or 0),
        -item["gig"].created_at.timestamp(),
    ))
    return JsonResponse({
        "jobs": [
            {
                "id": item["gig"].id,
                "title": item["gig"].title,
                "company": item["gig"].employer_name,
                "location": item["gig"].location,
                "description": item["gig"].description,
                "job_type": item["gig"].job_type,
                "job_type_display": item["gig"].get_job_type_display() if item["gig"].job_type else "",
                "pay": item["gig"].pay,
                "status": item["gig"].status,
                "required_skills": item["required_skills"],
                "matched_skills": item["matched_skills"],
                "missing_skills": item["missing_skills"],
                "match_score": item["match_score"],
                "explanation": item["explanation"],
                "learning_resources": item["resources"],
            }
            for item in matches
        ]
    })


def api_simulate_match(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "The request body must be a JSON object."}, status=400)
    user_skills = split_skills(
        payload["user_skills"] if "user_skills" in payload else get_saved_profile_skills(request.user)
    )
    selected_skill = str(payload.get("selected_skill") or "").strip()[:100]
    if not selected_skill:
        return JsonResponse({"error": "Choose a skill to simulate."}, status=400)
    candidate_keys = {normalize_skill(skill) for skill in user_skills}
    gigs = Gig.objects.filter(status__in=["open", "urgent"]).order_by("-created_at")
    if request.user.is_authenticated:
        gigs = gigs.exclude(employer=request.user)
    available_missing_skills = set()
    required_skill_keys = set()
    for gig in gigs:
        for skill in split_skills(gig.skills):
            skill_key = normalize_skill(skill)
            required_skill_keys.add(skill_key)
            if skill_key not in candidate_keys:
                available_missing_skills.add(skill_key)
    if required_skill_keys and normalize_skill(selected_skill) not in available_missing_skills:
        return JsonResponse({"error": "Choose a skill that is missing from a published job."}, status=400)
    increased_skills = split_skills([*user_skills, selected_skill])
    current_matches = [match_gig_to_skills(gig, user_skills) for gig in gigs]
    projected_matches = [match_gig_to_skills(gig, increased_skills) for gig in gigs]
    scored_current = [item["match_score"] for item in current_matches if item["match_score"] is not None]
    scored_projected = [item["match_score"] for item in projected_matches if item["match_score"] is not None]
    current_best = max(scored_current, default=None)
    projected_best = max(scored_projected, default=None)
    result = {
        "before": current_best,
        "after": projected_best,
        "selected_skill": selected_skill,
        "jobs_now_eligible": [
            item["gig"].title for item in projected_matches
            if item["match_score"] is not None and item["match_score"] >= 70
        ],
        "improvement": max(0, projected_best - current_best) if current_best is not None and projected_best is not None else None,
        "jobs_count": len(scored_current),
        "source": "published jobs in the current database",
    }
    return JsonResponse({"simulation": result, "status": "simulated"})


# -------------------------
# Google OAuth placeholders (needed because urls.py references them)
# -------------------------
def google_login(request):
    messages.info(request, "Google login coming soon!")
    return redirect("login")


def google_signup(request):
    messages.info(request, "Google signup coming soon!")
    return redirect("signup")


# -------------------------
# Jobs / Apply / Post
# -------------------------
@verified_login_required
def jobs_list(request):
    gigs = (
        Gig.objects
        .filter(status__in=["open", "urgent"])
        .select_related("employer")
        .order_by("-created_at")
    )

    applied_gig_ids = set(
        Application.objects.filter(applicant=request.user).values_list("gig_id", flat=True)
    )

    # ✅ Worker → Employer ratings shown on job cards
    rating_rows = (
        Rating.objects
        .filter(rating_type="worker_to_employer")
        .values("rated_user_id")
        .annotate(avg=Avg("stars"), cnt=Count("id"))
    )

    rating_map = {
        r["rated_user_id"]: {"avg": float(r["avg"] or 0), "cnt": int(r["cnt"] or 0)}
        for r in rating_rows
    }

    for g in gigs:
        stats = rating_map.get(g.employer_id, {"avg": 0.0, "cnt": 0})
        g.employer_avg_rating = stats["avg"]
        g.employer_rating_count = stats["cnt"]
        g.employer_display_name = (g.employer_name or g.employer.get_full_name() or g.employer.username)

    return render(request, "jobs.html", {
        "gigs": gigs,
        "applied_gig_ids": applied_gig_ids,
    })


@verified_login_required
def job_detail(request, gig_id):
    gig = get_object_or_404(
        Gig.objects.select_related("employer").filter(status__in=["open", "urgent"]),
        id=gig_id,
    )
    already_applied = (
        Application.objects.filter(gig=gig, applicant=request.user).exists()
        if gig.employer_id != request.user.id else False
    )
    is_owner = gig.employer_id == request.user.id
    match = match_gig_to_skills(gig, get_saved_profile_skills(request.user))
    return render(request, "job-detail.html", {
        "gig": gig,
        "is_owner": is_owner,
        "already_applied": already_applied,
        "can_view_contact": is_owner or already_applied,
        "match": match,
    })


@verified_login_required
def apply_to_gig(request, gig_id):
    if request.method != "POST":
        return redirect("jobs")

    gig = get_object_or_404(Gig, id=gig_id, status__in=["open", "urgent"])

    if gig.employer_id == request.user.id:
        messages.error(request, "You cannot apply to your own job.")
        return redirect("jobs")

    proposed_pay_raw = (request.POST.get("proposed_pay") or "").strip()
    payment_method = (request.POST.get("payment_method") or "full").strip().lower()

    try:
        proposed_pay = Decimal(proposed_pay_raw) if proposed_pay_raw else Decimal("0")
    except (InvalidOperation, ValueError):
        proposed_pay = Decimal("0")

    if payment_method not in ("full", "after"):
        payment_method = "full"

    UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.get_full_name() or request.user.username,
            "phone_number": "",
            "account_type": "worker",
            "skills": "",
            "verification_status": "approved",
            "aadhaar_verified": False,
        },
    )

    app, created = Application.objects.get_or_create(
        gig=gig,
        applicant=request.user,
        defaults={
            "proposed_pay": proposed_pay,
            "payment_method": payment_method,
            "status": "pending",
        },
    )

    if not created:
        messages.warning(request, "You already applied for this job.")
    else:
        messages.success(request, "Application submitted successfully!")

    return redirect("jobs")


@verified_login_required
def post_job(request):
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.get_full_name() or request.user.username,
            "phone_number": "",
            "account_type": "worker",
            "skills": "",
        },
    )

    if (profile.account_type or "").lower() not in ("employer", "both"):
        messages.info(request, "Select an Employer or Both account type to post a job.")
        completion_url = reverse("complete_profile")
        query = urlencode({"next": reverse("post_job")})
        return redirect(f"{completion_url}?{query}")

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        employer_name = (request.POST.get("employer_name") or "").strip()
        location = (request.POST.get("location") or "").strip()
        pay = (request.POST.get("pay") or "").strip()
        duration = (request.POST.get("duration") or "").strip()
        job_type = (request.POST.get("job_type") or "").strip().lower()
        work_schedule = (request.POST.get("schedule") or "").strip()
        contact_info = (request.POST.get("contact_info") or "").strip()
        skills = (request.POST.get("skills") or "").strip()

        form_errors = {}

        def add_form_error(field, message):
            form_errors.setdefault(field, []).append(message)

        for field, value, label in (
            ("title", title, "Job title"),
            ("employer_name", employer_name, "Your name or organization"),
            ("location", location, "Location"),
            ("pay", pay, "Pay offered"),
            ("description", description, "Job description"),
        ):
            if not value:
                add_form_error(field, f"{label} is required.")

        for field, value, label, limit in (
            ("title", title, "Job title", 200),
            ("employer_name", employer_name, "Your name or organization", 100),
            ("location", location, "Location", 200),
            ("pay", pay, "Pay offered", 50),
            ("duration", duration, "Duration", 100),
            ("work_schedule", work_schedule, "Work schedule", 200),
            ("contact_info", contact_info, "Contact information", 200),
            ("skills", skills, "Required skills", 200),
        ):
            if len(value) > limit:
                add_form_error(field, f"{label} must be {limit} characters or fewer.")

        valid_job_types = {value for value, _ in Gig.JOB_TYPE_CHOICES}
        if not job_type:
            add_form_error("job_type", "Employment type is required.")
        elif job_type not in valid_job_types:
            add_form_error("job_type", "Choose a valid employment type.")
        if not skills:
            add_form_error("skills", "Required skills are required.")

        if form_errors:
            return render(request, "post-job.html", {"form_errors": form_errors})

        Gig.objects.create(
            employer=request.user,
            title=title,
            description=description,
            employer_name=employer_name,
            location=location,
            pay=pay,
            duration=duration,
            job_type=job_type,
            work_schedule=work_schedule,
            contact_info=contact_info,
            skills=skills,
            status="open",
        )
        messages.success(request, "Job posted successfully.")
        return redirect("jobs")

    return render(request, "post-job.html")


# -------------------------
# Inbox
# -------------------------
@verified_login_required
def inbox(request):
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.get_full_name() or request.user.username,
            "phone_number": "",
            "account_type": "worker",
            "skills": "",
            "verification_status": "approved",
            "aadhaar_verified": False,
        },
    )

    acct = (profile.account_type or "").lower()

    employer_apps = None
    worker_apps = None

    if acct in ("employer", "both"):
        employer_apps = (
            Application.objects
            .filter(gig__employer=request.user)
            .select_related("gig", "applicant")
            .order_by("-applied_at")
        )

    if acct in ("worker", "both"):
        worker_apps = (
            Application.objects
            .filter(applicant=request.user)
            .select_related("gig", "gig__employer")
            .order_by("-applied_at")
        )

    return render(request, "inbox.html", {
        "profile": profile,
        "employer_apps": employer_apps,
        "worker_apps": worker_apps,
    })


# -------------------------
# Profile page
# -------------------------
@verified_login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.get_full_name() or request.user.username,
            "phone_number": "",
            "account_type": "worker",
            "skills": "",
            "verification_status": "approved",
            "aadhaar_verified": False,
        },
    )

    acct = (profile_obj.account_type or "worker").lower()

    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        phone = (request.POST.get("phone_number") or "").strip()
        skills = (request.POST.get("skills") or "").strip()
        account_type = (request.POST.get("account_type") or acct).strip().lower()

        if account_type not in ("worker", "employer", "both"):
            messages.error(request, "Invalid account type.")
            return redirect("profile")

        if full_name:
            profile_obj.full_name = full_name
        profile_obj.phone_number = phone
        profile_obj.skills = skills
        profile_obj.account_type = account_type

        if "profile_photo" in request.FILES:
            profile_obj.profile_photo = request.FILES["profile_photo"]

        profile_obj.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("profile")

    posted_gigs_qs = (
        Gig.objects.filter(employer=request.user)
        .annotate(applicants_count=Count("applications"))
        .order_by("-created_at")
    )

    total_posted = posted_gigs_qs.count()
    total_applicants_received = Application.objects.filter(gig__employer=request.user).count()
    total_applied_by_me = Application.objects.filter(applicant=request.user).count()

    my_applications = (
        Application.objects.filter(applicant=request.user)
        .select_related("gig", "gig__employer")
        .order_by("-applied_at")
    )

    received_applications = (
        Application.objects.filter(gig__employer=request.user)
        .select_related("gig", "applicant")
        .order_by("-applied_at")
    )

    return render(request, "profile.html", {
        "profile_obj": profile_obj,
        "acct": acct,
        "total_posted": total_posted,
        "total_applicants_received": total_applicants_received,
        "total_applied_by_me": total_applied_by_me,
        "posted_gigs": posted_gigs_qs,
        "my_applications": my_applications,
        "received_applications": received_applications,
    })


@verified_login_required
def complete_profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.get_full_name() or request.user.username,
            "phone_number": "",
            "account_type": "worker",
            "skills": "",
            "verification_status": "approved",
            "aadhaar_verified": False,
        },
    )

    requested_next = request.POST.get("next") if request.method == "POST" else request.GET.get("next")
    next_url = ""
    if requested_next and url_has_allowed_host_and_scheme(
        requested_next,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = requested_next

    next_is_post_job = bool(next_url) and urlsplit(next_url).path == reverse("post_job")
    cancel_url = request.META.get("HTTP_REFERER", "")
    if not cancel_url or not url_has_allowed_host_and_scheme(
        cancel_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ) or urlsplit(cancel_url).path in {
        reverse("complete_profile"),
        reverse("post_job"),
    }:
        cancel_url = reverse("jobs")

    if request.method == "POST":
        acct = (request.POST.get("account_type") or "").strip().lower()
        full_name = (request.POST.get("full_name") or "").strip()
        phone = (request.POST.get("phone_number") or "").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        elif len(full_name) > 200:
            errors.append("Full name must be 200 characters or fewer.")
        phone_digits = re.sub(r"\D", "", phone)
        if not phone:
            errors.append("Phone number is required.")
        elif len(phone) > 15 or len(phone_digits) < 7 or len(phone_digits) > 15:
            errors.append("Enter a valid phone number containing 7 to 15 digits.")
        if acct not in ("employer", "worker", "both"):
            errors.append("Choose an account type.")

        if errors:
            return render(request, "choose-account-type.html", {
                "profile": profile_obj,
                "errors": errors,
                "full_name": full_name,
                "phone_number": phone,
                "selected_account_type": acct,
                "next_url": next_url,
                "cancel_url": cancel_url,
            })

        profile_obj.account_type = acct
        profile_obj.full_name = full_name
        profile_obj.phone_number = phone
        profile_obj.save()
        messages.success(request, "Profile saved successfully.")

        if next_url and (acct in ("employer", "both") or not next_is_post_job):
            return redirect(next_url)
        return redirect("skill_dashboard")

    return render(request, "choose-account-type.html", {
        "profile": profile_obj,
        "full_name": profile_obj.full_name,
        "phone_number": profile_obj.phone_number,
        "selected_account_type": profile_obj.account_type,
        "next_url": next_url,
        "cancel_url": cancel_url,
    })


# -------------------------
# Employer actions
# -------------------------
@require_POST
@verified_login_required
def accept_application(request, app_id):
    app = get_object_or_404(Application, id=app_id)

    if app.gig.employer_id != request.user.id:
        messages.error(request, "Not allowed.")
        return redirect("inbox")

    if app.status != "pending":
        messages.info(request, "This application is already processed.")
        return redirect("inbox")

    app.status = "accepted"
    app.save(update_fields=["status"])

    app.gig.status = "filled"
    app.gig.save(update_fields=["status"])

    messages.success(request, "Application accepted. Gig marked as filled.")
    return redirect("inbox")


@require_POST
@verified_login_required
def reject_application(request, app_id):
    app = get_object_or_404(Application, id=app_id)

    if app.gig.employer_id != request.user.id:
        messages.error(request, "Not allowed.")
        return redirect("inbox")

    if app.status != "pending":
        messages.info(request, "This application is already processed.")
        return redirect("inbox")

    app.status = "rejected"
    app.save(update_fields=["status"])
    messages.success(request, "Application rejected.")
    return redirect("inbox")


@verified_login_required
def complete_job(request, app_id):
    app = get_object_or_404(
        Application,
        id=app_id,
        gig__employer=request.user,
        status="accepted",
    )
    app.status = "completed"
    app.save(update_fields=["status"])
    messages.success(request, "Job marked as completed.")
    return redirect("inbox")


# -------------------------
# Public profiles
# -------------------------
def employer_profile(request, user_id):
    employer = get_object_or_404(User, id=user_id)

    profile_obj, _ = UserProfile.objects.get_or_create(
        user=employer,
        defaults={
            "full_name": employer.get_full_name() or employer.username,
            "phone_number": "",
            "account_type": "employer",
            "skills": "",
            "verification_status": "approved",
            "aadhaar_verified": False,
        },
    )

    gigs = (
        Gig.objects.filter(employer=employer)
        .annotate(applicants_count=Count("applications"))
        .order_by("-created_at")
    )
    total_posted = gigs.count()
    total_applicants = Application.objects.filter(gig__employer=employer).count()

    rating_stats = Rating.objects.filter(
        rated_user=employer,
        rating_type="worker_to_employer",
    ).aggregate(avg=Avg("stars"), cnt=Count("id"))

    avg_rating = float(rating_stats["avg"] or 0)
    rating_count = int(rating_stats["cnt"] or 0)

    recent_ratings = (
        Rating.objects.filter(
            rated_user=employer,
            rating_type="worker_to_employer",
        )
        .select_related("rater")
        .order_by("-created_at")[:10]
    )

    return render(request, "employer-profile.html", {
        "employer": employer,
        "profile": profile_obj,
        "gigs": gigs,
        "total_posted": total_posted,
        "total_applicants": total_applicants,
        "avg_rating": avg_rating,
        "rating_count": rating_count,
        "recent_ratings": recent_ratings,
    })


def worker_profile(request, user_id):
    worker = get_object_or_404(User, id=user_id)

    profile_obj, _ = UserProfile.objects.get_or_create(
        user=worker,
        defaults={
            "full_name": worker.get_full_name() or worker.username,
            "phone_number": "",
            "account_type": "worker",
            "skills": "",
            "verification_status": "approved",
            "aadhaar_verified": False,
        },
    )

    total_completed = Application.objects.filter(applicant=worker, status="completed").count()
    total_applied = Application.objects.filter(applicant=worker).count()

    rating_stats = Rating.objects.filter(
        rated_user=worker,
        rating_type="employer_to_worker",
    ).aggregate(avg=Avg("stars"), cnt=Count("id"))

    avg_rating = float(rating_stats["avg"] or 0)
    rating_count = int(rating_stats["cnt"] or 0)

    recent_ratings = (
        Rating.objects.filter(
            rated_user=worker,
            rating_type="employer_to_worker",
        )
        .select_related("rater")
        .order_by("-created_at")[:10]
    )

    return render(request, "worker-profile.html", {
        "worker": worker,
        "profile": profile_obj,
        "total_completed": total_completed,
        "total_applied": total_applied,
        "avg_rating": avg_rating,
        "rating_count": rating_count,
        "recent_ratings": recent_ratings,
    })


# -------------------------
# Ratings
# -------------------------
@verified_login_required
def rate_employer(request, app_id):
    app = get_object_or_404(Application, id=app_id, applicant=request.user, status="completed")
    employer = app.gig.employer

    if app.worker_rated_employer:
        messages.info(request, "You already rated this employer.")
        return redirect("inbox")

    if request.method == "POST":
        stars = int(request.POST.get("stars") or 0)
        comment = (request.POST.get("comment") or "").strip()

        if stars < 1 or stars > 5:
            messages.error(request, "Please select a rating between 1 and 5.")
            return redirect("rate_employer", app_id=app.id)

        with transaction.atomic():
            Rating.objects.create(
                rating_type="worker_to_employer",
                rater=request.user,
                rated_user=employer,
                application=app,
                gig=app.gig,
                stars=stars,
                comment=comment,
            )
            app.worker_rated_employer = True
            app.save(update_fields=["worker_rated_employer"])

        messages.success(request, "Thanks! Your rating was submitted.")
        return redirect("inbox")

    return render(request, "rate-employer.html", {"app": app, "employer": employer})


@verified_login_required
def rate_worker(request, app_id):
    app = get_object_or_404(Application, id=app_id, gig__employer=request.user, status="completed")
    worker = app.applicant

    if app.employer_rated_worker:
        messages.info(request, "You already rated this worker.")
        return redirect("inbox")

    if request.method == "POST":
        stars = int(request.POST.get("stars") or 0)
        comment = (request.POST.get("comment") or "").strip()

        if stars < 1 or stars > 5:
            messages.error(request, "Please select a rating between 1 and 5.")
            return redirect("rate_worker", app_id=app.id)

        try:
            with transaction.atomic():
                Rating.objects.create(
                    rating_type="employer_to_worker",
                    rater=request.user,
                    rated_user=worker,
                    application=app,
                    gig=app.gig,
                    stars=stars,
                    comment=comment,
                )
                app.employer_rated_worker = True
                app.save(update_fields=["employer_rated_worker"])
        except Exception:
            messages.error(request, "Rating already exists or could not be saved.")
            return redirect("inbox")

        messages.success(request, "Thanks! Your rating for the worker was submitted.")
        return redirect("inbox")

    worker_profile_obj, _ = UserProfile.objects.get_or_create(
        user=worker,
        defaults={
            "full_name": worker.get_full_name() or worker.username,
            "phone_number": "",
            "account_type": "worker",
            "skills": "",
            "verification_status": "approved",
            "aadhaar_verified": False,
        },
    )

    return render(request, "rate-worker.html", {
        "app": app,
        "worker": worker,
        "worker_profile": worker_profile_obj,
    })


# -------------------------
# Static pages
# -------------------------
def parse_salary_amount(value):
    if value is None:
        return None, None
    raw = str(value).strip()
    if not raw:
        return None, None
    match = re.search(r"(\d+(?:\.\d+)?)", raw)
    if not match:
        return None, None
    amount = float(match.group(1))
    normalized = raw.lower()
    if "k" in normalized:
        amount *= 1000
    if "l" in normalized or "lac" in normalized or "lakhs" in normalized:
        amount *= 100000
    if "cr" in normalized or "crore" in normalized:
        amount *= 10000000
    currency = "INR" if any(symbol in raw for symbol in ("₹", "rs", "inr")) else "USD" if any(symbol in raw for symbol in ("$", "usd")) else "EUR" if any(symbol in raw for symbol in ("€", "eur")) else "GBP" if any(symbol in raw for symbol in ("£", "gbp")) else ""
    return amount, currency


def gig_is_entry_level(gig):
    haystack = " ".join([
        gig.title or "",
        gig.description or "",
        gig.location or "",
        gig.skills or "",
    ]).lower()
    return any(token in haystack for token in [
        "entry", "entry-level", "fresh graduate", "graduate", "intern",
        "apprentice", "beginner", "no experience", "basic", "starter"
    ])


def build_sdg1_learning_resources(job):
    normalized_skills = [normalize_skill(skill) for skill in split_skills(getattr(job, "skills", ""))]
    unique_skills = []
    seen = set()
    for skill in normalized_skills:
        if skill and skill not in seen:
            unique_skills.append(skill)
            seen.add(skill)
    resources = []
    for skill in unique_skills:
        skill_name = skill.replace("-", " ").title()
        links = LEARNING_RESOURCES.get(skill, [
            "https://www.youtube.com/results?search_query=" + skill.replace(" ", "+")
        ])
        reason = f"Useful for {job.title or 'this role'} and supports practical learning for local jobs."
        completed = False
        if hasattr(job, "user"):
            pass
        resources.append({
            "skill": skill_name,
            "skill_key": skill,
            "reason": reason,
            "links": links,
            "completed": completed,
        })
    return resources


def sdg1_opportunities(request):
    jobs = Gig.objects.filter(status__in=["open", "urgent"]).select_related("employer").order_by("-created_at")
    min_salary = request.GET.get("min_salary")
    location_filter = (request.GET.get("location") or "").strip()
    job_type = (request.GET.get("employment_type") or "").strip().lower()
    skills_filter = (request.GET.get("required_skills") or "").strip()
    entry_only = request.GET.get("entry_only") == "on"

    if min_salary:
        try:
            min_salary_value = float(min_salary)
            jobs = [gig for gig in jobs if parse_salary_amount(gig.pay)[0] is not None and parse_salary_amount(gig.pay)[0] >= min_salary_value]
        except ValueError:
            pass

    if location_filter:
        jobs = [gig for gig in jobs if location_filter.lower() in (gig.location or "").lower()]

    if job_type:
        jobs = [gig for gig in jobs if (gig.job_type or "").lower() == job_type]

    if skills_filter:
        requested = {normalize_skill(skill) for skill in split_skills(skills_filter)}
        jobs = [gig for gig in jobs if requested and requested.issubset({normalize_skill(skill) for skill in split_skills(gig.skills)})]

    if entry_only:
        jobs = [gig for gig in jobs if gig_is_entry_level(gig)]

    enriched_jobs = []
    for gig in jobs:
        salary_amount, currency = parse_salary_amount(gig.pay)
        required_skills = split_skills(gig.skills)
        skill_resources = []
        for skill in required_skills:
            skill_key = normalize_skill(skill)
            if not skill_key:
                continue
            resource_links = LEARNING_RESOURCES.get(skill_key, [
                "https://www.youtube.com/results?search_query=" + skill.replace(" ", "+")
            ])
            progress = False
            if request.user.is_authenticated:
                progress = SkillLearningProgress.objects.filter(user=request.user, skill_key=skill_key, completed=True).exists()
            skill_resources.append({
                "skill": skill,
                "skill_key": skill_key,
                "link": resource_links[0],
                "links": resource_links,
                "why_useful": f"Useful for {gig.title} and helps support a stronger application for local work.",
                "completed": progress,
            })
        enriched_jobs.append({
            "gig": gig,
            "required_skills": required_skills,
            "salary_amount": salary_amount,
            "salary_currency": currency or "",
            "salary_label": gig.pay if gig.pay else "Salary not provided",
            "entry_level": gig_is_entry_level(gig),
            "employment_type": gig.get_job_type_display() if gig.job_type else "Not specified",
            "learning_resources": skill_resources,
        })

    return render(request, "sdg1-opportunities.html", {
        "jobs": enriched_jobs,
        "selected_min_salary": min_salary,
        "selected_location": location_filter,
        "selected_employment_type": job_type,
        "selected_required_skills": skills_filter,
        "entry_only": entry_only,
        "location_options": sorted({location for location in Gig.objects.filter(status__in=["open", "urgent"]).exclude(location="").values_list("location", flat=True) if location}),
    })


def sdg1_impact(request):
    period_options = (6, 12, 24)
    try:
        period = int(request.GET.get("period", 12))
    except (TypeError, ValueError):
        period = 12
    if period not in period_options:
        period = 12

    worker_profiles = UserProfile.objects.filter(account_type__in=["worker", "both"])
    open_gigs = Gig.objects.filter(status__in=["open", "urgent"])
    applications = Application.objects.all()
    progress_records = SkillLearningProgress.objects.all()
    learning_records = progress_records.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(completed=True)),
    )
    learning_completion_rate = (
        round(learning_records["completed"] / learning_records["total"] * 100)
        if learning_records["total"] else None
    )

    total_registered_workers = worker_profiles.count()
    active_job_listings = open_gigs.count()
    total_applications = applications.count()
    application_status_counts = {
        row["status"]: row["total"]
        for row in applications.values("status").annotate(total=Count("id"))
    }
    completed_learning_records = learning_records["completed"]

    today = timezone.localdate()
    current_month = today.replace(day=1)
    month_starts = []
    for offset in range(period - 1, -1, -1):
        month_number = current_month.month - offset
        year = current_month.year
        while month_number <= 0:
            month_number += 12
            year -= 1
        month_starts.append(date(year, month_number, 1))

    timezone_for_dates = timezone.get_current_timezone()
    start_datetime = timezone.make_aware(
        datetime.combine(month_starts[0], time.min),
        timezone_for_dates,
    )

    def monthly_counts(queryset, date_field):
        rows = (
            queryset.filter(**{f"{date_field}__gte": start_datetime})
            .annotate(month=TruncMonth(date_field, tzinfo=timezone_for_dates))
            .values("month")
            .annotate(total=Count("id"))
        )
        return {
            (row["month"].year, row["month"].month): row["total"]
            for row in rows
        }

    worker_month_counts = monthly_counts(worker_profiles, "user__date_joined")
    job_month_counts = monthly_counts(Gig.objects.all(), "created_at")
    application_month_counts = monthly_counts(applications, "applied_at")
    completed_application_month_counts = monthly_counts(
        applications.filter(status="completed"),
        "applied_at",
    )

    trends = []
    for month_start in month_starts:
        month_key = (month_start.year, month_start.month)
        trends.append({
            "label": month_start.strftime("%b %Y"),
            "worker_registrations": worker_month_counts.get(month_key, 0),
            "job_postings": job_month_counts.get(month_key, 0),
            "applications": application_month_counts.get(month_key, 0),
            "completed_applications": completed_application_month_counts.get(month_key, 0),
        })

    trend_series = [
        {"key": "worker_registrations", "label": "Worker registrations", "color": "navy"},
        {"key": "job_postings", "label": "Job postings", "color": "teal"},
        {"key": "applications", "label": "Applications", "color": "gold"},
        {
            "key": "completed_applications",
            "label": "Completed application records (not verified hires)",
            "color": "green",
        },
    ]
    for series in trend_series:
        maximum = max((row[series["key"]] for row in trends), default=0)
        series["maximum"] = maximum
        series["points"] = []
        for row in trends:
            value = row[series["key"]]
            series["points"].append({
                "label": row["label"],
                "value": value,
                "height": round(value / maximum * 100) if maximum else 0,
            })

    funnel = [
        {"label": "Pending", "key": "pending", "count": application_status_counts.get("pending", 0)},
        {"label": "Accepted (not verified hires)", "key": "accepted", "count": application_status_counts.get("accepted", 0)},
        {"label": "Rejected", "key": "rejected", "count": application_status_counts.get("rejected", 0)},
        {
            "label": "Completed application records (not verified hires)",
            "key": "completed",
            "count": application_status_counts.get("completed", 0),
        },
    ]
    funnel_maximum = max((item["count"] for item in funnel), default=0)
    for item in funnel:
        item["width"] = round(item["count"] / funnel_maximum * 100) if funnel_maximum else 0

    job_type_rows = list(
        open_gigs.values("job_type").annotate(total=Count("id")).order_by("-total", "job_type")
    )
    job_types = [
        {
            "label": dict(Gig.JOB_TYPE_CHOICES).get(row["job_type"], "Not specified"),
            "count": row["total"],
        }
        for row in job_type_rows
    ]
    job_type_maximum = max((item["count"] for item in job_types), default=0)
    for item in job_types:
        item["width"] = round(item["count"] / job_type_maximum * 100) if job_type_maximum else 0

    application_job_type_rows = list(
        applications.values("gig__job_type")
        .annotate(total=Count("id"))
        .order_by("-total", "gig__job_type")
    )
    application_job_types = [
        {
            "label": dict(Gig.JOB_TYPE_CHOICES).get(row["gig__job_type"], "Not specified"),
            "count": row["total"],
        }
        for row in application_job_type_rows
    ]
    application_job_type_maximum = max(
        (item["count"] for item in application_job_types),
        default=0,
    )
    for item in application_job_types:
        item["width"] = (
            round(item["count"] / application_job_type_maximum * 100)
            if application_job_type_maximum else 0
        )

    worker_skill_counts = Counter()
    for skills_text in worker_profiles.values_list("skills", flat=True):
        worker_skill_counts.update(normalize_skill(skill) for skill in split_skills(skills_text))

    requested_skill_counts = Counter()
    for skills_text in open_gigs.values_list("skills", flat=True):
        requested_skill_counts.update(normalize_skill(skill) for skill in split_skills(skills_text))

    popular_worker_skills = [
        {"label": skill.title(), "count": count}
        for skill, count in worker_skill_counts.most_common(8)
    ]
    popular_requested_skills = [
        {"label": skill.title(), "count": count}
        for skill, count in requested_skill_counts.most_common(8)
    ]
    skill_gaps = [
        {
            "label": skill.title(),
            "demand": demand,
            "supply": worker_skill_counts.get(skill, 0),
            "gap": demand - worker_skill_counts.get(skill, 0),
        }
        for skill, demand in requested_skill_counts.items()
        if demand > worker_skill_counts.get(skill, 0)
    ]
    skill_gaps.sort(key=lambda item: (-item["gap"], -item["demand"], item["label"]))
    skill_gaps = skill_gaps[:8]
    skill_chart_maximum = max(
        [item["count"] for item in popular_worker_skills + popular_requested_skills],
        default=0,
    )
    for item in popular_worker_skills + popular_requested_skills:
        item["width"] = round(item["count"] / skill_chart_maximum * 100) if skill_chart_maximum else 0

    voluntary_improvements = None
    metrics = {
        "registered_job_seekers": total_registered_workers,
        "seeking_status": None,
        "employment_status": None,
        "verified_hires": None,
        "active_job_listings": active_job_listings,
        "job_applications": total_applications,
        "pending_applications": application_status_counts.get("pending", 0),
        "accepted_applications": application_status_counts.get("accepted", 0),
        "rejected_applications": application_status_counts.get("rejected", 0),
        "completed_applications": application_status_counts.get("completed", 0),
        "learning_resources_completed": completed_learning_records,
        "learning_records_total": learning_records["total"],
        "learning_completion_rate": learning_completion_rate,
        "voluntary_improvements": voluntary_improvements,
        "note": (
            "These figures describe platform activity and access to opportunities. "
            "The application does not currently record worker job-seeking status, "
            "current employment status, or independently verified hiring outcomes. "
            "Accepted and completed application records are not counted as verified hires."
        ),
    }
    return render(request, "sdg1-impact.html", {
        "metrics": metrics,
        "period": period,
        "period_options": period_options,
        "trends": trends,
        "trend_series": trend_series,
        "application_funnel": funnel,
        "job_types": job_types,
        "application_job_types": application_job_types,
        "popular_worker_skills": popular_worker_skills,
        "popular_requested_skills": popular_requested_skills,
        "skill_gaps": skill_gaps,
    })


def about(request):
    return render(request, "about.html")

def faq(request):
    return redirect("help_center")

def help_center(request):
    return render(request, "help-center.html")

def contact_support(request):
    return render(request, "contact-support.html")

def safety_guidelines(request):
    return render(request, "safety-guidelines.html")

def terms_redirect(request):
    return redirect("terms_of_service")

def terms_of_service(request):
    return render(request, "terms-of-service.html")


# -------------------------
# Location / Distance Calculation (optional)
# -------------------------
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def location(request):
    locations = [
        {"name": "Pune", "lat": 18.5204, "lng": 73.8567},
        {"name": "Chittoor", "lat": 13.2172, "lng": 79.1003},
    ]

    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        try:
            data = json.loads(request.body)
            user_lat = float(data.get("latitude"))
            user_lng = float(data.get("longitude"))

            results = []
            for loc in locations:
                distance = calculate_distance(user_lat, user_lng, loc["lat"], loc["lng"])
                results.append({"name": loc["name"], "distance": round(distance, 2)})

            return JsonResponse({"success": True, "distances": results})
        except (ValueError, KeyError, json.JSONDecodeError):
            return JsonResponse({"success": False, "error": "Invalid data"}, status=400)

    return render(request, "location.html", {"locations": locations})
