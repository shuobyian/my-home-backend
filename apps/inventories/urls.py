from apps.common.routing import route
from apps.inventories import views

urlpatterns = [
    route("inventory", views.InventoryView.as_view()),
]
