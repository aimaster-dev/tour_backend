from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
import random
# Create your models here.


class MyUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff = True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser = True.")
        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150)
    usertype = models.IntegerField(default=3)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(unique=True)
    tourplace = models.JSONField(blank=True, default=list)
    venue = models.ForeignKey(
        'tourplace.Venue', on_delete=models.SET_NULL, null=True, blank=True)
    isp = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers',
        limit_choices_to={'usertype': 2}
    )
    status = models.BooleanField(default=False)
    has_unlimited_access = models.BooleanField(default=False)
    level = models.IntegerField(default=0)
    device_token = models.CharField(
        max_length=150, null=True, blank=True, default='')
    is_invited = models.BooleanField(default=False)
    is_activate = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MyUserManager()

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def get_user_type_display(self):
        user_types = {
            1: 'Admin',
            2: 'ISP',
            3: 'Customer'
        }
        return user_types.get(self.usertype, 'Unknown')

    def is_admin(self):
        return self.usertype == 1

    def is_isp(self):
        return self.usertype == 2

    def is_customer(self):
        return self.usertype == 3

    def has_free_recording_access(self):
        return self.usertype in [1, 2] or self.has_unlimited_access

    class Meta:
        db_table = 'user_tbl'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return self.email


class Invitation(models.Model):
    email = models.EmailField()
    token = models.CharField(max_length=100, unique=True)
    tourplace = models.JSONField(blank=True, default=list)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


class EmailOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'otp_tbl'

    def generate_otp(self):
        self.otp = str(random.randint(100000, 999999))
        self.save()
