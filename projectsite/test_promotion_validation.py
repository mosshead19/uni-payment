#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
django.setup()

from paymentorg.forms import PromoteStudentToOfficerForm
from paymentorg.models import Student, Organization

# Find a student with Officer record but is_officer=False
student = Student.objects.filter(user__user_profile__is_officer=False).exclude(
    user__officer_profile=None
).first()

if student:
    print(f"\nTesting student: {student.user.username} ({student.student_id_number})")
    print(f"  Has Officer record: {hasattr(student.user, 'officer_profile')}")
    print(f"  is_officer flag: {student.user.user_profile.is_officer}")
    
    # Get a valid organization
    org = Organization.objects.first()
    
    # Create form with this student
    form = PromoteStudentToOfficerForm(data={
        'student': student.id,
        'organization': org.id if org else 1,
        'role': 'Test Officer',
        'can_process_payments': True,
        'can_void_payments': False,
        'can_generate_reports': False,
        'can_promote_officers': False,
    })
    
    print(f"\nForm validation result: {form.is_valid()}")
    if not form.is_valid():
        print("Form errors:")
        for field, errors in form.errors.items():
            print(f"  {field}: {errors}")
    else:
        print("✓ Student can be promoted!")
else:
    print("No students found with Officer record but is_officer=False")
