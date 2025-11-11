from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from paymentorg.models import (
    AcademicYearConfig,
    Organization,
    FeeType,
    Student,
    Officer,
)


class Command(BaseCommand):
    help = "Create initial demo data: AcademicYearConfig, Organizations, FeeTypes, Student and Officer users"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding initial demo data..."))

        # 1) Academic year config (current)
        academic_year = "2024-2025"
        semester = "1st Semester"
        start_date = date(timezone.now().year, 8, 1)
        end_date = start_date + timedelta(days=300)

        ayc, _ = AcademicYearConfig.objects.get_or_create(
            academic_year=academic_year,
            semester=semester,
            defaults={
                "start_date": start_date,
                "end_date": end_date,
                "is_current": True,
            },
        )
        # ensure it's current
        if not ayc.is_current:
            ayc.is_current = True
            ayc.save()
        self.stdout.write(self.style.SUCCESS(f"- AcademicYearConfig: {ayc} (is_current={ayc.is_current})"))

        # 2) Organizations
        cos, _ = Organization.objects.get_or_create(
            code="COS",
            defaults={
                "name": "College of Sciences Organization",
                "department": "College of Sciences",
                "description": "Student org for the College of Sciences",
                "contact_email": "cos@example.com",
                "contact_phone": "09170000001",
                "booth_location": "Ground Floor, Main Building",
            },
        )
        spect, _ = Organization.objects.get_or_create(
            code="SPECTRUM",
            defaults={
                "name": "SPECTRUM Publication",
                "department": "College of Sciences",
                "description": "Official publication of the college",
                "contact_email": "spectrum@example.com",
                "contact_phone": "09170000002",
                "booth_location": "2F, Student Center",
            },
        )
        self.stdout.write(self.style.SUCCESS(f"- Organizations: {cos.code}, {spect.code}"))

        # 3) Fee types
        pub_fee, _ = FeeType.objects.get_or_create(
            organization=spect,
            name="Publication Fee",
            academic_year=academic_year,
            semester=semester,
            defaults={
                "amount": Decimal("150.00"),
                "description": "Semester publication fee",
                "applicable_year_levels": "All",
            },
        )
        college_fee, _ = FeeType.objects.get_or_create(
            organization=cos,
            name="College Fee",
            academic_year=academic_year,
            semester=semester,
            defaults={
                "amount": Decimal("300.00"),
                "description": "General college fee",
                "applicable_year_levels": "All",
            },
        )
        self.stdout.write(self.style.SUCCESS(f"- FeeTypes: {pub_fee.name} ({spect.code}), {college_fee.name} ({cos.code})"))

        # 4) Users: student and officer
        # Student user
        student_username = "student1"
        student_email = "student1@example.com"
        student_password = "Pass1234!"
        student_user, created_student_user = User.objects.get_or_create(
            username=student_username,
            defaults={"email": student_email},
        )
        if created_student_user:
            student_user.set_password(student_password)
            student_user.save()
        # Student profile
        student_profile, _ = Student.objects.get_or_create(
            user=student_user,
            defaults={
                "student_id_number": "2024-00001",
                "first_name": "Alex",
                "last_name": "Rivera",
                "middle_name": "T",
                "course": "BS Biology",
                "year_level": 2,
                "college": "College of Sciences",
                "email": student_email,
                "phone_number": "09171234567",
                "academic_year": academic_year,
                "semester": semester,
            },
        )

        # Officer user
        officer_username = "officer1"
        officer_email = "officer1@example.com"
        officer_password = "Pass1234!"
        officer_user, created_officer_user = User.objects.get_or_create(
            username=officer_username,
            defaults={"email": officer_email, "is_staff": True},
        )
        if created_officer_user:
            officer_user.set_password(officer_password)
            officer_user.save()
        # Officer profile
        officer_profile, _ = Officer.objects.get_or_create(
            user=officer_user,
            defaults={
                "employee_id": "EMP-001",
                "first_name": "Jamie",
                "last_name": "Lopez",
                "organization": cos,
                "role": "Treasurer",
                "can_process_payments": True,
                "can_void_payments": True,
                "can_generate_reports": True,
                "email": officer_email,
                "phone_number": "09179876543",
            },
        )

        self.stdout.write(self.style.SUCCESS(f"- Users: student '{student_username}', officer '{officer_username}'"))
        self.stdout.write(self.style.HTTP_INFO("Login credentials (dev only):"))
        self.stdout.write(self.style.HTTP_INFO(f"  Student -> {student_username} / {student_password}"))
        self.stdout.write(self.style.HTTP_INFO(f"  Officer -> {officer_username} / {officer_password}"))

        self.stdout.write(self.style.SUCCESS("Initial demo data created/ensured.")) 

