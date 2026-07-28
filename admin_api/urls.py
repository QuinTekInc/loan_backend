
from django.urls import path 

from . import views

urlpatterns = [
    # Existing endpoints
    path('login/', views.loginAdmin, name='login_admin'),
    path('applications/', views.getLoanApplications, name='get_loan_applications'),
    path('loans/', views.getLoans, name='get_loans'),
    path('payments/', views.payments, name='payments'),
    path('send-notification/', views.sendNotification, name='send_notification'),
    
    # Loan Approval Workflow endpoints
    path('applications/review/pending/', views.getApplicationsForReview, name='get_applications_for_review'),
    path('applications/<uuid:application_id>/review/details/', views.getApplicationReviewDetails, name='get_application_review_details'),
    path('applications/<uuid:application_id>/approve/', views.approveApplication, name='approve_application'),
    path('applications/<uuid:application_id>/reject/', views.rejectApplication, name='reject_application'),
    path('applications/<uuid:application_id>/comments/', views.addReviewComments, name='add_review_comments'),
    path('applications/filter/', views.getApplicationsByStatus, name='get_applications_by_status'),
    path('applications/<uuid:application_id>/review/history/', views.getReviewHistory, name='get_review_history'),
    path('applications/stats/', views.getApprovalStats, name='get_approval_stats'),


    #loan management endpoints
    path('loans/<uuid:loan_id>/disburse/', views.disburseAmount),
    path('loans/<uuid:loan_id>/mark-as-completed/', views.markLoanAsCompleted),
    path('loans/<uuid:loan_id>/payments/', views.getLoanPayments),
    path('record-manual-payment/', views.recordManualPayment),
    
    # Document Verification & Fraud Detection endpoints
    path('applications/<uuid:application_id>/documents/', views.getDocumentsForApplication, name='get_documents_for_application'),
    path('documents/<uuid:document_id>/analyze/', views.analyzeSingleDocument, name='analyze_single_document'),


    #user management endpoints
    path('get-users/', views.getUsers),
    path('create-user/', views.createAdminUser),
    path('change-user-status/', views.updateUserStatus),
    path('change-user-role/', views.updateUserRole),
    path('users/student/<uuid:student_id>/', views.getUserFromStudentId),
    path('users/<str:username>/review-statistics/', views.getUserReviewStatistics),
    path('users/<str:username>/activity/', views.getUserActivity),

    path('users/<str:username>/studentInfo', views.getStudentInfo),
    path('users/<str:username>/loan-applications/', views.getStudentLoanApplications),
    path('users/<str:username>/loans/', views.getStudentLoans)
]
