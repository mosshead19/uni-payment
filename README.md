# UniPay - Unified Payment Portal

## 🎯 Problem Statement

Managing fee payments in educational institutions, particularly at the college level, presents numerous challenges:

- **Fragmented Payment Systems**: Different programs and organizations often use separate payment methods, leading to confusion and inefficiency
- **Complex Fee Structures**: Students need to navigate multiple fee types (program-specific fees vs. college-wide fees) without a unified view
- **Manual Processing**: Traditional payment processing is time-consuming, error-prone, and lacks real-time tracking
- **Limited Transparency**: Students struggle to track payment history, outstanding fees, and payment status
- **Access Control Issues**: Managing officer permissions across different organizational levels (college vs. program) requires complex authorization logic
- **QR Code Integration**: Modern payment systems require seamless QR code generation and scanning capabilities

**UniPay** solves these challenges by providing a **unified, intelligent payment portal** specifically designed for the College of Sciences, featuring a two-tiered fee system, role-based access control, and modern QR code payment processing.

## ✨ Key Features

### 🔐 Unified Authentication
- **Single Sign-On**: All users (students and officers) authenticate through one portal using Google OAuth
- **Role-Based Access Control**: Automatic role detection based on user profile (student vs. officer)
- **Secure Authentication**: Integration with Django AllAuth for secure OAuth 2.0 authentication

### 💰 Two-Tiered Fee System
- **Tier 1 - Program Affiliation Fees**: Program-specific fees unique to each academic program
  - Medical Biology, Marine Biology, Computer Science, Environmental Science, Information Technology
- **Tier 2 - College-Wide Organization Fees**: Mandatory fees for all students across the College
  - College Student Government (CSG),
  -  Compendium
- **Intelligent Fee Calculation**: Students only see fees relevant to their program and college requirements

### 📱 QR Code Payment Processing
- **QR Code Generation**: Students can generate unique QR codes for payment requests
- **QR Code Scanning**: Officers can scan QR codes to process payments instantly
- **Real-Time Status Updates**: Payment status updates immediately after processing

### 👥 Multi-Level Organization Hierarchy
- **College-Level Officers**: Can manage all programs under the college
- **Program-Level Officers**: Limited to their specific program data
- **Hierarchical Access Control**: Officers can only access data from their organization and child organizations
- **Promotion Authority**: Designated  officers can promote students to officer status within their scope or demote officer of their respective program affiliation to student status 

### 📊 Comprehensive Dashboards
- **Student Dashboard**: 
  - View all applicable fees (Tier 1 + Tier 2)
  - Generate QR codes for payment requests
  - Track payment history and outstanding fees
  - View payment receipts
- **Officer Dashboard**:
  - Process payments via QR code scanning
  - View organization-specific statistics
  - Manage fee types and payment requests
  - Access bulk payment posting
  - View transaction history

### 🔒 Security & Permissions
- **Data Isolation**: Officers can only access data from their organization hierarchy
- **Permission-Based Features**: Different officer roles have different capabilities
- **Activity Logging**: All promotions, demotions, and critical actions are logged
- **Audit Trail**: Complete history of payment transactions and officer actions

### 📧 Email Notifications
- **Payment Receipts**: Automatic email receipts after successful payment processing
- **Payment Confirmations**: Real-time notifications for payment status changes

### 📱 Progressive Web App (PWA)
- **Mobile-Friendly**: Responsive design optimized for mobile devices
- **Offline Capability**: Basic functionality available offline
- **Installable**: Can be installed as a native app on mobile devices

## 🛠️ Tech Stack

### Backend
- **Django 5.2.7**: High-level Python web framework for rapid development
- **Django AllAuth 65.13.1**: Integrated authentication system with Google OAuth support
- **SQLite**: Lightweight database for development (easily switchable to PostgreSQL for production)
- **Python 3.11+**: Modern Python with type hints and async support

### Frontend
- **Tailwind CSS**: Utility-first CSS framework for rapid UI development
- **Bootstrap 5**: Additional CSS framework for responsive components
- **Lucide Icons**: Modern icon library for UI elements
- **Custom CSS Design System**: Minimalist green-to-yellow gradient theme

### Payment & QR Code
- **QRCode 8.2**: Python library for QR code generation
- **Pillow 12.0.0**: Image processing for QR code rendering

### Email & Communication
- **Django SendGrid V5 1.2.3**: Email service integration for receipts and notifications
- **SendGrid 6.12.5**: Transactional email API

### Development & Deployment
- **Django PWA 2.0.1**: Progressive Web App support
- **WhiteNoise 6.11.0**: Static file serving for production
- **Python-Dotenv 1.2.1**: Environment variable management
- **Faker 37.12.0**: Test data generation for development

### Security
- **Cryptography 46.0.3**: Cryptographic primitives for secure operations
- **PyJWT 2.10.1**: JSON Web Token implementation for secure authentication

## 🎨 Design Philosophy

UniPay features a **minimalist, modern design** with a clean green-to-yellow gradient theme:
- **Primary Gradient**: `linear-gradient(0deg, rgba(34, 195, 112, 1) 0%, rgba(60, 194, 104, 1) 39%, rgba(253, 187, 45, 1) 100%)`
- **Simple & Clean**: Focus on usability and clarity
- **Responsive Design**: Optimized for desktop, tablet, and mobile devices
- **Accessible**: WCAG-compliant color contrasts and keyboard navigation

## System Architecture

### Scope
- **College Focus**: This system is designed specifically for the **College of Sciences** at the moment
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

## Authentication

### Google OAuth Login Only

UniPay uses **Google OAuth authentication exclusively**. All users must sign in using their PSU Palawan corporate email account (`@psu.palawan.edu.ph`).

**Login Requirements:**
- ✅ Must use Google account with `@psu.palawan.edu.ph` email domain
- ✅ First-time users are automatically registered upon first login
- ✅ User roles (Student/Officer) are determined by their profile in the system
- ❌ Username/password login is **not supported**

### Test Account Setup

To create test accounts for development/testing:

1. **Create users via Django admin or management commands:**
   ```bash
   python manage.py create_promotion_officers
   ```

2. **Users must have Google accounts with `@psu.palawan.edu.ph` email addresses**

3. **User roles are assigned through:**
   - Student profiles (automatic for students)
   - Officer profiles (created by authorized officers or admins)
   - Django admin panel (for superusers)

### Test Account Types

The system supports different account types for testing:

#### College-Level Officers
- **Organization**: College of Sciences Administration
- **Role**: College Administrator
- **Permissions**: Can process & void payments, generate reports, **promote officers**
- **Access**: See and manage ALL programs under College of Sciences
  - Computer Science, Environmental Science, Information Technology
- **Use Case**: Test college-wide officer accessing data from all programs

#### Program-Level Officers (No Promotion Authority)
- **Organization**: Program-specific (e.g., Computer Science Student Government)
- **Role**: Treasurer
- **Permissions**: Can process payments only (no void, no reports, NO promotion)
- **Access**: See ONLY their specific program data
- **Use Case**: Test program-specific officer with limited access

#### Program-Level Officers (With Promotion Authority)
- **Organization**: Program-specific (e.g., Environmental Science Club)
- **Role**: President
- **Permissions**: Can process & void payments, **promote officers**
- **Access**: See ONLY their program data + can promote/demote officers within program
- **Use Case**: Test program-level promotion authority

#### Superuser Accounts
- **Access**: Full Django admin panel access
- **Permissions**: Unrestricted access to all features and data
- **Use Case**: System administration and testing

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

1. **Test College-Level Officer**
   - Login with Google account (college-level officer email)
   - Go to Officer Dashboard
   - Verify you can see all 3 programs' data in admin pages
   - Click "Promote Officer" and verify you can select students from ALL programs
   - Try assigning officers to different programs

2. **Test Program-Level Officer - No Promotion**
   - Login with Google account (program-level officer email without promotion authority)
   - Go to Officer Dashboard
   - Verify you see ONLY your program's data
   - Verify "Promote Officer" button is NOT visible
   - Try accessing `/staff/students/` - should see only your program's students
   - Try accessing student detail page from your program - should succeed
   - Try accessing student from another program - should be denied

3. **Test Program-Level Officer - With Promotion**
   - Login with Google account (program-level officer email with promotion authority)
   - Go to Officer Dashboard
   - goto student > actions > promote / demote , you should onyl be able to do such actions to students within your program scope
   - Click "Promote Officer" and verify only your program's students appear
   - Try promoting a student from another program - should be denied

4. **Test Super Admin**
   - Login with Google account (superuser email)
   - Access `/admin/` - should see all data
   - Create new organizations or modify any student/officer
   - Use Django admin to manage hierarchy and permissions

### Security Verification Checklist
- [ ] cs_officer cannot view data from other programs
- [ ] cs_officer cannot access promote/demote functions
- [ ] es_officer can promote students only within their program
- [ ] superuser has unrestricted access to all data


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

**Note:** All test accounts must be created with Google accounts using `@psu.palawan.edu.ph` email addresses. The management command creates officer profiles with promotion authority (`can_promote_officers = TRUE`) and full payment processing permissions.

### Database Management
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Clear all data
python manage.py flush