from apps.common.routing import route
from apps.results import views

urlpatterns = [
    route("result", views.ResultView.as_view()),
    route("result/calculator", views.CalculatorView.as_view()),
    route("catalog/check", views.CatalogCheckView.as_view()),
]
