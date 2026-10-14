from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import resolve_url

from .models import UserProfile


class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        return "/"


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_login_redirect_url(self, request):
        return "/"

    def get_signup_redirect_url(self, request):
        return "/"

    def save_user(self, request, sociallogin, form=None):
        """
        Called after a social login/signup to save the Django user.
        Ensure a corresponding UserProfile exists for social signups
        (e.g. Google). Create a minimal profile so views that expect
        `UserProfile` (like `post_job`) don't fail.
        """
        user = super().save_user(request, sociallogin, form=form)

        # Create a UserProfile if it doesn't exist yet
        try:
            if not UserProfile.objects.filter(user=user).exists():
                full_name = (user.get_full_name() or sociallogin.account.extra_data.get('name') or user.username)
                UserProfile.objects.create(
                    user=user,
                    full_name=full_name,
                    phone_number="",
                    account_type="worker",
                    verification_status="pending",
                )
        except Exception:
            # Don't raise - profile creation failure shouldn't break login
            pass

        return user
