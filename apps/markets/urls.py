from apps.common.routing import route
from apps.markets import views

urlpatterns = [
    route("market", views.MarketView.as_view()),
]
