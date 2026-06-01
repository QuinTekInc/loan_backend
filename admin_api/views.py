from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.status import *
from django.contrib.auth import authenticate
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from core.models import *

# Create your views here.

@api_view(['POST'])
def loginAdmin(request):

    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response({'message': 'Incorrect username or password'}, status=HTTP_404_NOT_FOUND)
    

    #todo: build the user data here.

    return Response({'message': 'User login successful'})



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated, IsAdminUser])
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