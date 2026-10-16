from apps.common.routing import route
from apps.products import views

urlpatterns = [
    route("product", views.ProductView.as_view()),
    route("product/all", views.ProductBulkCreateView.as_view()),
    route("product/login", views.LoginView.as_view()),
]
