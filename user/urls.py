from django.urls import path
from .views import UserAPIView, UserDeleteAPIView, UserLoginAPIView, ISPRangeListAPIView, ClientRangeListAPIView, UserUpdateAPIView, ActivateAccount, ResendActivationEmail, InviteUserView, SetPasswordView, PhoneRegisterView, ResendActivationCode, SelfDeleteAPIView, GetProfileAPIView

urlpatterns = [
    path('register', UserAPIView.as_view(), name = 'auth_register'),
    path('phone/register', PhoneRegisterView.as_view(), name = 'auth_phone_register'),
    path('login', UserLoginAPIView.as_view(), name='auth_login'),
    path('delete', UserDeleteAPIView.as_view(), name='user_delete'),
    path('update', UserUpdateAPIView.as_view(), name='user-update'),
    path('isprange', ISPRangeListAPIView.as_view(), name = 'isp-range-list'),
    path('getprofile', GetProfileAPIView.as_view(), name = 'get-profile'),
    path('clientrange', ClientRangeListAPIView.as_view(), name = 'client-range-list'),
    path('id/<int:pk>', UserAPIView.as_view(), name = 'get-user-by-id'),
    path('activate', ActivateAccount.as_view(), name='activate'),
    path('phone/activate/<str:otp>', PhoneRegisterView.as_view(), name = 'activate_phone'),
    path('phone/resend/<int:pk>', ResendActivationCode.as_view(), name = 'resend_activation'),
    path('resend-activation/', ResendActivationEmail.as_view(), name='resend_activation'),
    path('invite', InviteUserView.as_view(), name='invite_user'),
    path('set_password/<token>', SetPasswordView.as_view(), name='accept_invite'),
    path('deleteaccount', SelfDeleteAPIView.as_view(), name='deactivate-acccount')
]