from datetime import timedelta
import hashlib
import hmac
from decimal import Decimal
from random import choice, randint

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from paymentorg.models import (
    AcademicYearConfig,
    ActivityLog,
    College,
    Course,
    FeeType,
    Organization,
    Officer,
    Payment,
    PaymentRequest,
    Student,
    UserProfile,
)


class Command(BaseCommand):
    help = "Create fake development data for UniPay (organizations, officers, students, fees, requests)."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=10, help="Number of students to create (default: 10)")
        parser.add_argument("--orgs", type=int, default=7, help="Number of organizations to create (default: 7 - includes 5 Tier 1 + 2 Tier 2)")
        parser.add_argument("--fees", type=int, default=3, help="Fee types per org (default: 3)")
        parser.add_argument("--requests", type=int, default=1, help="Payment requests per student (default: 1)")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear previously generated fake data before creating new records.",
        )

    def handle(self, *args, **options):
        if options.get("reset"):
            self._clear_existing_data()

        num_students = options["students"]
        num_orgs = options["orgs"]
        fees_per_org = options["fees"]
        requests_per_student = options["requests"]

        self._ensure_academic_period()

        self.stdout.write(self.style.MIGRATE_HEADING("Creating organizations"))
        requested_orgs = [
            ("BIO", "Bachelor of Science in Biology", "TIER_1", "MEDICAL_BIOLOGY"),
            ("MBIO", "Bachelor of Science in Marine Biology", "TIER_1", "MARINE_BIOLOGY"),
            ("BSCS", "Bachelor of Science in Computer Science", "TIER_1", "COMPUTER_SCIENCE"),
            ("BSES", "Bachelor of Science in Environmental Science", "TIER_1", "ENVIRONMENTAL_SCIENCE"),
            ("BSIT", "Bachelor of Science in Information Technology", "TIER_1", "INFORMATION_TECHNOLOGY"),
            ("CSG", "College Student Government", "TIER_2", "ALL"),
            ("COMPENDIUM", "Compendium", "TIER_2", "ALL"),
        ]
        # ensure we don't slice beyond available data
        selected_orgs = requested_orgs[: max(1, min(num_orgs, len(requested_orgs)))]

        organizations = []
        for code, name, tier, program in selected_orgs:
            org, _ = Organization.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "department": name,
                    "fee_tier": tier,
                    "program_affiliation": program,
                    "description": "Seeded organization",
                    "contact_email": f"{code.lower()}@example.com",
                    "contact_phone": "0917-000-0000",
                    "booth_location": "Main Building",
                },
            )
            updated_fields = []
            if org.fee_tier != tier:
                org.fee_tier = tier
                updated_fields.append("fee_tier")
            if org.program_affiliation != program:
                org.program_affiliation = program
                updated_fields.append("program_affiliation")
            if updated_fields:
                org.save(update_fields=updated_fields)
            organizations.append(org)
        self.stdout.write(self.style.SUCCESS(f"Organizations: {len(organizations)}"))

        self.stdout.write(self.style.MIGRATE_HEADING("Creating colleges/departments"))
        # System is focused on College of Sciences only
        college, _ = College.objects.get_or_create(
            code="COS",
            defaults={
                "name": "College of Sciences",
                "description": "College of Sciences - Primary focus of the system",
            },
        )
        colleges = [college]
        self.stdout.write(self.style.SUCCESS(f"College: {college.name}"))

        self.stdout.write(self.style.MIGRATE_HEADING("Creating courses/programs"))
        # Only the 5 specified programs for College of Sciences
        courses_data = [
            ("Bachelor of Science in Biology", "BSBIO", "MEDICAL_BIOLOGY", college),
            ("Bachelor of Science in Marine Biology", "BSMBIO", "MARINE_BIOLOGY", college),
            ("Bachelor of Science in Computer Science", "BSCS", "COMPUTER_SCIENCE", college),
            ("Bachelor of Science in Environmental Science", "BSES", "ENVIRONMENTAL_SCIENCE", college),
            ("Bachelor of Science in Information Technology", "BSIT", "INFORMATION_TECHNOLOGY", college),
        ]
        courses = []
        for name, code, program_type, college in courses_data:
            course, created = Course.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "college": college,
                    "description": f"Seeded {name}",
                    "program_type": program_type,
                },
            )
            if not created:
                fields_to_update = []
                if course.name != name:
                    course.name = name
                    fields_to_update.append("name")
                if course.college != college:
                    course.college = college
                    fields_to_update.append("college")
                if course.program_type != program_type:
                    course.program_type = program_type
                    fields_to_update.append("program_type")
                if fields_to_update:
                    course.save(update_fields=fields_to_update)
            courses.append(course)
        self.stdout.write(self.style.SUCCESS(f"Courses: {len(courses)}"))

        self.stdout.write(self.style.MIGRATE_HEADING("Creating officers (staff users)"))
        for org in organizations:
            username = f"officer_{org.code.lower()}"
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "first_name": "Org",
                    "last_name": org.code,
                    "is_staff": True,
                },
            )
            user.set_password("admin123")
            user.save()
            UserProfile.objects.update_or_create(user=user, defaults={"is_officer": True})
            Officer.objects.get_or_create(
                user=user,
                defaults={
                    "employee_id": f"EMP-{org.code}",
                    "first_name": "Org",
                    "last_name": org.code,
                    "email": user.email,
                    "phone_number": "0917-123-4567",
                    "organization": org,
                    "role": "Treasurer",
                    "can_process_payments": True,
                },
            )
        self.stdout.write(self.style.SUCCESS("Officers created."))

        self.stdout.write(self.style.MIGRATE_HEADING("Creating superusers (for testing)"))
        if organizations:
            su_officer, created = User.objects.get_or_create(
                username="superofficer",
                defaults={
                    "email": "superofficer@example.com",
                    "first_name": "Super",
                    "last_name": "Officer",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            if created:
                su_officer.set_password("admin123")
                su_officer.save()
            UserProfile.objects.update_or_create(user=su_officer, defaults={"is_officer": True})
            Officer.objects.get_or_create(
                user=su_officer,
                defaults={
                    "employee_id": "EMP-SUPER",
                    "first_name": "Super",
                    "last_name": "Officer",
                    "email": su_officer.email,
                    "phone_number": "0917-111-1111",
                    "organization": organizations[0],
                    "role": "Administrator",
                    "can_process_payments": True,
                    "can_void_payments": True,
                    "can_generate_reports": True,
                },
            )

        su_student, created = User.objects.get_or_create(
            username="superstudent",
            defaults={
                "email": "superstudent@example.com",
                "first_name": "Super",
                "last_name": "Student",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            su_student.set_password("admin123")
            su_student.save()
        UserProfile.objects.update_or_create(user=su_student, defaults={"is_officer": False})
        default_course = courses[0] if courses else None
        default_college = default_course.college if default_course else college
        if default_course and default_college:
            Student.objects.get_or_create(
                user=su_student,
                defaults={
                    "student_id_number": "2025-ADMIN",
                    "first_name": su_student.first_name,
                    "last_name": su_student.last_name,
                    "middle_name": "X",
                    "email": su_student.email,
                    "phone_number": "0917-222-2222",
                    "course": default_course,
                    "year_level": 4,
                    "college": default_college,
                    "academic_year": "2024-2025",
                    "semester": "1st Semester",
                },
            )
        self.stdout.write(self.style.SUCCESS("Superusers ensured (user/pass: superofficer admin123, superstudent admin123)."))

        self.stdout.write(self.style.MIGRATE_HEADING("Creating fee types"))
        fee_types = []
        for org in organizations:
            for i in range(fees_per_org):
                fee, _ = FeeType.objects.get_or_create(
                    organization=org,
                    name=f"{org.code} Fee {i+1}",
                    academic_year="2024-2025",
                    semester="1st Semester",
                    defaults={
                        "amount": Decimal(str(100 + 50 * (i + 1))),
                        "description": "Sample fee",
                        "applicable_year_levels": "All",
                    },
                )
                fee_types.append(fee)
        self.stdout.write(self.style.SUCCESS(f"Fee types: {len(fee_types)}"))

        self.stdout.write(self.style.MIGRATE_HEADING("Creating students"))
        students = []
        for i in range(num_students):
            username = f"student{i+1:03d}"
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "first_name": f"Student{i+1}",
                    "last_name": "Test",
                },
            )
            user.set_password("password123")
            user.save()
            UserProfile.objects.update_or_create(user=user, defaults={"is_officer": False})
            selected_course = choice(courses) if courses else None
            selected_college = selected_course.college if selected_course else college
            if selected_course and selected_college:
                student, _ = Student.objects.get_or_create(
                    user=user,
                    defaults={
                        "student_id_number": f"2025-{10000+i}",
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "middle_name": "A",
                        "email": user.email,
                        "phone_number": "0917-000-0000",
                        "course": selected_course,
                        "year_level": randint(1, 4),
                        "college": selected_college,
                        "academic_year": "2024-2025",
                        "semester": "1st Semester",
                    },
                )
                students.append(student)
        self.stdout.write(self.style.SUCCESS(f"Students: {len(students)}"))

        self.stdout.write(self.style.MIGRATE_HEADING("Creating payment requests"))
        request_count = 0
        for student in students:
            for _ in range(requests_per_student):
                fee = choice(fee_types)
                pr, created = PaymentRequest.objects.get_or_create(
                    student=student,
                    organization=fee.organization,
                    fee_type=fee,
                    amount=fee.amount,
                    defaults={
                        "payment_method": "CASH",
                        "status": "PENDING",
                        "qr_signature": "",
                        "expires_at": timezone.now() + timedelta(minutes=30),
                    },
                )
                if created:
                    request_count += 1
                if not pr.qr_signature:
                    secret = getattr(settings, "SECRET_KEY", "default-insecure-key").encode("utf-8")
                    message = str(pr.request_id).encode("utf-8")
                    pr.qr_signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
                    pr.save(update_fields=["qr_signature"])
        self.stdout.write(self.style.SUCCESS(f"Payment requests created: {request_count}"))

        self.stdout.write(self.style.SUCCESS("Fake data generation complete."))

    def _ensure_academic_period(self):
        current_year = "2024-2025"
        semester = "1st Semester"
        config, created = AcademicYearConfig.objects.get_or_create(
            academic_year=current_year,
            semester=semester,
            defaults={
                "start_date": timezone.now().date(),
                "end_date": timezone.now().date() + timedelta(days=120),
                "is_current": True,
            },
        )
        if not created and not config.is_current:
            AcademicYearConfig.objects.filter(is_current=True).exclude(pk=config.pk).update(is_current=False)
            config.is_current = True
            config.save(update_fields=["is_current"])

    def _clear_existing_data(self):
        self.stdout.write(self.style.WARNING("Reset flag detected – clearing previously generated fake data."))

        org_codes = {"BIO", "MBIO", "BSCS", "BSES", "BSIT", "CSG", "COMPENDIUM"}
        student_prefix = "student"
        officer_prefix = "officer_"
        special_usernames = {"superofficer", "superstudent"}

        # Remove dependent records (order matters due to FK constraints)
        # First, delete activity logs that reference payments/payment requests
        ActivityLog.objects.filter(payment__organization__code__in=org_codes).delete()
        ActivityLog.objects.filter(payment_request__organization__code__in=org_codes).delete()
        
        # Delete payments and payment requests
        Payment.objects.filter(organization__code__in=org_codes).delete()
        PaymentRequest.objects.filter(organization__code__in=org_codes).delete()
        
        # Delete fee types
        FeeType.objects.filter(organization__code__in=org_codes).delete()

        # Delete students BEFORE courses (courses have PROTECT constraint)
        seeded_students = Student.objects.filter(user__username__startswith=student_prefix)
        student_user_ids = list(seeded_students.values_list("user_id", flat=True))
        seeded_students.delete()
        UserProfile.objects.filter(user_id__in=student_user_ids).delete()
        User.objects.filter(id__in=student_user_ids).delete()

        # Delete officers (including super users)
        officer_users = User.objects.filter(username__startswith=officer_prefix) | User.objects.filter(
            username__in=special_usernames
        )
        officer_user_ids = list(officer_users.values_list("id", flat=True))
        Officer.objects.filter(user_id__in=officer_user_ids).delete()
        UserProfile.objects.filter(user_id__in=officer_user_ids).delete()
        officer_users.delete()

        # Remove organizations
        Organization.objects.filter(code__in=org_codes).delete()

        # Delete courses AFTER students (students reference courses with PROTECT)
        # Only delete courses that aren't referenced by any remaining students
        # Only the 5 specified programs
        course_codes = {
            "BSBIO",
            "BSMBIO",
            "BSCS",
            "BSES",
            "BSIT",
        }
        # Get courses that have no students referencing them
        # Exclude courses that are referenced by any students
        courses_with_students = Student.objects.values_list('course_id', flat=True).distinct()
        courses_to_delete = Course.objects.filter(code__in=course_codes).exclude(
            id__in=courses_with_students
        )
        deleted_count = courses_to_delete.count()
        courses_to_delete.delete()
        remaining = Course.objects.filter(code__in=course_codes).count()
        if remaining > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not delete {remaining} course(s) - they are still referenced by students."
                )
            )

        # Delete colleges AFTER courses (courses reference colleges)
        # Only College of Sciences
        College.objects.filter(code="COS").delete()

        self.stdout.write(self.style.SUCCESS("Previous fake data cleared."))
