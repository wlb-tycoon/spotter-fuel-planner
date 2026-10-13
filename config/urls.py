from django.urls import path

from planner import views

urlpatterns = [
    path("", views.home, name="home"),
    path("api/v1/route-plans/", views.create_plan, name="create-plan"),
    path("api/v1/health/", views.health),
    path("maps/<uuid:plan_id>/", views.map_view, name="map"),
]
