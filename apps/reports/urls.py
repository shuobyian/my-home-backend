from django.urls import re_path

from apps.common.routing import route
from apps.reports import views

urlpatterns = [
    route("report", views.ReportListView.as_view()),
    re_path(r"^report/(?P<pk>[0-9]{1,9})/?$", views.ReportDetailView.as_view()),
]
