from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from paymentorg.models import Officer, Organization, UserProfile


class Command(BaseCommand):
    help = "Create test officers with promotion authority for all organizations"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("CREATING OFFICERS WITH PROMOTION AUTHORITY"))

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
                'description': 'Can promote/demote in ALL organizations, create new officer accounts, and manage all organizations',
                'program_affiliation': 'ALL',
                'can_create_officers': True
            },
            # ... add the other orgs exactly as in your script
        ]

        parent_org = None
        accounts = []

        for config in organizations_config:
            self.stdout.write(f"\nCreating: {config['org_name']}")

            # Organization creation
            if config['org_code'] == 'ALLORG':
                org, _ = Organization.objects.get_or_create(
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
            elif 'parent_org_code' in config:
                parent = Organization.objects.get(code=config['parent_org_code'])
                org, _ = Organization.objects.get_or_create(
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

            # User creation
            user, _ = User.objects.get_or_create(
                username=config['username'],
                defaults={
                    'email': f"{config['username']}@unipay.local",
                    'first_name': config['first_name'],
                    'last_name': config['last_name']
                }
            )
            user.set_password(config['password'])
            user.save()

            # Officer creation
            officer, created = Officer.objects.get_or_create(
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
                    'can_create_officers': config.get('can_create_officers', False),
                    'is_super_officer': False
                }
            )
            if not created:
                officer.can_promote_officers = True
                officer.can_create_officers = config.get('can_create_officers', False)
                officer.organization = org
                officer.save()

            # UserProfile creation
            UserProfile.objects.update_or_create(user=user, defaults={'is_officer': True})

            accounts.append({
                'org_name': config['org_name'],
                'username': config['username'],
                'password': config['password'],
                'role': config['role'],
                'description': config['description']
            })

        self.stdout.write(self.style.SUCCESS("Promotion authority officers created successfully."))
        for account in accounts:
            self.stdout.write(f"{account['username']} | {account['role']} | {account['org_name']}")
