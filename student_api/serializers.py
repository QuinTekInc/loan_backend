
from django.db.transaction import atomic
from rest_framework import serializers
from core.models import *

class LoanApplicationSerializer(serializers.Serializer):

    # Loan information
    amount_requested = serializers.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    loan_reason = serializers.CharField()

    # Personal information
    first_names = serializers.CharField()
    surname = serializers.CharField()
    gender = serializers.CharField()
    nationality = serializers.CharField()
    phone_number = serializers.CharField()
    email = serializers.EmailField()
    ghana_card_number = serializers.CharField()

    # Guardian information
    guardian_name = serializers.CharField(required=False, allow_blank=True)
    guardian_relationship = serializers.CharField(required=False, allow_blank=True)
    guardian_phone_number = serializers.CharField(required=False, allow_blank=True)

    # Academic information
    reference_number = serializers.CharField()
    index_number = serializers.CharField()
    program = serializers.CharField()
    level = serializers.CharField()
    department = serializers.CharField()


    # Documents
    ghana_card = serializers.FileField()
    student_id = serializers.FileField()
    admission_letter = serializers.FileField()
    passport_photo = serializers.ImageField()

    def create(self, validated_data):

        request = self.context['request']
        user = request.user
        student = Student.objects.get(user=user)

        # Extract uploaded files
        ghana_card = validated_data.pop('ghana_card')
        student_id = validated_data.pop('student_id')
        admission_letter = validated_data.pop('admission_letter')
        passport_photo = validated_data.pop('passport_photo')

        with atomic():

            
            # Create application object if the application id is None.
            application = LoanApplication.objects.create(
                student=student,
                amount_requested=validated_data['amount_requested']
            )

            # Create application info
            StudentApplicationInfo.objects.create(
                application=application,

                first_names=validated_data['first_names'],
                surname=validated_data['surname'],
                gender = validated_data.get('gender', ''),
                nationality=validated_data.get('nationality', ''),
                phone_number=validated_data['phone_number'],
                email=validated_data['email'],
                ghana_card_number=validated_data['ghana_card_number'],

                guardian_name=validated_data.get('guardian_name'),
                guardian_relationship=validated_data.get('guardian_relationship'),
                guardian_phone_number=validated_data.get('guardian_phone_number'),

                reference_number=validated_data['reference_number'],
                index_number=validated_data['index_number'],
                program=validated_data['program'],
                level=validated_data['level'],
                department=validated_data['department']
            )

            # Save documents
            documents = {
                'ghana_card': ghana_card,
                'student_id': student_id,
                'admission_letter': admission_letter,
                'passport_photo': passport_photo
            }

            for document_type, file in documents.items():

                ApplicationDocument.objects.create(
                    application=application,
                    student=student,
                    document_type=document_type,
                    file=file
                )

            #create a loan review object for the application
            LoanReview.objects.create(application=application)

        return application
    


    def update(self, instance: LoanApplication, validated_data):

        instance.amount_requested = validated_data.get('amount_requested', instance.amount_requested)
        instance.loan_reason = validated_data.get('loan_reason', instance.loan_reason)

        instance.save()

        #get the loan application info
        info = StudentApplicationInfo.objects.get(loan_application=instance)

        info.surname = validated_data.get('surname', info.surname)
        info.first_names = validated_data.get('first_names', info.first_names)
        info.gender = validated_data.get('gender', info.gender)
        info.nationality = validated_data.get('nationality', info.nationality)
        info.email = validated_data.get('email', info.email)
        info.ghana_card_number = validated_data.get('ghana_card_number', self.ghana_card_number)
        
        info.guardian_name = validated_data.get('guardian_name', info.guardian_name)
        info.guardian_relationsip = validated_data.get('guardian_relationsip', info.guardian_relationship)
        info.guardian_phone_number = validated_data.get('guardian_phone_number', info.guardian_phone_number)


        info.reference_number = validated_data.get('reference_number', info.reference_number)
        info.index_number = validated_data.get('index_number', info.index_number)
        info.level = validated_data.get('level', info.level)
        info.department = validated_data.get('department', info.department)
        info.program = validated_data.get('program', info.program)

        info.save()

        document_fields = [
            'passport_photo',
            'ghana_card',
            'admission_letter',
            'student_id'
        ]

        for field in document_fields:

            uploaded_file = validated_data.get(field)

            if uploaded_file:

                document = ApplicationDocument.objects.filter(
                    application=instance,
                    document_type=field
                ).first()

                if document:
                    # optionally delete old file
                    document.file.delete(save=False)

                    document.file = uploaded_file
                    document.save()

                else:

                    ApplicationDocument.objects.create(
                        application=instance,
                        student=instance.student,
                        document_type=field,
                        file=uploaded_file
                    )

        
        return instance