
from django.db import models
from django.contrib.auth.models import User
import django.utils.timezone
import uuid

from django.core.validators import RegexValidator


ghana_card_validator = RegexValidator(
    regex=r"^GHA-\d{9}-\d$",
    message="Invalid Ghana Card format (Expected: GHA-XXXXXXXXX-X)",
    inverse_match=False
)


index_number_validator = RegexValidator( 
    regex=r'UEB\d{7}',
    message="Invalid Index Number format (Expected: UEBXXXXXXX)",
    inverse_match=False
)


reference_number_validator = RegexValidator( 
    regex=r'UA\d{7}',
    message="Invalid Reference Number format (Expected: UEBXXXXXXX)",
    inverse_match=False
)


# Create your models here.


class Issuer(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4)
    user = models.OneToOneField(User, on_delete=models.CASCADE)


class Student(models.Model):

    GENDER_CHOICES = (
        ("male", "Male"),
        ("female", "Female")
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True,)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    gender = models.CharField(max_length=10, blank=False, null=False, choices=GENDER_CHOICES, default='male')
    phone_number = models.TextField(max_length=30, null=False, blank=False) #the user's phone number field should not be empty.
    ghana_card_number = models.TextField(max_length=40, unique=True, blank=False, null=False, validators=[ghana_card_validator])
    profile_picture = models.FileField(null=True, upload_to='media/profile_pictures/', blank=True)
    # reference_number = models.CharField(max_length=15, null=False, blank=False, unique=True, validators=[reference_number_validator])
    # index_number = models.CharField(max_length=15, blank=False, null=False, unique=True, validators=[index_number_validator])


    def __repr__(self):
        return (self.id, self.user.username)
    
    def __str__(self):
        return str(self.__repr__())


    def toMap(self):
        return {
            'id': str(self.id),
            'name': f'{self.user.last_name} {self.user.first_name}',
            'email': self.user.email,
            'ghana_card_number': self.ghana_card_number, 
            'phone_number': self.phone_number,   
            'gender': self.gender,       
        }


#for sending the verification either to phone or email.
#if accounts are succesfully verified, 
#their corresponding verification object is deleted from this table
class AccountVerification(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, null=False, blank=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=False)
    code = models.CharField(max_length=10, blank=False, null=False)
    
    def __repr__(self):
        return self.id, self.user.username
    
    def __str__(self):
        return self.__repr__()




class LoanApplication(models.Model):

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", 'Cancelled'), #this status is for when a student cancels the application after it has been submitted.
    ]   


    APPLICATION_STEPS = [
        ("personal", "Personal Information"),
        ("academic", "Academic Information"),
        ("loan", "Loan Details"),
        ("documents", "Documents Upload"),
        ("review", "Review"),
        ("submitted", "Submitted"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="loan_applications")
    loan_reason = models.TextField(blank=True, null=True)
    amount_requested = models.FloatField(default=0)
    status = models.CharField(default="submitted", max_length=50, choices=STATUS_CHOICES) #SUBMITTED, UNDER_REVIEW, ACCEPTED, REJECTED
    current_step = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def toMap(self):
        return {
            'id': str(self.id),
            'amount_requested': self.amount_requested, 
            'loan_reason': self.loan_reason,
            'status': self.status,
            'current_step': self.current_step,
            'created_at': self.created_at, 
            'updated_at': self.updated_at,
        }


class StudentApplicationInfo(models.Model):

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female')
    ]

    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, null=False)
    loan_application = models.ForeignKey(LoanApplication, on_delete=models.CASCADE, related_name='application_information')

    #the student's personal information
    first_names = models.CharField(max_length=255, blank=False, null=False)
    surname = models.CharField(max_length=255, blank=False, null=False)
    gender = models.CharField(max_length=10, blank=True, choices=GENDER_CHOICES)
    phone_number = models.CharField(max_length=255, blank=False, null=False)
    email = models.EmailField(blank=True, null=False)
    ghana_card_number = models.CharField(max_length=50, null=False, blank=False, validators=[ghana_card_validator])
    nationality = models.CharField(max_length=100, blank=True)


    #parental_information
    guardian_name = models.CharField(max_length=255, blank=True)
    guardian_relationship = models.CharField(max_length=50, blank=True)
    guardian_phone_number = models.CharField(max_length=50, blank=True)

    #academic information
    reference_number = models.CharField(max_length=20, unique=True, blank=False, null=False, validators=[reference_number_validator])
    index_number = models.CharField(max_length=20, blank=False, null=False, validators=[index_number_validator])
    program = models.CharField(max_length=255, blank=False, null=False)
    level = models.CharField(max_length=10, blank=False)
    department = models.CharField(max_length=255, blank=False, null=False)


    def toMap(self):
        return {
            'id': str(self.id),
            'application_id': self.loan_application.id, 
            'first_names': self.first_names, 
            'surname': self.surname, 
            'gender': self.gender,
            'phone_number': self.phone_number, 
            'email': self.email,
            'ghana_card_number': self.ghana_card_number, 
            'nationality': self.nationality,

            'guardian_name': self.guardian_name, 
            'guardian_relationship': self.guardian_relationship, 
            'guardian_phone_number': self.guardian_phone_number,

            'reference_number': self.reference_number, 
            'index_number': self.index_number, 
            'level': self.level,
            'program': self.program, 
            'department': self.department
        }



class ApplicationDocument(models.Model):

    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('approved', 'Approved'),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(primary_key =True, default=uuid.uuid4, blank=False, null=False, unique=True)
    loan_application = models.ForeignKey(LoanApplication, related_name='documents', on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=255, blank=True)
    file = models.FileField(null=True, upload_to='loan_documents/')
    status = models.TextField(max_length=255, blank=True, null=False, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    def toMap(self):
        return  {
            'id': str(self.id),
            'application_id': str(self.loan_application.id), 
            'student_id': str(self.student_id),
            'document_type': self.document_type,
            'file_url': self.file.url,
            'status': self.status, 
            'created_at': self.created_at, 
            'updated_at': self.updated_at,
        }

    



class Loan(models.Model):

    LOAN_STATUS_CHOICES = [
        ('awaiting_disbursement', 'Awaiting Disbursement'),
        ('cancelled', 'Cancelled'),
        ("disbursed", "Funds Disbursed"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed')
    ]


    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4)
    application = models.ForeignKey(LoanApplication, on_delete=models.CASCADE, related_name='loan')
    issuer = models.ForeignKey(Issuer, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='loan')
    approved_amount = models.FloatField(default=0)
    interest_rate = models.FloatField(default=0)
    duration = models.IntegerField(default=0)
    loan_status = models.CharField(max_length=50, blank=True, choices=LOAN_STATUS_CHOICES)
    payment_status = models.CharField(max_length=50, blank=True, choices=PAYMENT_STATUS_CHOICES)
    start_date = models.DateTimeField(null=True)
    end_date = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def toMap(self):
        return {
            'id': str(self.id),
            'application_id': str(self.application.id),
            'student_id': str(self.student.id),
            'approved_amount': self.approved_amount, 
            'interest_rate': self.interest_rate, 
            'duration': self.duration, 
            'loan_status': self.loan_status,
            'payment_status': self.payment_status,
            'start_date': self.start_date, 
            'end_date': self.end_date, 
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


class LoanPayment(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="loan_payments")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='student_payments')
    amount = models.FloatField(default=0) #this is the amount paid by the student
    payment_method = models.TextField(max_length=50)
    status = models.CharField(blank=True, null=False, max_length=255) #whether the payment is pending, failed, or confirmed.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def toMap(self):
        return {
            'id': str(self.id),
            'loan_id': str(self.loan.id),
            'student_id': str(self.student.id),
            'amount': self.amount, 
            'payment_method': self.payment_method, 
            'status': self.status, 
            'created_at': self.created_at, 
            'updated_at': self.updated_at
        }




class Notification(models.Model):

    TYPE_CHOICES = [
        ('success', 'Success'),
        ('info', 'Info'),
        ('reminder', 'Reminder'), 
        ('warning', 'Warning')
    ]

    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=300, blank=True)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now=True)


    def toMap(self):
        return {
            'id': str(self.id),
            'title': self.title, 
            'message': self.message,
            'type': self.notification_type, 
            'is_read': self.is_read, 
            'created_at': self.created_at
        }


# ============ LOAN APPROVAL WORKFLOW MODELS (SIMPLIFIED) ============

class LoanReview(models.Model):
    """Simple loan application review and approval workflow"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4)
    application = models.OneToOneField(LoanApplication, on_delete=models.CASCADE, related_name='review')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='loan_reviews')
    comments = models.TextField(blank=True)
    approved_amount = models.FloatField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.application.id} - {self.status}"

    def toMap(self):
        return {
            'id': str(self.id),
            'application_id': str(self.application.id),
            'status': self.status,
            'reviewed_by': self.reviewed_by.username if self.reviewed_by else None,
            'comments': self.comments,
            'approved_amount': self.approved_amount,
            'rejection_reason': self.rejection_reason,
            'reviewed_at': self.reviewed_at,
        }
