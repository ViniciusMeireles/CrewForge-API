from django.urls import path

from apps.billing.views import (
    AsaasWebhookView,
    BillingProfileView,
    InvoiceListView,
    PlanListView,
    SubscriptionCancelView,
    SubscriptionChangeView,
    SubscriptionDiscardChangeView,
    SubscriptionPreviewView,
    SubscriptionResumeView,
    SubscriptionView,
)

app_name = 'billing'

urlpatterns = [
    path('api/billing/plans/', PlanListView.as_view(), name='plans'),
    path('api/billing/subscription/', SubscriptionView.as_view(), name='subscription'),
    path(
        'api/billing/subscription/preview/',
        SubscriptionPreviewView.as_view(),
        name='subscription-preview',
    ),
    path(
        'api/billing/subscription/change/',
        SubscriptionChangeView.as_view(),
        name='subscription-change',
    ),
    path(
        'api/billing/subscription/cancel/',
        SubscriptionCancelView.as_view(),
        name='subscription-cancel',
    ),
    path(
        'api/billing/subscription/resume/',
        SubscriptionResumeView.as_view(),
        name='subscription-resume',
    ),
    path(
        'api/billing/subscription/discard-change/',
        SubscriptionDiscardChangeView.as_view(),
        name='subscription-discard-change',
    ),
    path('api/billing/profile/', BillingProfileView.as_view(), name='profile'),
    path('api/billing/invoices/', InvoiceListView.as_view(), name='invoices'),
    path(
        'api/billing/webhooks/asaas/',
        AsaasWebhookView.as_view(),
        name='webhook-asaas',
    ),
]
