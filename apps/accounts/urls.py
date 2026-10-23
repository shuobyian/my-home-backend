from apps.accounts import views
from apps.common.routing import route

urlpatterns = [
    route("auth/signup", views.SignupView.as_view()),
    route("auth/login", views.LoginView.as_view()),
    route("auth/logout", views.LogoutView.as_view()),
    route("auth/me", views.MeView.as_view()),
    route("auth/password", views.PasswordView.as_view()),
]
