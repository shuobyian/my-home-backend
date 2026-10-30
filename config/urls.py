from django.urls import include, path

from apps.common.routing import route
from apps.common.views import health

urlpatterns = [
    route("", health),
    path("", include("apps.accounts.urls")),
    path("", include("apps.products.urls")),
    path("", include("apps.markets.urls")),
    path("", include("apps.results.urls")),
    path("", include("apps.experiences.urls")),
    path("", include("apps.inventories.urls")),
    path("", include("apps.logs.urls")),
    path("", include("apps.reports.urls")),
]

handler400 = "apps.common.views.bad_request"
handler404 = "apps.common.views.not_found"
handler500 = "apps.common.views.server_error"
