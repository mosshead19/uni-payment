#!/usr/bin/env python
"""
Debug script to test form filtering on deployment
Run with: python debug_form_filtering.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projectsite.settings')
django.setup()

from paymentorg.models import Student, Officer, Organization, Course
from paymentorg.forms import PromoteStudentToOfficerForm, DemoteOfficerToStudentForm
from django.contrib.auth.models import User

print("\n" + "="*80)
print("DEBUGGING FORM FILTERING")
print("="*80)

# Test 1: Check if officers exist
print("\n[1] Checking for PROGRAM-level officers...")
program_officers = Officer.objects.filter(
    organization__hierarchy_level='PROGRAM',
    is_active=True
)
print(f"Found {program_officers.count()} PROGRAM-level officers")

if program_officers.exists():
    for officer in program_officers[:3]:  # Show first 3
        org = officer.organization
        print(f"\n  Officer: {officer.user.username}")
        print(f"  Organization: {org.name} (Level: {org.hierarchy_level})")
        print(f"  Program Affiliation: {org.program_affiliation}")

# Test 2: Check students in database
print("\n[2] Checking total students...")
all_students = Student.objects.filter(is_active=True)
non_promoted = Student.objects.filter(is_active=True).exclude(user__officer_profile__isnull=False)
print(f"Total active students: {all_students.count()}")
print(f"Non-promoted students: {non_promoted.count()}")

# Test 3: Test actual filtering with a program officer
print("\n[3] Testing filtering logic with sample PROGRAM officer...")
officer = program_officers.first()

if officer:
    org = officer.organization
    print(f"\nUsing: {officer.user.username} from {org.name}")
    
    # Simulate the view's filtering
    base_qs = Student.objects.filter(
        is_active=True
    ).exclude(
        user__officer_profile__isnull=False
    ).select_related('course', 'college').order_by('last_name', 'first_name').distinct()
    
    print(f"Base queryset (non-promoted): {base_qs.count()} students")
    
    if org.hierarchy_level == 'PROGRAM':
        filtered_qs = base_qs.filter(course__program_type=org.program_affiliation)
        print(f"After program_type filter ({org.program_affiliation}): {filtered_qs.count()} students")
        print(f"\nFiltered students:")
        for student in filtered_qs:
            course_type = student.course.program_type if student.course else "No course"
            print(f"  - {student.first_name} {student.last_name} | Course: {course_type}")
    else:
        print(f"Not a PROGRAM level org")

# Test 4: Test form initialization
print("\n[4] Testing form initialization...")

if officer:
    org = officer.organization
    
    # Simulate view behavior
    base_qs = Student.objects.filter(
        is_active=True
    ).exclude(
        user__officer_profile__isnull=False
    ).select_related('course', 'college').order_by('last_name', 'first_name').distinct()
    
    if org.hierarchy_level == 'PROGRAM':
        accessible_students = base_qs.filter(course__program_type=org.program_affiliation)
    else:
        accessible_students = base_qs
    
    accessible_orgs = Organization.objects.filter(id=org.id)
    
    print(f"Creating form with:")
    print(f"  student_queryset: {accessible_students.count()} students")
    print(f"  organization_queryset: {accessible_orgs.count()} orgs")
    
    # Create form
    form = PromoteStudentToOfficerForm(
        student_queryset=accessible_students,
        organization_queryset=accessible_orgs
    )
    
    # Check form fields
    student_field = form.fields['student']
    org_field = form.fields['organization']
    
    print(f"\nForm student field queryset:")
    print(f"  Count: {student_field.queryset.count()}")
    print(f"  SQL: {student_field.queryset.query}")
    
    print(f"\nForm organization field queryset:")
    print(f"  Count: {org_field.queryset.count()}")

# Test 5: Test COLLEGE-level officer
print("\n[5] Testing with COLLEGE-level officer...")
college_officers = Officer.objects.filter(
    organization__hierarchy_level='COLLEGE',
    is_active=True
)
print(f"Found {college_officers.count()} COLLEGE-level officers")

if college_officers.exists():
    college_officer = college_officers.first()
    org = college_officer.organization
    
    base_qs = Student.objects.filter(
        is_active=True
    ).exclude(
        user__officer_profile__isnull=False
    ).select_related('course', 'college').order_by('last_name', 'first_name').distinct()
    
    print(f"Using: {college_officer.user.username} from {org.name}")
    print(f"Base queryset (non-promoted): {base_qs.count()} students")
    print(f"For COLLEGE level, should show all: {base_qs.count()} students")

# Test 6: Test demote officer filtering
print("\n[6] Testing DemoteOfficerToStudentForm filtering...")
if officer:
    org = officer.organization
    
    # Simulate get_accessible_officers logic
    if org.hierarchy_level == 'PROGRAM':
        org_ids = [org.id]
    else:
        org_ids = org.get_accessible_organization_ids()
    
    accessible_officers_qs = Officer.objects.filter(
        is_active=True,
        organization_id__in=org_ids
    )
    
    print(f"Officer: {officer.user.username} in {org.name}")
    print(f"Org hierarchy level: {org.hierarchy_level}")
    print(f"Accessible org IDs: {org_ids}")
    print(f"Accessible officers: {accessible_officers_qs.count()}")
    
    form = DemoteOfficerToStudentForm(officer_queryset=accessible_officers_qs)
    officer_field = form.fields['officer']
    print(f"\nDemote form officer field queryset count: {officer_field.queryset.count()}")

print("\n" + "="*80)
print("DEBUG COMPLETE")
print("="*80 + "\n")
