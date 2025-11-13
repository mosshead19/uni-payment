
## Getting Started

1. **Create and activate a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate  # windows
   source .venv/bin/activate   # macOS / linux
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Apply migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **(Optional) Seed sample data:**
   ```bash
   python manage.py create_initial_data
   ```
   This creates organizations, officers, students, fee types, and payment requests for testing.

5. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

6. **Access the app:**
   - Student dashboard: `http://127.0.0.1:8000/student/dashboard/`
   - Officer dashboard: `http://127.0.0.1:8000/officer/dashboard/`
   - Admin/staff views are linked in the navbar for superusers.

### Superuser Accounts

| Username        | Password   | Role / Notes                                   |
|-----------------|------------|-----------------------------------------------|
| `superofficer`  | `admin123` | Superuser + staff + officer profile (ORG1)    |
| `superstudent`  | `admin123` | Superuser + staff + student profile           |

### Officer Accounts (seeded per organization)

| Username             | Password   | Organization Code | Organization Name                                 |
|----------------------|------------|-------------------|---------------------------------------------------|
| `officer_bio`        | `admin123` | BIO               | Bachelor of Science in Biology                    |
| `officer_mbio`       | `admin123` | MBIO              | Bachelor of Science in Marine Biology             |
| `officer_bscs`       | `admin123` | BSCS              | Bachelor of Science in Computer Science           |
| `officer_bses`       | `admin123` | BSES              | Bachelor of Science in Environmental Science      |
| `officer_bsit`       | `admin123` | BSIT              | Bachelor of Science in Information Technology     |
| `officer_studorg`    | `admin123` | STUDORG           | Student organizations (umbrella organization)     |

### Sample Student Accounts

The data seeder provisions 10 numbered students. All use the password `password123`.

| Username     | Password     | Example Details                                   |
|--------------|--------------|---------------------------------------------------|
| `student001` | `password123`| Randomized course/year; belongs to seeded orgs    |
| `student002` | `password123`| …                                                 |
| `student010` | `password123`| …                                                 |