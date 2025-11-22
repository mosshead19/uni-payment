## System Architecture

### Scope
- **College Focus**: This system is designed specifically for the **College of Sciences** only
- All courses, students, and organizations are within the College of Sciences

### Unified Login System
- **Single Authentication Portal**: All users (students and officers) use the same login system
- **Officer Status Flag**: The `UserProfile.is_officer` flag determines access to officer-exclusive features
- **Role-Based Access**: Officers can promote students, process payments, and access administrative features

### Two-Tiered Fee System

The system implements precise data segregation for financial management:

1. **Tier 1: Program Affiliation Fees**
   - Exclusive fees unique to each student's specific academic program
   - **Only 5 programs are supported:**
     - Medical Biology
     - Marine Biology
     - Computer Science
     - Environmental Science
     - Information Technology

2. **Tier 2: College-Based Organization Fees**
   - Mandatory payments for college-wide groups
   - Organizations (separate entities):
     - College Student Government (CSG)
     - Compendium

Students only see and are charged for fees based on their program affiliation and the standard college-wide requirements.

## Getting Started

1. **Create and activate a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Apply migrations:**
   ```bash
   cd projectsite
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **Seed sample data:**
   ```bash
   python manage.py create_initial_data --reset --students 10 --fees 3
   ```
   
   Options:
   - `--reset`: Clear previously generated fake data before creating new records
   - `--students N`: Number of students to create (default: 10)
   - `--orgs N`: Number of organizations to create (default: 7 - includes 5 Tier 1 + 2 Tier 2)
   - `--fees N`: Fee types per organization (default: 3)
   - `--requests N`: Payment requests per student (default: 1)

5. **Create promotion authority test accounts:**
   ```bash
   python manage.py create_promotion_officers
   ```

6. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

7. **Access the app:**
   - Home: `http://127.0.0.1:8000/`
   - Student dashboard: `http://127.0.0.1:8000/student/dashboard/`
   - Officer dashboard: `http://127.0.0.1:8000/officer/dashboard/`
   - Admin panel: `http://127.0.0.1:8000/admin/`

## Deployment Instructions

### Initial Setup (First Time)
```bash
# 1. Activate virtual environment
.\.venv\Scripts\activate

# 2. Install/update dependencies
pip install -r requirements.txt

# 3. Apply database migrations
python manage.py migrate

# 4. Create sample data (optional)
python manage.py create_initial_data --reset --students 10

# 5. Create promotion authority officers
python manage.py create_promotion_officers

# 6. Collect static files (for production)
python manage.py collectstatic --noinput

# 7. Start the server
python manage.py runserver 0.0.0.0:8000
```

**📖 See [DEPLOYMENT_FLOW.md](DEPLOYMENT_FLOW.md) for:**
- Complete user registration & promotion flow
- PythonAnywhere specific setup steps
- Detailed timeline of who can login when
- Real-world usage scenarios
- Troubleshooting guide

### Updating Existing Installation
```bash
# 1. Pull latest code
git pull origin main

# 2. Install new dependencies
pip install -r requirements.txt

# 3. Apply new migrations
python manage.py migrate

# 4. Create any missing accounts (idempotent - safe to run anytime)
python manage.py create_promotion_officers

# 5. Restart the application
```

### Creating Officers in Production
The **Django management command** is the recommended approach for production:

```bash
# Create all 5 promotion authority officers in one command
python manage.py create_promotion_officers

# Show help for advanced options
python manage.py create_promotion_officers --help

# Skip updating affiliations if you've already done it
python manage.py create_promotion_officers --skip-update-affiliations
```

This command is:
- ✅ **Idempotent** - Safe to run multiple times without creating duplicates
- ✅ **Non-destructive** - Won't affect existing data
- ✅ **Part of the codebase** - No need for external scripts
- ✅ **Django-native** - Works with your deployment system

## Test Accounts

### Superuser Accounts

| Username        | Password         | Role / Notes                                   |
|-----------------|------------------|-----------------------------------------------|
| `superofficer`  | `SuperOfficer@123` | Super Officer + Organization-level access    |
| `admin2`        | `Admin2@12345`   | Full superuser + admin panel access           |
| `superstudent`  | `SuperStudent@123` | Superuser + Student profile (for testing)     |

### Organization Hierarchy Test Accounts

These accounts test the multi-level organization structure with different access permissions:

#### College-Level Officer
- **Username**: `college_officer`
- **Password**: `CollegeOfficer@123`
- **Organization**: College of Sciences Administration
- **Role**: College Administrator
- **Permissions**: Can process & void payments, generate reports, **promote officers**
- **Access**: See and manage ALL programs under College of Sciences
  - Computer Science
  - Environmental Science
  - Information Technology
- **Use Case**: Test college-wide officer accessing data from all programs

#### Program-Level Officer (No Promotion Authority)
- **Username**: `cs_officer`
- **Password**: `CSProgram@123`
- **Organization**: Computer Science Student Government
- **Role**: Treasurer
- **Permissions**: Can process payments only (no void, no reports, NO promotion)
- **Access**: See ONLY Computer Science program data
- **Use Case**: Test program-specific officer with limited access and no promotion capability

#### Program-Level Officer (With Promotion Authority)
- **Username**: `es_officer`
- **Password**: `EnvScience@123`
- **Organization**: Environmental Science Club
- **Role**: President
- **Permissions**: Can process & void payments, **promote officers** (no reports)
- **Access**: See ONLY Environmental Science program data + promote/demote officers within program
- **Use Case**: Test program-level promotion authority

### Promotion Authority Test Accounts (Multi-Organization)

These accounts have promotion authority (`can_promote_officers = TRUE`) and can promote/demote officers within their accessible organizations:

#### All Organizations Admin (College-Level)
- **Username**: `all_org_officer`
- **Password**: `AllOrg@123`
- **Organization**: ALL Organizations Admin (COLLEGE level)
- **Role**: College Administrator
- **Permissions**: Can process & void payments, generate reports, **promote/demote officers**
- **Access**: See and manage ALL programs (Medical Biology, Marine Biology, IT, Computer Science)
- **Use Case**: Test college-wide promotion authority across multiple programs

#### Medical Biology Officer
- **Username**: `medbio_officer`
- **Password**: `MedBio@123`
- **Organization**: Medical Biology (PROGRAM level)
- **Role**: Program Head
- **Permissions**: Can process & void payments, generate reports, **promote/demote officers**
- **Access**: See ONLY Medical Biology program data + full promotion authority within program
- **Use Case**: Test program-level promotion authority with full management capabilities

#### Marine Biology Officer
- **Username**: `marinebio_officer`
- **Password**: `MarineBio@123`
- **Organization**: Marine Biology (PROGRAM level)
- **Role**: Program Head
- **Permissions**: Can process & void payments, generate reports, **promote/demote officers**
- **Access**: See ONLY Marine Biology program data + full promotion authority within program
- **Use Case**: Test program-level promotion authority with full management capabilities

#### Information Technology Officer
- **Username**: `it_officer`
- **Password**: `IT@123`
- **Organization**: Information Technology (PROGRAM level)
- **Role**: Program Head
- **Permissions**: Can process & void payments, generate reports, **promote/demote officers**
- **Access**: See ONLY IT program data + full promotion authority within program
- **Use Case**: Test program-level promotion authority with full management capabilities

#### Computer Science Officer
- **Username**: `comsci_officer`
- **Password**: `ComSci@123`
- **Organization**: Computer Science (PROGRAM level)
- **Role**: Program Head
- **Permissions**: Can process & void payments, generate reports, **promote/demote officers**
- **Access**: See ONLY Computer Science program data + full promotion authority within program
- **Use Case**: Test program-level promotion authority with full management capabilities

### Original Officer Accounts (Tier 1 - Program-Specific Organizations)

| Username             | Password   | Organization Code | Fee Tier | Program Affiliation                    |
|----------------------|------------|-------------------|----------|----------------------------------------|
| `officer_bio`        | `admin123` | BIO               | Tier 1   | Medical Biology                        |
| `officer_mbio`       | `admin123` | MBIO              | Tier 1   | Marine Biology                         |
| `officer_bscs`       | `admin123` | BSCS              | Tier 1   | Computer Science                       |
| `officer_bses`       | `admin123` | BSES              | Tier 1   | Environmental Science                  |
| `officer_bsit`       | `admin123` | BSIT              | Tier 1   | Information Technology                 |

### Officer Accounts (Tier 2 - College-Wide Organizations)

| Username             | Password   | Organization Code | Fee Tier | Description                            |
|----------------------|------------|-------------------|----------|----------------------------------------|
| `officer_csg`        | `admin123` | CSG               | Tier 2   | College Student Government              |
| `officer_compendium` | `admin123` | COMPENDIUM        | Tier 2   | Compendium                              |

### Sample Student Accounts

The data seeder provisions 10 numbered students. All use the password `password123`.

| Username     | Password     | Details                                           |
|--------------|--------------|---------------------------------------------------|
| `student001` | `password123`| Randomized course/year; sees Tier 1 + Tier 2 fees |
| `student002` | `password123`| …                                                 |
| `student010` | `password123`| …                                                 |

## Key Features

### For Students
- View applicable fees based on program affiliation (Tier 1) and college-wide requirements (Tier 2)
- Generate QR codes for payment requests
- Track payment history and outstanding fees
- Receive email receipts after payment

### For Officers
- Process payment requests via QR code scanning
- View organization-specific dashboards
- Generate reports and manage fee types
- Promote students to officer status (Officer-exclusive ability)
- Void payments (with proper permissions)

### For College-Level Officers (Multi-Program Access)
- Access and manage **all programs** under their college hierarchy
- Promote/demote officers across all programs in the college
- View consolidated reporting for entire college
- Delegate officer responsibilities to program-level officers

### For Program-Level Officers
- Access data for **only their specific program**
- If authorized: Promote/demote students within their program
- Limited permissions based on role (Treasurer, President, etc.)
- Cannot access other program's data or officers

### Fee Calculation Logic
- **Tier 1 Fees**: Only shown to students whose program matches the organization's program affiliation
- **Tier 2 Fees**: Shown to all students regardless of program
- Students see a combined bill reflecting only their relevant obligations

## Organization Hierarchy Testing

### Hierarchy Structure
```
College of Sciences (COLLEGE LEVEL)
├── College of Sciences Administration
│   └── college_officer (can manage all programs)
│
├── Computer Science (PROGRAM LEVEL)
│   └── Computer Science Student Government
│       └── cs_officer (program access only, no promotion)
│
├── Environmental Science (PROGRAM LEVEL)
│   └── Environmental Science Club
│       └── es_officer (program access only, WITH promotion)
│
└── Information Technology (PROGRAM LEVEL)
    └── [No officer assigned yet]
```

### Testing Workflow

1. **Test College-Level Officer (college_officer)**
   - Login with `college_officer` / `CollegeOfficer@123`
   - Go to Officer Dashboard
   - Verify you can see all 3 programs' data in admin pages
   - Click "Promote Officer" and verify you can select students from ALL programs
   - Try assigning officers to different programs

2. **Test Program-Level Officer - No Promotion (cs_officer)**
   - Login with `cs_officer` / `CSProgram@123`
   - Go to Officer Dashboard
   - Verify you see ONLY Computer Science data
   - Verify "Promote Officer" button is NOT visible
   - Try accessing `/staff/students/` - should see only CS students
   - Try accessing CS student detail page - should succeed
   - Try accessing Environmental Science student - should be denied

3. **Test Program-Level Officer - With Promotion (es_officer)**
   - Login with `es_officer` / `EnvScience@123`
   - Go to Officer Dashboard
   - Verify you see ONLY Environmental Science data
   - Verify "Promote Officer" and "Demote Officer" buttons ARE visible
   - Click "Promote Officer" and verify only ES students appear
   - Try promoting a CS student - should be denied

4. **Test Super Admin (admin2)**
   - Login with `admin2` / `Admin2@12345`
   - Access `/admin/` - should see all data
   - Create new organizations or modify any student/officer
   - Use Django admin to manage hierarchy and permissions

### Security Verification Checklist
- [ ] cs_officer cannot view data from other programs
- [ ] cs_officer cannot access promote/demote functions
- [ ] es_officer can promote students only within their program
- [ ] college_officer can manage all programs in the college
- [ ] admin2 has unrestricted access to all data
- [ ] Accessing denied resources returns 403 or redirects to login

## Management Commands

### Create/Reset Sample Data
```bash
# Create new data (keeps existing)
python manage.py create_initial_data --students 10

# Clear old data and create fresh
python manage.py create_initial_data --reset --students 10 --fees 3
```

### Create Test Promotion Authority Accounts

**Option 1: Django Management Command** (Recommended for Production)
```bash
# Create 5 promotion authority officers and update affiliations
python manage.py create_promotion_officers
```

**Option 2: Standalone Script** (For Development)
```bash
# Create 5 promotion authority officers (college-level + 4 program-level)
python create_promotion_officers.py

# Update organization program affiliations (required after creating accounts)
python update_org_affiliations.py
```

**Test Accounts Created:**
- `all_org_officer` / `AllOrg@123` - College-level (all programs)
- `medbio_officer` / `MedBio@123` - Medical Biology only
- `marinebio_officer` / `MarineBio@123` - Marine Biology only
- `it_officer` / `IT@123` - Information Technology only
- `comsci_officer` / `ComSci@123` - Computer Science only

All accounts have promotion authority (`can_promote_officers = TRUE`) and full payment processing permissions.

### Database Management
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Clear all data
python manage.py flush