from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.status import *
from django.contrib.auth import authenticate
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone

from core.models import *
from core.document_verification import DocumentVerificationService

# Create your views here.

@api_view(['POST'])
def loginAdmin(request):

    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response({'message': 'Incorrect username or password'}, status=HTTP_404_NOT_FOUND)

    
    token, _  = Token.objects.get_or_create(user=user)
    
    #todo: build the user data here.
    response_map = user_object_toMap(user)
    response_map['token'] = token.key

    return Response(response_map)



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getLoanApplications(request):
    applications = LoanApplication.objects.all()
    return Response([application.toMap() for application in applications])




def getLoans(request):
    loans = LoanApplication.objects.all()
    return Response([loan.toMap() for loan in loans])


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def payments(request):
    payments = LoanPayment.objects.all()
    
    return Response([payment.toMap() for payment in payments])



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def sendNotification(request):
    #todo: trigger a push notification send
    return


# ============ LOAN APPROVAL WORKFLOW VIEWS ============

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def getApplicationsForReview(request):
    """Get all applications pending review"""
    try:
        reviews = LoanReview.objects.filter(status='pending')
        return Response({
            'count': reviews.count(),
            'data': [review.toMap() for review in reviews]
        }, status=HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def getApplicationReviewDetails(request, application_id):
    """
    Get detailed review information for a specific application
    Includes AI-powered fraud detection analysis for documents
    """
    try:
        try:
            application = LoanApplication.objects.get(id=application_id)
        except LoanApplication.DoesNotExist:
            return Response({'error': 'Application not found'}, status=HTTP_404_NOT_FOUND)
        
        # Get or create review
        review, created = LoanReview.objects.get_or_create(application=application)
        
        app_info = application.application_information.first()
        
        # Get all documents and run fraud detection on each
        documents = application.documents.all()
        documents_with_fraud_analysis = []
        
        verification_service = DocumentVerificationService()
        
        for doc in documents:
            doc_data = doc.toMap()
            
            try:
                # Run fraud detection on document
                verification_result = verification_service.verify_document_complete(
                    doc.file,
                    expected_ghana_card=app_info.ghana_card_number if app_info else None
                )
                
                doc_data['fraud_detection_analysis'] = {
                    'verification_status': verification_result['verification_status'],
                    'ocr_confidence': verification_result['ocr_confidence'],
                    'fraud_detection': verification_result['fraud_detection'],
                    'extracted_fields': verification_result['extracted_fields'],
                    'requires_manual_review': verification_result['requires_manual_review'],
                    'cross_validation_passed': verification_result.get('cross_validation_passed', None),
                }
            except Exception as e:
                doc_data['fraud_detection_analysis'] = {
                    'verification_status': 'ERROR',
                    'error': f'Could not analyze document: {str(e)}',
                    'requires_manual_review': True,
                }
            
            documents_with_fraud_analysis.append(doc_data)
        
        return Response({
            'application': application.toMap(),
            'application_info': app_info.toMap() if app_info else None,
            'review': review.toMap(),
            'documents': documents_with_fraud_analysis
        }, status=HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def approveApplication(request, application_id):
    """Approve a loan application"""
    try:
        try:
            application = LoanApplication.objects.get(id=application_id)
        except LoanApplication.DoesNotExist:
            return Response({'error': 'Application not found'}, status=HTTP_404_NOT_FOUND)
        
        # Get or create review
        review, created = LoanReview.objects.get_or_create(application=application)
        
        # Get data from request
        approved_amount = request.data.get('approved_amount')
        comments = request.data.get('comments', '')
        
        if approved_amount is None:
            return Response({'error': 'approved_amount is required'}, status=HTTP_400_BAD_REQUEST)
        
        # Update review
        review.status = 'approved'
        review.reviewed_by = request.user
        review.approved_amount = approved_amount
        review.comments = comments
        review.reviewed_at = timezone.now()
        review.save()
        
        # Update application status
        application.status = 'approved'
        application.updated_at = timezone.now()
        application.save()
        
        # Create notification for student
        Notification.objects.create(
            user=application.student.user,
            title='Loan Application Approved',
            message=f'Your loan application for GHC {approved_amount} has been approved!',
            notification_type='success'
        )
        
        return Response({
            'message': 'Application approved successfully',
            'review': review.toMap()
        }, status=HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def rejectApplication(request, application_id):
    """Reject a loan application"""
    try:
        try:
            application = LoanApplication.objects.get(id=application_id)
        except LoanApplication.DoesNotExist:
            return Response({'error': 'Application not found'}, status=HTTP_404_NOT_FOUND)
        
        # Get or create review
        review, created = LoanReview.objects.get_or_create(application=application)
        
        # Get data from request
        rejection_reason = request.data.get('rejection_reason')
        comments = request.data.get('comments', '')
        
        if not rejection_reason:
            return Response({'error': 'rejection_reason is required'}, status=HTTP_400_BAD_REQUEST)
        
        # Update review
        review.status = 'rejected'
        review.reviewed_by = request.user
        review.rejection_reason = rejection_reason
        review.comments = comments
        review.reviewed_at = timezone.now()
        review.save()
        
        # Update application status
        application.status = 'rejected'
        application.updated_at = timezone.now()
        application.save()
        
        # Create notification for student
        Notification.objects.create(
            user=application.student.user,
            title='Loan Application Rejected',
            message=f'Your loan application has been rejected. Reason: {rejection_reason}',
            notification_type='warning'
        )
        
        return Response({
            'message': 'Application rejected successfully',
            'review': review.toMap()
        }, status=HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def addReviewComments(request, application_id):
    """Add or update comments on an application review"""
    try:
        try:
            application = LoanApplication.objects.get(id=application_id)
        except LoanApplication.DoesNotExist:
            return Response({'error': 'Application not found'}, status=HTTP_404_NOT_FOUND)
        
        # Get or create review
        review, created = LoanReview.objects.get_or_create(application=application)
        
        # Get comments from request
        comments = request.data.get('comments', '')
        
        if not comments:
            return Response({'error': 'comments field is required'}, status=HTTP_400_BAD_REQUEST)
        
        # Update review comments
        review.comments = comments
        review.save()
        
        return Response({
            'message': 'Comments added successfully',
            'review': review.toMap()
        }, status=HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def getApplicationsByStatus(request):
    """Get applications filtered by status"""
    try:
        status = request.query_params.get('status', None)
        
        if not status:
            return Response({'error': 'status query parameter is required'}, status=HTTP_400_BAD_REQUEST)
        
        valid_statuses = ['draft', 'submitted', 'under_review', 'approved', 'rejected', 'cancelled']
        if status not in valid_statuses:
            return Response({'error': f'Invalid status. Valid options: {valid_statuses}'}, status=HTTP_400_BAD_REQUEST)
        
        applications = LoanApplication.objects.filter(status=status)
        
        return Response({
            'status': status,
            'count': applications.count(),
            'data': [application.toMap() for application in applications]
        }, status=HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def getReviewHistory(request, application_id):
    """Get review history for an application"""
    try:
        try:
            application = LoanApplication.objects.get(id=application_id)
        except LoanApplication.DoesNotExist:
            return Response({'error': 'Application not found'}, status=HTTP_404_NOT_FOUND)
        
        try:
            review = LoanReview.objects.get(application=application)
            return Response({
                'review': review.toMap()
            }, status=HTTP_200_OK)
        except LoanReview.DoesNotExist:
            return Response({
                'message': 'No review found for this application',
                'review': None
            }, status=HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def getApprovalStats(request):
    """Get approval statistics"""
    try:
        total_applications = LoanApplication.objects.count()
        approved = LoanApplication.objects.filter(status='approved').count()
        rejected = LoanApplication.objects.filter(status='rejected').count()
        under_review = LoanApplication.objects.filter(status='under_review').count()
        pending_review = LoanReview.objects.filter(status='pending').count()
        
        approval_rate = (approved / total_applications * 100) if total_applications > 0 else 0
        
        return Response({
            'total_applications': total_applications,
            'approved': approved,
            'rejected': rejected,
            'under_review': under_review,
            'pending_review': pending_review,
            'approval_rate': round(approval_rate, 2)
        }, status=HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


# ============ DOCUMENT VERIFICATION & FRAUD DETECTION VIEWS ============

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def analyzeSingleDocument(request, document_id):
    """
    Analyze a single document for fraud
    
    Query params:
    - expected_ghana_card: Optional Ghana Card number to cross-validate
    """
    try:
        try:
            document = ApplicationDocument.objects.get(id=document_id)
        except ApplicationDocument.DoesNotExist:
            return Response({'error': 'Document not found'}, status=HTTP_404_NOT_FOUND)
        
        # Get expected Ghana Card from query params
        expected_ghana_card = request.query_params.get('expected_ghana_card', None)
        
        # Initialize verification service
        verification_service = DocumentVerificationService()
        
        # Verify document
        result = verification_service.verify_document_complete(
            document.file,
            expected_ghana_card=expected_ghana_card
        )
        
        return Response(result, status=HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def getDocumentsForApplication(request, application_id):
    """
    Get all documents for an application with fraud detection analysis
    """
    try:
        try:
            application = LoanApplication.objects.get(id=application_id)
        except LoanApplication.DoesNotExist:
            return Response({'error': 'Application not found'}, status=HTTP_404_NOT_FOUND)
        
        documents = application.documents.all()
        documents_with_analysis = []
        
        verification_service = DocumentVerificationService()
        app_info = application.application_information.first()
        
        for doc in documents:
            doc_data = doc.toMap()
            
            try:
                # Run fraud detection on document
                verification_result = verification_service.verify_document_complete(
                    doc.file,
                    expected_ghana_card=app_info.ghana_card_number if app_info else None
                )
                
                doc_data['fraud_detection_analysis'] = {
                    'verification_status': verification_result['verification_status'],
                    'ocr_confidence': verification_result['ocr_confidence'],
                    'fraud_detection': verification_result['fraud_detection'],
                    'requires_manual_review': verification_result['requires_manual_review'],
                }
            except Exception as e:
                doc_data['fraud_detection_analysis'] = {
                    'verification_status': 'ERROR',
                    'error': str(e),
                    'requires_manual_review': True,
                }
            
            documents_with_analysis.append(doc_data)
        
        return Response({
            'application_id': str(application.id),
            'document_count': len(documents_with_analysis),
            'documents': documents_with_analysis
        }, status=HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=HTTP_500_INTERNAL_SERVER_ERROR)





@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getUsers(request):

    current_user: User = request.user;

    if not current_user.is_superuser:
        return Response({'message': 'Out of bounds'}, status=HTTP_401_UNAUTHORIZED)

    users = User.objects.all()

    users_map_list = list(map(user_object_toMap, users))

    return Response(users_map_list)


def user_object_toMap(user: User):

    user_role = 'admin'

    if user.is_superuser:
        user_role = 'superuser'
    elif Student.objects.filter(user=user).exists():
        user_role = 'student'

    user_map = {
        'username': user.username,
        'first_name': user.first_name, 
        'last_name': user.last_name, 
        'email': user.email, 
        'role': user_role, 
        'status': 'active' if user.is_active else 'suspended'
    }

    return user_map