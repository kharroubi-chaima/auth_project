from django.urls import path
from .views import ChatbotView, PrescriptionScannerView

urlpatterns = [
    path('chat/', ChatbotView.as_view(), name='chatbot_api'),
    path('scan/', PrescriptionScannerView.as_view(), name='prescription_scan'),
]
