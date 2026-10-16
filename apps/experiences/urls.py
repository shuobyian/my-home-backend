from apps.common.routing import route
from apps.experiences import views

urlpatterns = [
    route("experience", views.ExperienceView.as_view()),
    route("experience/walnut", views.WalnutView.as_view()),
]
