
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [

    path('login/', views.loginStudent),
    path('signup/', views.signupStudent),
    path('update-user-info/', views.updateUserInfo),

    path('request-otp/', views.request_otp),

    #dashboard
    path('get-dashboard-data/', views.getDashboardData),


    #loan applications 
    path('get-loan-applications/', views.getLoanApplications),
    path('get-application-info/<str:application_id>', views.getApplicationInfo),

    #submitting/updating loan applications and its related documents.
    path('submit-loan-application/', views.submitLoanApplication),
    path('update-loan-application/<str:application_id>', views.updateLoanApplication),


    #loan application documents
    path('get-documents/', views.getDocuments),

    #loans
    path('get-loans/', views.getLoans)
]


