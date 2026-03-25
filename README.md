# 🕒 Work Hours Tracking System

A lightweight and practical attendance tracking system built with **Python (Streamlit)** and **Supabase (PostgreSQL)**.  
Designed to provide a simple, secure, and user-friendly way to manage daily check-ins, check-outs, vacation days, and work hour tracking.

🌍 **Language:** The application interface is fully in **Hebrew**.

🚀 **Live Demo:**  https://attendance-app-otbl.onrender.com
---

## ✨ Features

- 🔐 **Authentication system**
  - Username & password login
  - Passwords are securely stored using hashing

- ⏱ **Daily attendance tracking**
  - Check-in / Check-out logging
  - Automatic session duration calculation

- 🏖 **Leave reporting**
  - Mark specific days as vacation / day off
  - Clearly separates working days from non-working days

- 📅 **Date-based records**
  - View attendance and leave status per selected date

- 📊 **Reports & exports**
  - Generate summaries of working hours
  - Export data for external use (e.g., Excel)

- ⚡ **Real-time UI**
  - Built with Streamlit for a fast and interactive experience

---

## 🔒 Security (Minimal but intentional)

This project implements foundational security practices:

- 🔑 **Password Hashing**  
  User passwords are never stored in plain text.

- 🔐 **Environment Variables**  
  Sensitive data (database credentials, secrets) are stored in `.env` files and are not exposed in the repository.

- 🚫 **.gitignore protection**  
  Prevents leaking:
  - `.env` files  
  - Python cache files (`__pycache__`, `.pyc`)

> ⚠️ Note: This is an MVP-level security implementation and can be extended further (JWT, RLS, etc).

---

## 🧠 Tech Stack

- **Backend & UI:** Python + Streamlit  
- **Database:** Supabase (PostgreSQL)  
- **DB Connection:** psycopg  
- **Environment Management:** python-dotenv  

---

## 📂 Project Structure

attendance-app/
│
├── app.py # Main Streamlit app
├── auth.py # Authentication logic (login, hashing)
├── db.py # Database connection & queries
├── export_utils.py # Export/report utilities
├── requirements.txt # Dependencies
├── .env.example # Example environment variables
└── .gitignore


---

## ⚙️ Setup

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd Work--Hours--Tracking-System


2. Install dependencies
  pip install -r requirements.txt

3. Configure environment variables
  Create a .env file based on .env.example:

DATABASE_URL=your_database_connection_string
AUTH_SECRET=your_secret_key
AUTH_USERNAME=your_username
AUTH_PASSWORD_HASH=your_password_hash

4. Run the app
  streamlit run app.py

🚀 Deployment

The app is designed to be easily deployed on platforms like Render.
Make sure to configure environment variables in your deployment settings.

##💡 Future Improvements
Role-based access (admin / user)
Row Level Security (RLS)
JWT-based authentication
UI/UX enhancements
Mobile responsiveness

🤍 About

This project was built as a practical full-stack application focusing on:

Real-world problem solving
Clean and modular architecture
Basic security implementation
Working with external databases
Deployment and environment management
