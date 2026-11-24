from django.urls import path

from apps.billing.views import PlanListView, SubscriptionView

app_name = 'billing'

urlpatterns = [
    path('api/billing/plans/', PlanListView.as_view(), name='plans'),
    path('api/billing/subscription/', SubscriptionView.as_view(), name='subscription'),
]
