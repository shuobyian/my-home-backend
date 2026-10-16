from django.urls import include, path

from apps.common.routing import route
from apps.common.views import health

urlpatterns = [
    route("", health),
    path("", include("apps.products.urls")),
    path("", include("apps.markets.urls")),
    path("", include("apps.results.urls")),
    path("", include("apps.experiences.urls")),
]

handler404 = "apps.common.views.not_found"
handler500 = "apps.common.views.server_error"
