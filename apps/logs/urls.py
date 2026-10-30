from apps.common.routing import route
from apps.logs import views

urlpatterns = [
    route("log", views.ActivityLogView.as_view()),
]
