from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.status import *
from django.contrib.auth import authenticate
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.core.cache import cache

from core.models import *
from core.document_verification import DocumentVerificationService
from channels.layers import get_channel_layer
from asgiref.sync import sync_to_async

from core.utils import LogActionType
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
def logout(request):
    logout(request.user)
    return Response({'message': 'User logged out'})


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getLoanApplications(request):
    applications = LoanApplication.objects.all()
    return Response([application.toMap() for application in applications])





@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def getLoans(request):
    loans = Loan.objects.all()
    return Response([loan.toMap() for loan in loans])


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def payments(request):
    payments = LoanPayment.objects.all()
    return Response([payment.toMap() for payment in payments])




#TODO: fix sending notification much easier
@api_view(['POST'])
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

            if application.status in ['submitted']:
                application.status = 'under_review'
                application.save()

            #anything greater than submitted will not need this update.

        except LoanApplication.DoesNotExist:
            return Response({'error': 'Application not found'}, status=HTTP_404_NOT_FOUND)
        
        cache_key = f'application_detail_{application.id}'

        #Check the cache if it's available
        if cache.has_key(cache_key):
            print("Returning the data from the cache.")
            return Response(cache.get(cache_key))
        
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


        response_map = {
            'application': application.toMap(),
            'application_info': app_info.toMap() if app_info else None,
            'review': review.toMap(),
            'documents': documents_with_fraud_analysis
        }

        #Override the cache with the new response map
        cache.add(cache_key, response_map)
        
        return Response(response_map, status=HTTP_200_OK)
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
            return Response({'message': 'Application not found'}, status=HTTP_404_NOT_FOUND)
        
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

        #A Loan Object is created with the approved amount 
        #once the user's application has been approved
        Loan.objects.create(  
            application=application, 
            issuer=request.user, 
            student=application.student, 
            approved_amount=request.data.get('approved_amount'),
            interest_rate=request.data.get('interest_rate'), 
            duration=request.data.get('duration'),
            loan_status='awaiting_disbursement'
        )
        
        #TODO: Create notification for student
        notification = Notification.objects.create(
            user=application.student.user,
            title='Loan Application Approved',
            message=f'Your loan application for GHC {approved_amount} has been approved!',
            notification_type='success'
        )

        #send the notification via websocket to the student.
        notification_channel = get_channel_layer()

        sync_to_async(notification_channel.group_send)(  
            f'notification_{application.user.username}', 
            {
                'type': 'send_notification', 
                'data': notification.toMap()
            }
        )
        

        #TODO: also send an email to the student.


        #TODO: create an audit log
        AuditLog.objects.create(  
            actor = request.user,
            target_model = application.__class__.__name__,
            target_id = application.id,
            action= LogActionType.LOAN_APPROVAL,
            description='Aproval of Loan Application',
            affected_user=application.student.user
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
        notification = Notification.objects.create(
            user=application.student.user,
            title='Loan Application Rejected',
            message=f'Your loan application has been rejected. Reason: {rejection_reason}',
            notification_type='warning'
        )

        #send the notificaiton to the student via the web socket
        notification_channel = get_channel_layer()

        sync_to_async(notification_channel.group_send)( 
            f'notification_{application.student.user.username}',
            {
                'type': 'send_notification',#the event inside the Notification consumer
                'data': notification.toMap()
            }
        )

        #TODO: also send email notification to the student.


        #create the audit log.
        AuditLog.objects.create(  
            actor=request.user, 
            action=LogActionType.LOAN_REJECTION,
            description='Reject of loan application',
            target_model=application.__class__.__name__, 
            target_id=application.id,
            affected_user=application.student.user
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



#================================LOAN AMOUNT VIEWS===============
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def disburseAmount(request, loan_id):

    try:
        loan = Loan.objects.get(id=loan_id)
    except Loan.DoesNotExist:
        return Response({'message': 'Loan does not exists'}, status=HTTP_404_NOT_FOUND)
    
    if loan.status == 'disbursed':
        return Response({'Loan has already been disbursed'}, status=HTTP_400_BAD_REQUEST)

    #TODO: logic to move to 
    loan.status = 'disbursed'
    loan.save()


    notification = Notification.objects.create( 
        user=loan.objects.user, 
        title='Disbursement Notice', 
        message=f'An amount of GHS {loan.approvedAmount} has been disbursed to your account',
        notification_type='info'
    )


    AuditLog.objects.create(  
        actor = request.user,
        target_model = loan.__class__.__name__,
        target_id = loan.id,
        action= LogActionType.LOAN_APPROVAL,
        description='Aproval of Loan Application',
        affected_user=loan.student.user
    )


    channel_layer = get_channel_layer()

    sync_to_async(channel_layer.group_send)( 
        f'notification_{loan.user.username}',
        {
            'type': 'send_notification',
            'data': notification.toMap()
        }
    )

    return Response({'message': 'Loan has sucessfully been disbursed'})



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def markLoanAsCompleted(request, loan_id):

    try:
        loan = Loan.objects.get(id=loan_id)
    except Loan.DoesNotExist:
        return Response({'message': ''}, status=HTTP_404_NOT_FOUND)
    
    payable_amount = loan.approved_amount + ((loan.interest_rate/100) * loan.approved_amount)
    
    total_payments = (LoanPayment.objects.filter(loan=loan)
                .aggregate(total=Sum('amount'))['total'])
    
    if total_payments < payable_amount:
        return Response({'message': 'Cannot mark loan as completed.'}, status=HTTP_400_BAD_REQUEST)

    loan.loan_status = 'completed'
    loan.save()

    notification = Notification.objects.create(  
        user=loan.user, 
        title='Loan Completed', 
        message=f'Loan, {loan_id}, has been marked as completed.'
    )


    AuditLog.objects.create( 
        actor=request.user, 
        action=LogActionType.CHANGE_LOAN_STATUS, 
        description='Loan has be marked as completed', 
        target_model=loan.__class__.__name__, 
        target_id=loan.id, 
        affected_user=loan.user,
    )

    channel_layer = get_channel_layer()

    sync_to_async(channel_layer.group_send)( 
        f'notification_{loan.user.username}',
        {
            'type': 'send_notification', 
            'data': notification.toMap()
        }
    )
    return Response({'message': 'Status updated sucessfully'})



@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
def recordManualPayment(request):

    loan_id = request.data.get('loan_id', None)
    amount = request.data.get('payment_amount', None)
    payment_method = request.data.get('payment_method', None)
    notes = request.data.get('notes', '')

    if None in [loan_id, amount, payment_method]:
        return Response({'message': 'Loan ID or amount paid or payment status should not be empty'}, status=HTTP_400_BAD_REQUEST)

    loan = Loan.objects.get(id=loan_id)

    #create the payment object
    loan_payment = LoanPayment.objects.create(
        loan = loan, 
        student = loan.student, 
        amount = amount, 
        payment_method = payment_method,
        status = 'completed'
    )

    if notes:
        loan_payment.notes = notes
        loan_payment.save()



    #create an audit log. 
    AuditLog.objects.create(  
        actor = request.user, 
        action = 'LOAN_MANUAL_PAYMENT',
        description = f'Manual Payment Recorded for loan, {loan_id}, amount: {amount}',
        affected_user = loan.student.user, 
        target_model = loan_payment.__class__.__name__,
        target_id=loan_payment.id
    )

    return Response(loan_payment.toMap())



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


def user_object_toMap(user: User, request=None):

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



@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def createAdminUser(request):

    last_name = request.data.get('last_name', '')
    first_names = request.data.get('first_name', '')
    email = request.data.get('email', None)
    username = request.data.get('username', '')

    is_superuser = request.data.get('is_superuser', False)

    #use all if you want to check whether every element in the subset can be found in the universal set.
    #user any if you to check if atleast one item in the subset can be found in the universal set. 

    
    if any(item in [last_name, first_names, email, username, email] for item in [None, '']):
        return Response({"message":"Required fields should not be empty"}, status=HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(username=username).exists():
        return Response({'Usernames must be unique'})
    

    user = User.objects.create(
        username = username, 
        last_name = last_name, 
        first_name = first_names, 
        email = email,
        is_superuser = is_superuser,
        is_staff = True
    )

    #generate an 8 character password.
    password = generate_password()
    user.set_password(password)
    user.save()

    #TODO: send a notification the person's email

    
    AuditLog.objects.create(  
        actor=request.user, 
        action=LogActionType.CREATE_USER,
        description='Created a new admin user', 
        target_model=user.__class__.__name__,
        target_id=user.username,
        affected_user=user
    ).save()

    user_map = user_object_toMap(user)

    return Response(user_map)


#this function generates password with only the only text and numbers.
def generate_password() -> str:

    import string
    import random

    characters = string.ascii_letters + string.digits

    return ''.join(random.sample(characters, k = 8))




@api_view(['put'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateUserStatus(request,):

    username = request.data.get('username', None)
    is_active = request.data.get('is_active', True)


    if not username:
        return Response({'message': 'Provide the username'}, status=HTTP_400_BAD_REQUEST)

    affected_user = User.objects.get(username=username)
    affected_user.is_active = is_active


    notification_message = f'Your account, @{username} '

    if not is_active:
        notification_message += '''has been temporarily suspended due to activity that requires further review.
                    During this period, access to certain features may be unavailable. 
                    If you believe this was made in error, please contact support for assistance.'''
    else: 
        notification_message += '''has been activated and access has been restored. 
                            You may now continue using available features and services. 
                            Thank you for your patience.'''

    
    log_description = 'Suspended user account' if is_active else 'Activated user account'

    notification = Notification.objects.create( 
        user=affected_user, 
        notification_type='info',
        title='User status change',
        message=notification_message
    )


    #send a notification to the user via the websocket.
    notification_channel = get_channel_layer()

    sync_to_async(notification_channel.group_send)( 
        f'notification_{username}', 
        {
            'type': 'send_notification', 
            'data': notification.toMap()
        }
    )


    AuditLog.objects.create( 
        actor=request.user, 
        action=LogActionType.CHANGE_USER_STATUS, 
        description=log_description,
        target_model=affected_user.__class__.__name__, 
        target_id=username, #the username of the affected user.
    )

    return Response({'message': 'User status changed.'})



@api_view(['PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateUserRole(request):

    username = request.data.get('username', None)
    new_role = request.data.get('password', None)

    if None in (username, new_role):
        return Response({'message': 'Username or role should be provided'}, status=HTTP_400_BAD_REQUEST)
    
    user = User.objects.get(username=username)

    old_role = 'superuser' if user.is_superuser else 'admin'

    if new_role == 'superuser':
        user.is_superuser = True 

    if new_role == 'admin':
        if user.is_superuser:
            user.is_superuser = False
        
        user.is_staff = True 

    
    notification = Notification.objects.create( 
        user=user, 
        notification_type='info',
        title='User status change',
        message=f'Your user role has been changed from {old_role} to {new_role}'
    )

    
    #TODO: Send a notifcation to the affected user.
    #send a notification to the user via the websocket.
    notification_channel = get_channel_layer()

    sync_to_async(notification_channel.group_send)( 
        f'notification_{username}', 
        {
            'type': 'send_notification', 
            'data': notification.toMap()
        }
    )


    #create an audit log
    AuditLog.objects.create( 
        actor=request.user, 
        action=LogActionType.CHANGE_USER_ROLE,
        description=f'Change user role from {old_role} to {new_role}',
        target_model= user.__class__.__name__,
        target_id=username, 
        affected_user=user
    )

    return Response({'message': 'User has been updated'})


@api_view(['GET'])
def getUserFromStudentId(request, student_id):

    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({"message": 'student does not exist'}, status=HTTP_404_NOT_FOUND)
    

    response_map = user_object_toMap(student.user)

    return Response(response_map)



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getUserReviewStatistics(request, username):

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist: 
        return Response({'message': 'The requested user not \'{username}\' not found'}, status=HTTP_404_NOT_FOUND)
    
    application_reviews = LoanReview.objects.filter(reviewed_by=user)

    statuses = ['pending', 'approved', 'rejected']

    stat_dict = {'total_reviews': application_reviews.count()}

    for status in statuses:
        status_count = application_reviews.filter(status=status).count()
        stat_dict[status] = status_count

    return Response(stat_dict)



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getUserActivity(request, username):

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist: 
        return Response({'message': f'The requested user not \'{username}\' not found'}, status=HTTP_404_NOT_FOUND)
    
    user_logs = AuditLog.objects.filter(actor=user)

    return Response([log.toMap() for log in user_logs])



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentInfo(request, username):

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist: 
        return Response({'message': 'The requested user not \'{username}\' not found'}, status=HTTP_404_NOT_FOUND)
    
    try:
        student = Student.objects.get(user=user)
    except Student.DoesNotExist:
        return Response({'message': 'Student doe not exist'}, status=HTTP_404_NOT_FOUND)

    return Response(student.toMap())



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentLoanApplications(request, username):

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist: 
        return Response({'message': 'The requested user not \'{username}\' not found'}, status=HTTP_404_NOT_FOUND)
    

    try:
        student = Student.objects.get(user=user)
    except Student.DoesNotExist:
        print(f'[GET STUDENT LOANS] - Could not find student object associated to user {username}')
        return Response({'message': 'User should be a student'}, status=HTTP_404_NOT_FOUND)
    
    applications = LoanApplication.objects.filter(student=student)

    return Response([application.toMap() for application in applications])



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentLoans(request, username):

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist: 
        return Response({'message': f'The requested user not \'{username}\' not found'}, status=HTTP_404_NOT_FOUND)
    

    try:
        student = Student.objects.get(user=user)
    except Student.DoesNotExist:
        print(f'[GET STUDENT LOANS] - Could not find student object associated to user {username}')
        return Response({'message': 'User should be a student'}, status=HTTP_404_NOT_FOUND)
    
    loans = Loan.objects.filter(student=student)

    return Response([loan.toMap() for loan in loans])


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getLoanPayments(request, loan_id):

    try:
        loan = Loan.objects.get(loan_id)
    except: 
        return Response({'message': 'Loan does not exist'}, status=HTTP_404_NOT_FOUND)
    
    payments = LoanPayment.objects.filter(loan=loan)

    return Response([payment.toMap() for payment in  payments])
