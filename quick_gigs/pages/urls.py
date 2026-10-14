from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # Home
    path("", views.home, name="home"),

    # Authentication
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("verification-status/", views.verification_status, name="verification_status"),
    path("logout/", views.logout_view, name="logout"),

    # Google OAuth placeholders
    path("auth/google/login/", views.google_login, name="google_login"),
    path("auth/google/signup/", views.google_signup, name="google_signup"),

    # Core pages
    path("inbox/", views.inbox, name="inbox"),
    path("jobs/", views.jobs_list, name="jobs"),
    path("jobs/<int:gig_id>/", views.job_detail, name="job_detail"),
    path("dashboard/", views.skill_dashboard, name="skill_dashboard"),
    path("job-matches/", views.job_matches, name="job_matches"),
    path("resume-builder/", views.resume_builder, name="resume_builder"),
    path("voice-demo/", views.voice_demo, name="voice_demo"),
    path("apply/<int:gig_id>/", views.apply_to_gig, name="apply_to_gig"),
    path("post-job/", views.post_job, name="post_job"),
    path("complete-profile/", views.complete_profile, name="complete_profile"),
    path("profile/", views.profile, name="profile"),

    # SkillMatch APIs
    path("api/health/", views.api_health, name="api_health"),
    path("api/skills/extract/", views.api_extract_skills, name="api_extract_skills"),
    path("api/profile/skills/", views.api_save_profile_skills, name="api_save_profile_skills"),
    path("api/learning/progress/", views.api_save_learning_progress, name="api_save_learning_progress"),
    path("api/experience/analyze/", views.api_experience_analyze, name="api_experience_analyze"),
    path("api/resumes/generate/", views.api_generate_resume, name="api_generate_resume"),
    path("api/resumes/extract/", views.api_extract_resume, name="api_extract_resume"),
    path("api/resumes/pdf/", views.api_resume_pdf, name="api_resume_pdf"),
    path("api/jobs/recommendations/", views.api_job_recommendations, name="api_job_recommendations"),
    path("api/matching/simulate/", views.api_simulate_match, name="api_simulate_match"),

    # Canonical static pages
    path("about/", views.about, name="about"),
    path("sdg1/", views.sdg1_opportunities, name="sdg1_opportunities_alias"),
    path("sdg1-opportunities/", views.sdg1_opportunities, name="sdg1_opportunities"),
    path("sdg1-impact/", views.sdg1_impact, name="sdg1_impact"),
    path("contact-support/", views.contact_support, name="contact_support"),
    path("faq/", views.faq, name="faq"),
    path("help-center/", views.help_center, name="help_center"),
    path("safety-guidelines/", views.safety_guidelines, name="safety_guidelines"),
    path("terms-of-service/", views.terms_of_service, name="terms_of_service"),

    # Short URL aliases (for old links / footer links)
    path("contact/", views.contact_support, name="contact_alias"),
    path("help/", views.help_center, name="help_alias"),
    path("safety/", views.safety_guidelines, name="safety_alias"),
    path("terms/", views.terms_of_service, name="terms_alias"),
    path("application/<int:app_id>/accept/", views.accept_application, name="accept_application"),
    path("application/<int:app_id>/reject/", views.reject_application, name="reject_application"),
    path("employer/<int:user_id>/", views.employer_profile, name="employer_profile"),
    path("application/<int:app_id>/complete/", views.complete_job, name="complete_job"),
    path("application/<int:app_id>/rate/", views.rate_employer, name="rate_employer"),
    path("rate-worker/<int:app_id>/", views.rate_worker, name="rate_worker"),
    path("worker/<int:user_id>/", views.worker_profile, name="worker_profile"),
    path("location/", views.location, name="location"),
]


# Media in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
