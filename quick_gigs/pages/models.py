# models.py
# Place this in your Django app directory

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import os

def user_directory_path(instance, filename):
    """File will be uploaded to MEDIA_ROOT/user_<id>/<filename>"""
    return f'user_{instance.user_profile.user.id}/{filename}'

class UserProfile(models.Model):
    """Extended user profile with verification fields"""
    
    ACCOUNT_TYPES = (
        ('worker', 'Service Provider'),
        ('employer', 'Client'),
        ('both', 'Both'),
    )
    
    VERIFICATION_STATUS = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Basic Information
    full_name = models.CharField(max_length=200, help_text="Full name as per Aadhaar")
    phone_number = models.CharField(max_length=15)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    
    # Aadhaar Verification
    aadhaar_name = models.CharField(max_length=200, blank=True, help_text="Name extracted from Aadhaar")
    aadhaar_verified = models.BooleanField(default=False)
    
    # Skills
    skills = models.TextField(blank=True, help_text="Comma-separated list of skills")
    
    # Verification Status
    verification_status = models.CharField(
        max_length=10, 
        choices=VERIFICATION_STATUS, 
        default='pending'
    )
    rejection_reason = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True, help_text="Internal notes for admin")
    
    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Profile
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.full_name} ({self.user.email})"
    
    def get_skills_list(self):
        """Return skills as a list"""
        return [s.strip() for s in self.skills.split(',') if s.strip()]
    
    def is_verified(self):
        """Check if user is verified"""
        return self.verification_status == 'approved' and self.aadhaar_verified
    
    def can_login(self):
        """Check if user can access the platform"""
        return self.verification_status == 'approved'


class VerificationDocument(models.Model):
    """Store user verification documents"""
    
    DOCUMENT_TYPES = (
        ('aadhaar_front', 'Aadhaar Card - Front'),
        ('aadhaar_back', 'Aadhaar Card - Back'),
        ('skill_certificate', 'Skill Certificate'),
        ('work_sample', 'Work Sample'),
        ('license', 'License'),
        ('other', 'Other'),
    )
    
    user_profile = models.ForeignKey(
        UserProfile, 
        on_delete=models.CASCADE, 
        related_name='verification_documents'
    )
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to=user_directory_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['document_type', '-uploaded_at']
        verbose_name = 'Verification Document'
        verbose_name_plural = 'Verification Documents'
    
    def __str__(self):
        return f"{self.user_profile.full_name} - {self.get_document_type_display()}"
    
    def filename(self):
        """Get just the filename without path"""
        return os.path.basename(self.file.name)


class Gig(models.Model):
    """Job/Gig posting model (existing)"""
    # Add this if it doesn't exist

    JOB_TYPE_CHOICES = (
        ("full-time", "Full Time"),
        ("part-time", "Part Time"),
        ("contract", "Contract"),
        ("temporary", "Temporary"),
    )
    
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('urgent', 'Urgent'),
        ('filled', 'Filled'),
        ('closed', 'Closed'),
    )
    
    employer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posted_gigs')
    title = models.CharField(max_length=200)
    description = models.TextField()
    employer_name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    pay = models.CharField(max_length=50)
    duration = models.CharField(max_length=100, blank=True)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, blank=True, default="")
    work_schedule = models.CharField(max_length=200, blank=True)
    contact_info = models.CharField(max_length=200, blank=True)
    workers_needed = models.IntegerField(default=1)
    skills = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class SkillLearningProgress(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="skill_learning_progress",
    )
    skill_key = models.CharField(max_length=100)
    skill_name = models.CharField(max_length=100)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "skill_key"],
                name="uniq_user_skill_learning_progress",
            )
        ]
        ordering = ["skill_name"]

    def __str__(self):
        return f"{self.user.username}: {self.skill_name}"


# pages/models.py

class Application(models.Model):
    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="applications")
    proposed_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, default="full")

    worker_rated_employer = models.BooleanField(default=False)
    employer_rated_worker = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=(
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("completed", "Completed"),
        ),
        default="pending",
    )

    # ✅ keep for now if already migrated, but DO NOT USE it anymore
    rated = models.BooleanField(default=False)

    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-applied_at"]
        unique_together = ["gig", "applicant"]


    
class Rating(models.Model):
    RATING_TYPES = (
        ("worker_to_employer", "Worker → Employer"),
        ("employer_to_worker", "Employer → Worker"),
    )

    rating_type = models.CharField(max_length=30, choices=RATING_TYPES)

    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings_given_v2")
    rated_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings_received_v2")

    application = models.ForeignKey("Application", on_delete=models.CASCADE, related_name="ratings_v2")
    gig = models.ForeignKey("Gig", on_delete=models.SET_NULL, null=True, blank=True)

    stars = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["application", "rating_type"],
                                    name="uniq_rating_per_side_per_app_v2")
        ]

    def __str__(self):
        return f"{self.rating_type}: {self.rater.username} → {self.rated_user.username} ({self.stars})"
