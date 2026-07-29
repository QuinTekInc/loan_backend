
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async, async_to_sync
from .models import Notification
from django.contrib.auth.models import User 

import json

class NotificationConsumer(AsyncWebsocketConsumer):

    #for broadcasting
    group_name = "notification"
    headers = None


    async def connect(self):

        self.headers = get_headers(self.scope)
        print(f'[NOTIFICATION SOCKET] - Headers: {self.headers}')

        self.token_key = get_auth_token(self.headers)

        print(f'[NOTIFICATION SOCKET] - Token: {self.token_key}')
        
        self.user = await self.get_user_from_token(self.token_key)


        if not self.user: 
            await self.close(reason='could to verify user')
            return
        

        if not self.user.is_authenticated:
            await self.close(reason='Authentication is required.')
            return


        self.group_name = f'notification_{self.user.username}'

        await self.channel_layer.group_add( 
            self.group_name, 
            self.channel_name
        )

        
        #create a global notification consumer
        # await self.channel_layer.group_add( 
        #     'global_notifications', 
        #     self.channel_name
        # )

        await self.accept()

        #send the initial data to the user.
        initial_notifications = await self.get_user_notifications(self.user)
    
        await self.send( 
            text_data=json.dumps(initial_notifications)
        )

        pass


    async def disconnect(self, code):

        if self.group_name is None: 
            return
        

        await self.channel_layer.group_discard(
            self.group_name, 
            self.channel_name
        )

        print(f'[NOTIFICATION WEBSOCKET] - {self.group_name} disconnected')
        pass


    async def receive(self, text_data = None, bytes_data=None):

        decoded = json.loads(text_data)

        action_type = decoded.get('type', None)

        if not action_type:
            print('Data recieved must contain the "type" parameter')
            return
        
        if action_type == 'mark_as_read':
            #retrive the notification id
            notification_id = decoded.get('id', None)
            self.mark_notification_as_read(notification_id=notification_id)

        if action_type == 'mark_all_as_read':
            self.mark_notification_as_read(all=True)
            pass
        
        pass
    


    async def send_notification(self, event):
        await self.send(
            text_data=json.dumps(event['data']))
        pass


    @database_sync_to_async 
    def get_user_from_token(self, token_key: str) -> User:

        from rest_framework.authtoken.models import Token 

        token_filter = Token.objects.filter(key=token_key.strip())

        if not token_filter.exists():
            print('No user exists yet.')
            return None


        return token_filter.first().user

    

    @database_sync_to_async
    def mark_notification_as_read(self, notification_id=None, is_update_all=False):
        if notification_id is not None:
            notification = Notification.objects.get(id=notification_id)
            notification.is_read = True 
            notification.save()
            return
        

        if not is_update_all:
            return

        notifications = Notification.objects.filter(user=self.user, is_read=False)
        
        for notification in notifications:
            notification.is_read = True
            notification.save()
            pass

        pass

    
    
    @database_sync_to_async 
    def get_user_notifications(self, user):
        notifications = Notification.objects.filter(user=user)

        return [notification.toMap() for notification in notifications]

    

class DashboardConsumer(AsyncWebsocketConsumer):

    group_name = ''
    headers = None

    async def connect(self):

        self.headers = get_headers(self.scope)
        self.token_key = get_auth_token(self.headers)

        self.user = await get_user_from_token(self.token_key)

        if not self.user or not self.user.is_authenticated:
            await self.close('User does not exist or has not been authenticated.')
            return

        self.group_name = f'dashboard_{self.user.username}'

        print(f'GROUP NAME - {self.group_name}')
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
    
        await self.accept()


        initial_data = await self.get_dashboard_data()


        await self.send(text_data=json.dumps(initial_data))

        pass



    async def disconnect(self, code):

        if self.group_name is None: 
            return 


        await self.channel_layer.group_discard( 
            self.group_name, 
            self.channel_name,
        )
        
        print(f'[DASHBOARD WEBSOCKET] - {self.group_name} disconected')
        pass 


    async def send_dashboard_data(self, event):
        await self.send(await self.get_dashboard_data())
        pass

    @database_sync_to_async
    def get_dashboard_data(self):
        from .models import Student
        
        student = Student.objects.filter(user=self.user)

        if student.exists():
            return self.get_student_dashboard_data()
        else:
            return self.get_admin_dashboard_data()

        pass



    def get_student_dashboard_data(self):

        from .models import (
            Student, LoanApplication, 
            Loan, AuditLog, ApplicationDocument)

        user_logs = AuditLog.objects.filter(user=self.user)
        logs_map_list = [user_log.toMap() for user_log in user_logs]

        #define response map here.
        response_map = {
            'audit_logs': logs_map_list
        }


        stats_map: dict = {}

        student = Student.objects.filter(user=self.user)

        loan_applications = LoanApplication.objects.filter(student=student).order_by('-created_at')

        stats_map['applications_count'] = loan_applications.count()

        if loan_applications.exists():
            application = loan_applications.first()
            response_map['current_application'] = application.toMap()
            pass 



        documents = ApplicationDocument.objects.filter(student=student)

        stats_map['total_documents'] = documents.count()

        loans = Loan.objects.filter(application__in=loan_applications).order_by('-created_at')

        stats_map['total_loans'] = loans.count()

        if loans.exists():
            loan = loans.first()
            response_map['current_loan'] = loan.toMap()
            pass 

        payments = Loan.objects.filter(loan__in=loans).order_by('-created_at')

        if payments.exists():
            pass

        response_map['dashboard_stat'] = stats_map
        return response_map

    def get_admin_dashboard_data(self):
        from  django.utils import timezone
        from django.db.models import Sum
        from . import models 


        total_students = models.Student.objects.count()

        if self.user.is_superuser:
            audit_logs = models.AuditLog.objects.all().order_by('-created_at')[:5]
        else: 
            audit_logs = models.AuditLog.objects.filter(actor=self.user).order_by('-created-at')[:5]

        
        logs_map = [audit_log.toMap() for audit_log in audit_logs]


        total_pending_applications = models.LoanApplication.objects.filter(status__in=['submitted', 'pending']).count()

        if not self.user.is_superuser:
            reviews = models.LoanReview.objects.filter(user=self.user).order_by('-created_at')
            applications = [review.application for review in reviews]
        else:
            applications = models.LoanApplication.objects.all().order_by('-created_at')[:5]


    
        #get the total loans which has loan_statuses for disbursed, active, completed for the current year.
        
        current_year = timezone.now().year


        total_approved_amounts = 0

        loans = models.Loan.objects.filter(loan_status__in=['disbursed', 'active', 'completed'], created_at__year=current_year)
        
        total_disbursed = loans.aggregate(total=Sum('approved_amount'))['total'] or 0

        total_active_loans = loans.filter(loan_status='active').count()

        loan_payments = models.LoanPayment.objects.filter(loan__in=loans, status__in=['completed'])

        total_paid = loan_payments.aggregate(total=Sum('amount'))['total'] or 0

        applications_map = [application.toMap() for application in applications]

        return {
            'dashboard_stats': {
                'total_students': total_students,
                'total_pedning_applications': total_pending_applications,
                'total_approved_amount': total_approved_amounts,  
                'total_paid': total_paid,
                'total_disbursed': total_disbursed,
                'total_active_loans': total_active_loans 
            },
            'audit_logs': logs_map, 
            'recent_applications': applications_map,
        }

    
    pass


    








#==============================UTITLITY FUNCTIONS WITH RESPECT TO WEB SOCKETS=============================

def get_headers(scope):
    return dict((k.decode(),v.decode()) for k,v in scope['headers'])

def get_auth_token(headers:dict):

    header_key = headers.get('authorization')

    if not header_key:
        return ''
    
    token_key = header_key.split(' ')[1]
    print('Token Key: ', token_key)
    return token_key


@database_sync_to_async
def get_user_from_token(key) -> User:

    from rest_framework.authtoken.models import Token

    token = Token.objects.filter(key=key)

    if not token.exists():
        return None 
    
    return token.first().user