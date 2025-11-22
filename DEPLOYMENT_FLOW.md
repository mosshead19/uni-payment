# User Registration & Officer Promotion Flow on PythonAnywhere

## Phase 1: Initial Deployment Setup (Admin Only)

```
Admin/Developer
    ↓
1. Deploy code to PythonAnywhere
2. Configure database
3. Run migrations: python manage.py migrate
4. Create promotion authority officers: python manage.py create_promotion_officers
5. (Optional) Seed sample data: python manage.py create_initial_data
    ↓
System Ready with 5 Pre-Created Officers:
✅ all_org_officer (AllOrg@123)
✅ medbio_officer (MedBio@123)
✅ marinebio_officer (MarineBio@123)
✅ it_officer (IT@123)
✅ comsci_officer (ComSci@123)
```

---

## Phase 2: Real User Registration & Officer Creation

### Scenario A: Student Joins First (Normal Path)

```
1. NEW STUDENT visits http://yourapp.pythonanywhere.com/
   ↓
2. Clicks "Register as Student"
   ↓
3. Creates student account with:
   - Username, password, email
   - Student ID number
   - Program (Medical Biology, Marine Bio, CS, ES, IT)
   - Year level
   ↓
4. Account created: is_officer = FALSE
   ↓
5. Student can only:
   ✅ View fees
   ✅ Generate payment requests
   ✅ View payment history
   ✅ Cannot promote others
   ✅ Cannot process payments
   ↓
6. Waits for officer to process payments or promote them to officer
```

### Scenario B: Officer Promotes Student (Typical Flow)

```
STUDENT (already exists in system)
    ↓
OFFICER WITH PROMOTION AUTHORITY logs in
    ↓
Goes to: Officer Dashboard → "Promote Officer" button
    ↓
Selects:
- Student to promote
- Organization they'll work for
- Role (e.g., Treasurer, President)
- Permissions (process payments, void, promotion authority)
    ↓
Student's account UPDATED:
- is_officer flag = TRUE
- Officer profile created
- Organization assigned
- Permissions set
    ↓
STUDENT CAN NOW:
✅ Login with same username/password
✅ See "Officer Dashboard" option
✅ Process payments
✅ View all organization data (if authorized)
✅ Promote/demote (if can_promote_officers=TRUE)
```

---

## Phase 3: Complete User Lifecycle

### Timeline View

```
DAY 1 - DEPLOYMENT
├─ Admin deploys code
├─ Runs: python manage.py migrate
├─ Runs: python manage.py create_promotion_officers
│  └─ Creates 5 officers with promotion authority
└─ System LIVE ✅

DAY 2-N - NORMAL OPERATIONS
├─ Students register themselves
│  ├─ Visit registration page
│  ├─ Create account with credentials
│  ├─ Select program (Medical Bio, Marine Bio, etc.)
│  └─ Account created with is_officer=FALSE
│
├─ Officer logs in (pre-created or promoted)
│  ├─ Login with credentials
│  ├─ See officer dashboard
│  └─ Can promote/demote students
│
├─ Officer promotes student
│  ├─ Navigate to "Promote Officer"
│  ├─ Select student from dropdown (filtered by org)
│  ├─ Set permissions
│  └─ Student becomes officer
│
└─ New officer logs in with original credentials
   ├─ Still same username/password
   ├─ Now sees officer dashboard
   ├─ Can process payments
   └─ Can promote others (if authorized)
```

---

## Who Can Do What - Access Control

### Before Deployment (Admin Phase)
```
✅ Developer/Admin can:
   - Access database directly
   - Run management commands
   - Create initial officers
   - Deploy code
   - Configure PythonAnywhere
   
❌ Regular users:
   - Cannot access system yet
```

### After Deployment - Initial State

```
PRE-CREATED OFFICERS (from create_promotion_officers command):
✅ all_org_officer (AllOrg@123)
   ├─ Can see ALL programs
   ├─ Can promote/demote any officer
   └─ Role: College Administrator

✅ medbio_officer (MedBio@123)
   ├─ Can see Medical Biology only
   ├─ Can promote/demote in Medical Biology
   └─ Role: Program Head

✅ Similar for marinebio, it, comsci officers

STUDENTS:
❌ Cannot login yet (no student accounts exist)
❌ Can only register new accounts
```

### After First Student Registration

```
STUDENT (newly registered):
├─ Can login ✅
├─ Can view fees ✅
├─ Can generate payment requests ✅
├─ Cannot process payments ❌
├─ Cannot promote others ❌
└─ Cannot see officer dashboard ❌

OFFICER:
├─ Can login ✅
├─ Can view payments ✅
├─ Can process payments ✅
├─ Can promote/demote (if authorized) ✅
└─ Can see officer dashboard ✅
```

### After Officer Promotes Student

```
PROMOTED STUDENT (now officer):
├─ Can login with SAME credentials ✅
├─ Can process payments ✅
├─ Can view organization data ✅
├─ Can see officer dashboard ✅
└─ Can promote others (if granted authority) ✅
```

---

## PythonAnywhere Specific Deployment Flow

### Step-by-Step Deployment on PythonAnywhere

```
1. CREATE ACCOUNT & SETUP
   ├─ Create PythonAnywhere account
   ├─ Create Web App (Django framework)
   ├─ Point to your git repository
   └─ Configure Python version (3.x)

2. INITIAL DATABASE SETUP
   ├─ PythonAnywhere creates SQLite database (default)
   ├─ Navigate to: Web → Database
   ├─ Confirm database file location
   └─ Set DATABASE_NAME in settings.py

3. INSTALL DEPENDENCIES
   ├─ Bash console: pip install -r requirements.txt
   └─ May take 2-5 minutes

4. RUN MIGRATIONS (Critical!)
   ├─ Bash console: python manage.py migrate
   ├─ Creates all database tables
   ├─ Applies migration 0013 (organization hierarchy)
   └─ Must complete before next step

5. CREATE PROMOTION OFFICERS (This Step!)
   ├─ Bash console: python manage.py create_promotion_officers
   ├─ Creates 5 officers with promotion authority
   ├─ Creates "ALL Organizations Admin" (parent)
   ├─ Creates 4 program-level organizations
   └─ Creates associated users and credentials

6. (OPTIONAL) SEED SAMPLE DATA
   ├─ Bash console: python manage.py create_initial_data --reset --students 20
   ├─ Creates 20 sample students
   ├─ Creates sample fees
   └─ Good for testing before real students arrive

7. COLLECT STATIC FILES
   ├─ Bash console: python manage.py collectstatic --noinput
   ├─ Collects CSS, JS, images
   └─ Required for production

8. RELOAD WEB APP
   ├─ Web tab → Reload button
   ├─ Activates changes
   └─ System LIVE ✅

9. TEST THE SYSTEM
   ├─ Visit: yourapp.pythonanywhere.com/
   ├─ Register as student
   ├─ Login as officer (use pre-created credentials)
   ├─ Try promoting the student
   └─ Test complete!
```

---

## Command Reference for PythonAnywhere

### Bash Console Commands (in order)

```bash
# 1. Navigate to project directory
cd /home/username/uni-payment/projectsite

# 2. Apply database migrations
python manage.py migrate

# 3. Create 5 promotion authority officers
python manage.py create_promotion_officers

# 4. (Optional) Create sample data
python manage.py create_initial_data --reset --students 20

# 5. Collect static files
python manage.py collectstatic --noinput

# 6. Check for errors
python manage.py check
```

### If You Need to Reset

```bash
# WARNING: Deletes ALL data!
python manage.py flush --noinput

# Then re-run creation commands
python manage.py migrate
python manage.py create_promotion_officers
python manage.py create_initial_data --reset --students 10
```

---

## Real-World Usage Scenario

### Week 1: System Launches
```
MONDAY 8:00 AM
├─ Promotion officer (all_org_officer) logs in
├─ Checks officer dashboard
├─ System ready to accept students
└─ Notifies students they can register

MONDAY-FRIDAY
├─ 50 students register themselves
│  ├─ Visit /student/register/
│  ├─ Create accounts
│  ├─ Assigned to programs
│  └─ Can view fees
│
├─ Students generate payment requests
│  ├─ Cannot process own payments
│  └─ Wait for officer
│
└─ Officer processes payments
   ├─ Scans QR codes
   ├─ Records payments
   └─ Students get receipts

FRIDAY EVENING
├─ College needs program officers
├─ Promotion officer (all_org_officer) promotes students:
│  ├─ Promotes 1 Medical Bio student → medbio_officer
│  ├─ Promotes 1 Marine Bio student → marinebio_officer
│  ├─ Promotes 1 IT student → it_officer
│  └─ Promotes 1 CS student → comsci_officer
│
└─ New officers can now:
   ├─ Process their program's payments
   ├─ Promote students in their program (if authorized)
   └─ View only their program's data
```

---

## Security Notes

### Login Credentials

```
PRE-CREATED OFFICERS (Change immediately after deployment):
all_org_officer: AllOrg@123 ← CHANGE THIS!
medbio_officer: MedBio@123 ← CHANGE THIS!
marinebio_officer: MarineBio@123 ← CHANGE THIS!
it_officer: IT@123 ← CHANGE THIS!
comsci_officer: ComSci@123 ← CHANGE THIS!

RECOMMENDED PROCEDURE:
1. Deploy with default credentials
2. Login as all_org_officer
3. Change password in Django admin
4. Share new password securely
5. Document in secure location
```

### Database Access on PythonAnywhere

```
Web app database:
├─ Located: /var/www/username_pythonanywhere_com/db.sqlite3
├─ Accessible via: Bash console
├─ Accessible via: Web tab → Database
├─ NOT directly accessible from internet
└─ Safe for student data

Static files:
├─ Located: /var/www/username_pythonanywhere_com/static/
├─ Collected via: python manage.py collectstatic
└─ Served by web server

Media files:
├─ Uploaded by students (if enabled)
├─ Stored separately
└─ Need configuration in settings.py
```

---

## Troubleshooting

### "I ran create_promotion_officers twice - did it break anything?"
```
✅ NO PROBLEM! Command is idempotent.
   ├─ Checks if users already exist
   ├─ Won't create duplicates
   ├─ Safe to run multiple times
   └─ Can run on schedule if needed
```

### "Students can't register, what happened?"
```
CHECK:
1. Database: python manage.py dbshell
2. Users table: SELECT * FROM auth_user;
3. Check migrations: python manage.py showmigrations
4. Re-run migrations: python manage.py migrate --fake-initial
```

### "Officer can't see students in promotion dropdown"
```
This is the bug we FIXED earlier!
1. Make sure student filtering uses program_affiliation
2. Update organization program affiliations
3. Students must have valid course assigned
4. Officer must have can_promote_officers=TRUE
```

---

## Summary Timeline

```
PHASE 1: DEPLOYMENT (Admin, ~15 minutes)
└─ Deploy code → Run migrations → Create officers → System ready

PHASE 2: STUDENT REGISTRATION (Ongoing, day 1+)
└─ Students register themselves → Fill system with users

PHASE 3: OFFICER PROMOTION (As needed, day 3-7)
└─ College officers promote students → Expand leadership

PHASE 4: NORMAL OPERATIONS (Weeks 1+)
└─ Officers manage payments → Students pay → System runs
```

---

## Key Takeaway

**WHO LOGS IN FIRST?**
1. ✅ **Promotion Officers** (pre-created by admin)
   - Can login immediately after deployment
   - Use credentials from deployment output
   
2. ✅ **Students** (register themselves)
   - Can register anytime
   - Can view fees but can't process payments
   
3. ⏳ **New Officers** (promoted from students)
   - Promoted by existing officers
   - Login with their original student credentials
   - Immediately get officer permissions

**The system is designed so officers exist BEFORE students!**
