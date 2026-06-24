



from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.transaction import atomic
from django.db.models import Q

from rest_framework.decorators import ( 
    api_view,
    permission_classes, 
    authentication_classes
)
from rest_framework.response import Response
from rest_framework.status import *
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token

from core.models import *
from .serializers import LoanApplicationSerializer

# Create your views here.


@api_view(['POST'])
def loginStudent(request):

    username = request.data.get('username', None)
    password = request.data.get('password', None)


    try:
        user: User = authenticate(username=username, password=password)

        print("USER: ", user.username if user is not None else "Null")

        if not user:
            return Response({'message': 'Incorrect username of password'}, status=HTTP_404_NOT_FOUND)

        student: Student = Student.objects.get(user=user)

        student_map = student.toMap()

        user_token, created = Token.objects.get_or_create(user=user)

        if created:
            print('New Authentication Token created for: ', user_token)

        student_map['username'] = user.username 
        #student_map['email'] = user.email
        student_map['token'] = user_token.key

        if student.profile_picture is not None:
            #generate the absolute url for the media image. 
            absolute_url = request.build_absolute_uri(student.profile_picture.url)
            student_map['image_link'] = absolute_url

        #generate the user tokens here.
        return Response(student_map)

   
    except Exception as e:
        print(str(e))
        return Response({"message": 'Invalid username or password.'}, status=HTTP_404_NOT_FOUND)
    

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def signupStudent(request):

    username = request.data.get('username', None)
    password = request.data.get('password', None)
    full_name = request.data.get('name', None)
    email = request.data.get('email', None)
    ghana_card_number = request.data.get('ghana_card_number', None)
    phone_number = request.data.get('phone_number', None)
    gender = request.data.get('gender', 'male')
    #reference_number = request.data.get('reference_number', None)

    required_fields_values = [username, password, full_name, email, ghana_card_number, phone_number]

    
    profile_picture = request.FILES.get('profile_picture', None)

    if None in required_fields_values:
        print("Signup Error: Input fields should not none or empty")
        print(required_fields_values)

        return Response({'message': 'Invalid Data provided'}, status=HTTP_400_BAD_REQUEST)
    

    if User.objects.filter(username=username).exists():
        print("Signup Error: Username should be unique")
        return Response({'message': 'User already exists.'}, status=HTTP_400_BAD_REQUEST)
    
    if Student.objects.filter(ghana_card_number=ghana_card_number).exists():
        print('Signup Error: Ghana card number should be valid and unique')
        return Response({'message': 'Student already exist'})
    
    
    try:
        with atomic():

            name_split = full_name.split(' ')
            surname = name_split[0]
            first_names = name_split[1: len(name_split)]

            user = User.objects.create(
                username=username, 
                last_name=surname, 
                first_name=first_names,
                email=email, 
            )
            user.set_password(password)
            user.save()

            print("[SIGN UP] user object created")

            #TODO: change fix the gender from the frontend
            student = Student.objects.create(
                user=user,
                phone_number=phone_number,
                ghana_card_number=ghana_card_number, 
                gender=gender
            )

            if profile_picture: 
                student.profile_picture = profile_picture
                student.save()
                student.refresh_from_db()
                print("[SIGN UP] saved profile picture")

            token = Token.objects.create(user=user)

            student_map = student.toMap()
            student_map['username'] = user.username
            student_map['token'] = token.key

            if student.profile_picture is not None:
                #generate the absolute url for the media image. 
                absolute_url = request.build_absolute_uri(student.profile_picture.url)
                student_map['image_link'] = absolute_url
            
            print("[SIGN UP] Wrapping everything up")
            
            #todo: generate the verification code.
            code = generate_otp()

            AccountVerification.objects.create(user=user, code=code)

            #TODO: send the verification code to the email provided
            #also it is going to be fail silent kind of send.

            return Response(student_map)
    
    except Exception as e:
        print(f'Signup Error: {e}') 
        return Response({'message': 'Invalid Data provided'}, status=HTTP_400_BAD_REQUEST)

    pass 



def generate_otp():
    import random 
    random_numbers = [str(random.randint(0, 9)) for _ in range(6)]
    return ''.join(random_numbers)
    


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def request_otp(request):
    user = request.user

    acc_verification = AccountVerification.objects.filter(user=user)

    if acc_verification.exists():
        acc_verification.delete()
        pass

    verification_code = generate_otp()

    AccountVerification.objects.create(user=user, code=verification_code)

    #todo: send the verification code the user's email
    try:
        print(f'VERIFCATION CODE FOR {user.email}: {verification_code}')
        #logic to send the email comes here.
        pass
    except Exception as e:
        return Response({'message': 'Could not send verification code.'}, status=HTTP_500_INTERNAL_SERVER_ERROR)
        
    pass

    return Response({'message': f'Verification code sent to {user.email}.'})


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def verify_otp(request):

    user = request.user 

    verification_code = request.data.get('otp')

    if not verification_code:
        return Response({'message': 'Please provide the verification_code(code)'}, stauts=HTTP_400_BAD_REQUEST)
    
    account_verification = AccountVerification.objects.get(user=user)

    is_code_match = account_verification.code == verification_code

    return Response(
        {
            'message': 'Verified' if is_code_match else 'Invalid verification code'
        }, 
        status = HTTP_200_OK if is_code_match else HTTP_404_NOT_FOUND
    )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([AllowAny])
def updateUserInfo(request):

    user: User = request.user

    student = Student.objects.get(user=user)

    
    was_updated = False

    if 'new_password'  in request.data:
        old_password = request.data['old_password']
        new_password = request.data['new_password']

        if not user.check_password(old_password):
            return Response({'message': ''}, status=HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        was_updated = True

    
    if 'last_name' in request.data and 'first_name' in request.data:
        first_name = request.data['first_name']
        last_name = request.data['last_name']

        if not (first_name.strip() or last_name.strip()):
            return Response({'message': 'New name or last name should not be empty'}, status=HTTP_400_BAD_REQUEST)
            
        user.first_name = first_name
        user.last_name = last_name 
        was_updated = True

    
    if 'reference_number' in request.data:
        reference_number = request.data['reference_number']
        student.reference_number = reference_number 

        was_updated = True 

    if 'index_number' in request.data:
        index_number = request.data['index_number']
        student.index_number = index_number 
        
        was_updated = True

    
    if 'ghana_card_number' in request.data:
        ghana_card_number = request.data['ghana_card_number']
        try:
            student.ghana_card_number = ghana_card_number
            was_updated = True
        except:
            return Response({'message': 'Invalid ghana card number'}, status=HTTP_400_BAD_REQUEST)
        

    if 'phone_number' in request.data:
        phone_number = request.data['phone_number']
        student.phone_number = phone_number
        was_updated = True

    
    if 'level' in request.data:
        level = request.data['level']
        student.level = level
        was_updated = True

    
    if 'program' in request.data:
        program = request.data['program']
        student.program = program 
        was_updated = True

    
    if not was_updated:
        user.save()
        student.save()

    return Response({'message': 'User information has been updated.'})




@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getDashboardData(request):

    user = request.user
    student = Student.objects.get(user=user)


    print(f'[GET DASHBOARD] Student Name -> {student.user.last_name}')

    loan_applications = LoanApplication.objects.filter(student=student)

    loans = Loan.objects.filter(student=student, payment_status='active')

    total_loan_amount = sum([loan.approved_amount for loan in loans])

    payments = LoanPayment.objects.filter(loan__in=loans, status='disbursed')

    total_paid_amount = sum([payment.amount for payment in payments])

    documents = ApplicationDocument.objects.filter(student=student)

    outstanding_debt = total_loan_amount - total_paid_amount

    #retreive the next payment

    dashboard_map = {
        'total_applications': loan_applications.count(),
        'total_loans': loans.count(),
        'total_documents': documents.count(),
        'total_loan_amount': total_loan_amount,
        'total_paid_amount': total_paid_amount,
        'outstanding_debt': outstanding_debt
    }

    return Response(dashboard_map)



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getLoanApplications(request):

    user = request.user 

    student = Student.objects.get(user=user)

    applications = LoanApplication.objects.filter(student=student)

    return Response([application.toMap() for application in applications])


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getApplicationInfo(request, application_id):

    application = LoanApplication.objects.filter(id=application_id)

    if not application.exists():
        return Response(
            {'message': f'Loan Applicatio, "{application_id}" does not exits'},
            status=HTTP_404_NOT_FOUND
        )
    
    application = application.first()

    info = StudentApplicationInfo.objects.get(loan_application=application)

    return Response(info.toMap())


# @api_view(['POST'])
# @authentication_classes([TokenAuthentication])
# @permission_classes([IsAuthenticated])
# def submitLoanApplication(request):

#     user = request.user
#     student = Student.objects.get(user=user)


#     amount_requested = request.data.get('amount_requested')
#     loan_reason = request.data.get('loan_reason')

#     #personal information
#     first_names = request.data.get('first_names')
#     surname = request.data.get('surname')
#     phone_number = request.data.get('phone_number')
#     email = request.data.get('email')
#     ghana_card_number = request.data.get('ghana_card_number')

#     #parental/guardian information
#     guardian_name = request.data.get('guardian_name')
#     guardian_relationship = request.data.get('guardian_relationship')
#     guardian_phone_number = request.data.get('guardian_phone_number')

#     #academic information
#     reference_number = request.data.get('reference_number')
#     index_number = request.data.get('index_number')
#     program = request.data.get('program')
#     level = request.data.get('level')
#     department = request.data.get('department')


#     app_document_keys = ['ghana_card', 'student_id', 'admission_letter', 'passport_photo']
#     app_documents = [request.FILES.get(key) for key in app_document_keys]


#     if None in [first_names, surname, phone_number, email, 
#                 ghana_card_number, reference_number, index_number, program, level, 
#                 department, amount_requested, loan_reason]:
#         return Response({'message': 'Invalid data'}, status=HTTP_400_BAD_REQUEST)
    

#     if None in app_documents:
#         return Response({'message': 'Please upload all required files'}, status=HTTP_400_BAD_REQUEST)


#     try:

#         with atomic():
#             application = LoanApplication.objects.create( 
#                 student=student, 
#                 amount_requested=amount_requested, 
#                 loan_reason=loan_reason
#             )

#             application_info = StudentApplicationInfo.objects.create( 
#                 loan_application=application,
#                 first_names=first_names, 
#                 surname=surname,
#                 phone_number=phone_number, 
#                 email=email, 
#                 ghana_card_number=ghana_card_number, 

#                 guardian_name = guardian_name, 
#                 guardian_relationship = guardian_relationship, 
#                 guardian_phone_number = guardian_phone_number,
                
#                 reference_number = reference_number, 
#                 index_number=index_number, 
#                 program=program,
#                 level=level, 
#                 department=department
#             )


#             for i in range(len(app_document_keys)):
#                 document_type = app_document_keys[i]
#                 file = app_documents[i]

#                 ApplicationDocument.objects.create( 
#                     application=application,
#                     student=student, 
#                     document_type=document_type,
#                     file=file
#                 )

#                 pass

#             return Response({'message': 'Application submitted successfully'})
#         pass 
#     except Exception as e: 
#         return Response({
#             'message': str(e),
#         }, status=HTTP_500_INTERNAL_SERVER_ERROR)

#     pass



@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitLoanApplication(request):

    user = request.user 
    student = Student.objects.get(user=user)

    loan_filter = Loan.objects.filter(student=student, payment_status='active')

    if loan_filter.exists():
        return Response(
            {'message': 'Cannot submit a new application while you have an active loan'}, 
            status=HTTP_403_FORBIDDEN
        )


    serializer = LoanApplicationSerializer(
        data=request.data,
        context={'request': request}
    )

    if serializer.is_valid():

        application = serializer.save()

        #todo: send a websocket notification to the user.

        return Response(
            {
                'message': 'Loan application submitted successfully',
                'application_id': application.id
            },
        )

    return Response(
        serializer.errors,
        status=HTTP_400_BAD_REQUEST
    )


@api_view(['PUT'])
@authentication_classes([])
@permission_classes([AllowAny])
def updateLoanApplication(request, application_id):

    application = LoanApplication.objects.filter(id=application_id)

    if not application.exists():
        return Response({'message': f'Application, {application_id}, not found'}, status=HTTP_404_NOT_FOUND)

    application = application.first()

    serializer = LoanApplicationSerializer(
        instance=application, 
        data=request.data,
        partial=True
    )

    if not serializer.is_valid():
        return Response({'message': str(serializer.errors)}, status=HTTP_400_BAD_REQUEST)
    

    return Response({'message': f'Loan Application, {application_id}, was succesfully updated.'})


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getLoans(request):

    user = request.user 

    student = Student.objects.get(user=user)

    loans = Loan.objects.filter(student=student)
    
    return Response([loan.toMap() for loan in loans])



@api_view(['GET'])
def getDocuments(request):

    user = request.user 

    student = Student.objects.get(user=user)

    documents = ApplicationDocument.objects.filter(student=student)

    return Response([document.toMap() for document in documents])




@api_view(['POST'])
def makePayment(request):
    return Response()

