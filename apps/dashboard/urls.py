from django.urls import path

from apps.dashboard.views.overview import OverviewView

app_name = 'dashboard'

urlpatterns = [
    path('api/dashboard/overview/', OverviewView.as_view(), name='overview'),
]
