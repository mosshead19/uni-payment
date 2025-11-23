"""
Django management command to create promotion authority officers
Usage: python manage.py create_promotion_officers
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from paymentorg.models import Officer, Organization, UserProfile
import sys

class Command(BaseCommand):
    help = 'Create promotion authority officers for organization hierarchy testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-update-affiliations',
            action='store_true',
            help='Skip updating organization affiliations after creation'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('CREATING PROMOTION AUTHORITY OFFICERS'))
        self.stdout.write(self.style.SUCCESS('='*80))

        # Define organizations and their officer credentials
        organizations_config = [
            {
                'org_name': 'ALL Organizations Admin',
                'org_code': 'ALLORG',
                'org_level': 'COLLEGE',
                'username': 'all_org_officer',
                'password': 'AllOrg@123',
                'first_name': 'All',
                'last_name': 'Organizations',
                'employee_id': 'ALL_001',
                'role': 'College Administrator',
                'description': 'Can promote/demote in ALL organizations',
                'program_affiliation': 'ALL'
            },
            {
                'org_name': 'Medical Biology',
                'org_code': 'MEDBIO',
                'org_level': 'PROGRAM',
                'parent_org_code': 'ALLORG',
                'username': 'medbio_officer',
                'password': 'MedBio@123',
                'first_name': 'MedBio',
                'last_name': 'Officer',
                'employee_id': 'MEDBIO_001',
                'role': 'Program Head',
                'description': 'Can promote/demote in Medical Biology only',
                'program_affiliation': 'MEDICAL_BIOLOGY'
            },
            {
                'org_name': 'Marine Biology',
                'org_code': 'MARINEBIO',
                'org_level': 'PROGRAM',
                'parent_org_code': 'ALLORG',
                'username': 'marinebio_officer',
                'password': 'MarineBio@123',
                'first_name': 'MarineBio',
                'last_name': 'Officer',
                'employee_id': 'MARINEBIO_001',
                'role': 'Program Head',
                'description': 'Can promote/demote in Marine Biology only',
                'program_affiliation': 'MARINE_BIOLOGY'
            },
            {
                'org_name': 'Information Technology',
                'org_code': 'IT',
                'org_level': 'PROGRAM',
                'parent_org_code': 'ALLORG',
                'username': 'it_officer',
                'password': 'IT@123',
                'first_name': 'IT',
                'last_name': 'Officer',
                'employee_id': 'IT_001',
                'role': 'Program Head',
                'description': 'Can promote/demote in Information Technology only',
                'program_affiliation': 'INFORMATION_TECHNOLOGY'
            },
            {
                'org_name': 'Computer Science',
                'org_code': 'COMSCI',
                'org_level': 'PROGRAM',
                'parent_org_code': 'ALLORG',
                'username': 'comsci_officer',
                'password': 'ComSci@123',
                'first_name': 'ComSci',
                'last_name': 'Officer',
                'employee_id': 'COMSCI_001',
                'role': 'Program Head',
                'description': 'Can promote/demote in Computer Science only',
                'program_affiliation': 'COMPUTER_SCIENCE'
            }
        ]

        parent_org = None
        accounts = []

        for config in organizations_config:
            self.stdout.write(self.style.HTTP_INFO(f'\n{"="*80}'))
            self.stdout.write(self.style.HTTP_INFO(f'Creating: {config["org_name"]}'))
            self.stdout.write(self.style.HTTP_INFO(f'{"="*80}'))

            # Get or create parent organization first
            if config['org_level'] == 'COLLEGE':
                org, created = Organization.objects.get_or_create(
                    code=config['org_code'],
                    defaults={
                        'name': config['org_name'],
                        'hierarchy_level': config['org_level'],
                        'department': 'Promotion Authority',
                        'fee_tier': 'TIER_1',
                        'program_affiliation': config['program_affiliation'],
                        'contact_email': f"{config['org_code'].lower()}@unipay.local",
                        'contact_phone': '555-0000',
                        'booth_location': 'Main Office'
                    }
                )
                parent_org = org
                status = "created" if created else "already exists"
                self.stdout.write(self.style.SUCCESS(f'✓ Organization {status}: {org.name}'))
            else:
                # Get parent organization
                try:
                    parent = Organization.objects.get(code=config.get('parent_org_code'))
                except Organization.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'ERROR: Parent organization {config.get("parent_org_code")} not found!'))
                    continue

                org, created = Organization.objects.get_or_create(
                    code=config['org_code'],
                    defaults={
                        'name': config['org_name'],
                        'hierarchy_level': config['org_level'],
                        'parent_organization': parent,
                        'department': 'Promotion Authority',
                        'fee_tier': 'TIER_1',
                        'program_affiliation': config['program_affiliation'],
                        'contact_email': f"{config['org_code'].lower()}@unipay.local",
                        'contact_phone': '555-0000',
                        'booth_location': f'{config["org_name"]} Office'
                    }
                )
                status = "created" if created else "already exists"
                self.stdout.write(self.style.SUCCESS(f'✓ Organization {status}: {org.name}'))
                self.stdout.write(self.style.SUCCESS(f'  Parent: {parent.name}'))

            # Create or update user
            user, user_created = User.objects.get_or_create(
                username=config['username'],
                defaults={
                    'email': f"{config['username']}@unipay.local",
                    'first_name': config['first_name'],
                    'last_name': config['last_name']
                }
            )
            user.set_password(config['password'])
            user.save()
            status = "created" if user_created else "updated"
            self.stdout.write(self.style.SUCCESS(f'✓ User {status}: {user.username}'))

            # Create or update officer
            officer, officer_created = Officer.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': config['employee_id'],
                    'first_name': config['first_name'],
                    'last_name': config['last_name'],
                    'email': f"{config['username']}@unipay.local",
                    'phone_number': '555-0000',
                    'organization': org,
                    'role': config['role'],
                    'can_process_payments': True,
                    'can_void_payments': True,
                    'can_generate_reports': True,
                    'can_promote_officers': True,
                    'is_super_officer': False
                }
            )

            # Update if already exists (to ensure promotion authority is set)
            if not officer_created:
                officer.can_promote_officers = True
                officer.organization = org
                officer.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Officer updated: {officer.employee_id}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'✓ Officer created: {officer.employee_id}'))

            # Create user profile
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'is_officer': True}
            )

            # Store account info for display
            accounts.append({
                'org_name': config['org_name'],
                'username': config['username'],
                'password': config['password'],
                'role': config['role'],
                'description': config['description'],
                'org_code': config['org_code']
            })

            self.stdout.write(self.style.SUCCESS(f'✓ Permissions: Can promote/demote officers'))
            self.stdout.write(self.style.SUCCESS(f'✓ Access: {config["description"]}'))

        # Display all created accounts
        self.stdout.write(self.style.SUCCESS('\n\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('PROMOTION AUTHORITY ACCOUNTS'))
        self.stdout.write(self.style.SUCCESS('='*80))

        for i, account in enumerate(accounts, 1):
            self.stdout.write(self.style.HTTP_INFO(f'\n{i}. {account["org_name"]}'))
            self.stdout.write(f'   Username: {account["username"]}')
            self.stdout.write(f'   Password: {account["password"]}')
            self.stdout.write(f'   Role: {account["role"]}')
            self.stdout.write(self.style.SUCCESS(f'   Promotion Authority: ✅ YES'))
            self.stdout.write(f'   Access: {account["description"]}')

        # Update affiliations if not skipped
        if not options['skip_update_affiliations']:
            self.stdout.write(self.style.SUCCESS('\n' + '='*80))
            self.stdout.write(self.style.SUCCESS('UPDATING ORGANIZATION AFFILIATIONS'))
            self.stdout.write(self.style.SUCCESS('='*80))

            updates = [
                ('MEDBIO', 'MEDICAL_BIOLOGY'),
                ('MARINEBIO', 'MARINE_BIOLOGY'),
                ('IT', 'INFORMATION_TECHNOLOGY'),
                ('COMSCI', 'COMPUTER_SCIENCE'),
            ]

            for org_code, program_affiliation in updates:
                try:
                    org = Organization.objects.get(code=org_code)
                    org.program_affiliation = program_affiliation
                    org.save()
                    self.stdout.write(self.style.SUCCESS(f'✓ Updated {org.name}: {program_affiliation}'))
                except Organization.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'⚠ {org_code} not found'))

        self.stdout.write(self.style.SUCCESS('\n' + '='*80 + '\n'))
        self.stdout.write(self.style.SUCCESS('✅ SETUP COMPLETE! Officers are ready for testing.'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))
