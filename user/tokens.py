from django.contrib.auth.tokens import PasswordResetTokenGenerator
import six


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Token generator for email verification.
    """
    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk) + six.text_type(timestamp) +
            six.text_type(user.is_verified)
        )


email_verification_token = EmailVerificationTokenGenerator()
