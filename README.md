
# EduManage – Student Course Management System

![EduManage Screenshot](https://img.freepik.com/free-vector/online-learning-isometric-concept_1284-17947.jpg)

**EduManage** is a Flask-based web application for managing students, courses, and enrollments using a PostgreSQL backend. It showcases extensive SQL feature integration and a modern responsive frontend.

---

## 🚀 1. Project Overview

EduManage helps educational institutions efficiently manage students, courses, enrollments, grades, and academic reports. It includes:

- Secure user authentication
- Student & course management
- Enrollment with capacity control
- Grade tracking and GPA reports
- Audit logging with triggers
- API endpoints for integration

---

## 🧰 2. Technology Stack

| Layer       | Technology                             |
|-------------|-----------------------------------------|
| **Frontend**| HTML5, Bootstrap 5, JavaScript           |
| **Backend** | Python 3.8+, Flask Framework            |
| **Database**| PostgreSQL 12+                          |
| **Auth**    | Flask-Login, Werkzeug password hashing  |

---

## ⚙️ 3. Installation Guide

### Step 1: Clone the repository
```bash
git clone https://github.com/yourusername/EduManage.git
cd EduManage
```

### Step 2: Create and configure `.env`
```ini
DB_HOST=localhost
DB_NAME=edumanage
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432
SECRET_KEY=your_secret_key
```

### Step 3: Set up the database
```sql
CREATE DATABASE edumanage;
```

### Step 4: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Run the application
```bash
python main.py
```

Visit `http://127.0.0.1:5000/` in your browser.

---

## 🗂️ 4. Project Structure

```
EduManage/
├── templates/
│   ├── landing_page.html
│   ├── index.html
│   ├── students/
│   ├── courses/
│   ├── auth/
│   └── reports/
├── main.py
├── .env
├── requirements.txt
└── README.md
```

---

## 🧠 5. SQL Features Implemented

- ✅ DDL (CREATE TABLE)
- ✅ DML (INSERT, UPDATE, DELETE)
- ✅ Stored Procedures
- ✅ Cursors and Exception Handlers
- ✅ Nested Queries and Joins
- ✅ User-Defined Functions
- ✅ Triggers for auditing

---

## 🧪 6. Usage Instructions

- Visit `/register` to create an account
- Access dashboard after login at `/home`
- Manage students/courses/enrollments via dashboard
- Use reports for GPA and performance analytics
- View audit log of student changes at `/audit_log`

---

## 🤝 10. Contribution Guidelines

1. Fork the repository
2. Create a new branch (`git checkout -b feature-name`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature-name`)
5. Create a pull request

---

## 📜 11. License Information

This project is licensed under the **MIT License**.  
See the [LICENSE](LICENSE) file for details.

---

> Developed by **Vansh Sambhaji Gosavi**  
> 📧 vanshgosavi7@gmail.com | 📱 +91-9359775740
