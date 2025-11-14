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

5. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

6. **Access the app:**
   - Home: `http://127.0.0.1:8000/`
   - Student dashboard: `http://127.0.0.1:8000/student/dashboard/`
   - Officer dashboard: `http://127.0.0.1:8000/officer/dashboard/`
   - Admin panel: `http://127.0.0.1:8000/admin/`

## Test Accounts

### Superuser Accounts

| Username        | Password   | Role / Notes                                   |
|-----------------|------------|-----------------------------------------------|
| `superofficer`  | `admin123` | Superuser + Officer Status Flag enabled        |
| `superstudent`  | `admin123` | Superuser + Student profile (for testing)      |

### Officer Accounts (Tier 1 - Program-Specific Organizations)

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

### Fee Calculation Logic
- **Tier 1 Fees**: Only shown to students whose program matches the organization's program affiliation
- **Tier 2 Fees**: Shown to all students regardless of program
- Students see a combined bill reflecting only their relevant obligations

## Management Commands

### Create/Reset Sample Data
```bash
# Create new data (keeps existing)
python manage.py create_initial_data --students 10

# Clear old data and create fresh
python manage.py create_initial_data --reset --students 10 --fees 3
```

### Database Management
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Clear all data
python manage.py flush