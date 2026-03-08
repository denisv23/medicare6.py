import streamlit as st
import sqlite3
import bcrypt
import smtplib
from email.message import EmailMessage
from twilio.rest import Client
from datetime import datetime
import pandas as pd
import os

# ==============================================================
# PROFESSIONAL CLINIC MANAGEMENT SYSTEM (SECURED & INTEGRATED)
# ============================================================== 

# ---------------- CONFIGURATION & SECRETS ----------------
# Shënim: Në një ambient real, këto vlera vendosen te "Secrets" në Streamlit ose skedar .env
EMAIL_ADDRESS = st.secrets.get("EMAIL_USER", "email@yt.com")
EMAIL_PASSWORD = st.secrets.get("EMAIL_PASS", "fjalekalimi_app")
TWILIO_SID = st.secrets.get("TWILIO_SID", "sid_yt_ketu")
TWILIO_TOKEN = st.secrets.get("TWILIO_TOKEN", "token_yt_ketu")
TWILIO_PHONE = st.secrets.get("TWILIO_PHONE", "+123456789")

# ---------------- NOTIFICATION SYSTEM ----------------

class Notifications:
    @staticmethod
    def send_email(to_email, subject, content):
        msg = EmailMessage()
        msg.set_content(content)
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        try:
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            st.error(f"Gabim në dërgimin e email-it: {e}")

    @staticmethod
    def send_sms(to_phone, body):
        try:
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            client.messages.create(from_=TWILIO_PHONE, body=body, to=to_phone)
        except Exception as e:
            st.error(f"Gabim në dërgimin e SMS: {e}")

# ---------------- DATABASE ----------------

class Database:
    def __init__(self, db="clinic_system.db"):
        self.conn = sqlite3.connect(db, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        c = self.conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, full_name TEXT, phone TEXT, email TEXT, birth_date TEXT, address TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS doctors(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, specialty TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY AUTOINCREMENT, patient TEXT, doctor TEXT, date TEXT, time TEXT, notes TEXT, status TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY AUTOINCREMENT, patient TEXT, doctor TEXT, diagnosis TEXT, prescription TEXT, date TEXT)")
        self.conn.commit()

    # ---------- SECURITY (BCRYPT) ----------
    def hash_pw(self, password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    def check_pw(self, password, hashed):
        return bcrypt.checkpw(password.encode('utf-8'), hashed)

    # ---------- USERS ----------
    def register(self, username, password, role="patient"):
        c = self.conn.cursor()
        try:
            hashed = self.hash_pw(password)
            c.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)", (username, hashed, role))
            self.conn.commit()
            return True
        except:
            return False

    def login(self, username, password):
        c = self.conn.cursor()
        c.execute("SELECT username, password, role FROM users WHERE username=?", (username,))
        user = c.fetchone()
        if user and self.check_pw(password, user[1]):
            return (user[0], user[2])
        return None

    # ---------- PATIENTS ----------
    def save_patient(self, username, name, phone, email, birth, address):
        c = self.conn.cursor()
        c.execute("INSERT INTO patients(username,full_name,phone,email,birth_date,address) VALUES(?,?,?,?,?,?)", 
                  (username, name, phone, email, birth, address))
        self.conn.commit()

    def get_patient_info(self, username):
        c = self.conn.cursor()
        c.execute("SELECT phone, email FROM patients WHERE username=? ORDER BY id DESC LIMIT 1", (username,))
        return c.fetchone()

    def get_patients(self):
        return pd.read_sql_query("SELECT * FROM patients", self.conn)

    # ---------- DOCTORS & APPOINTMENTS ----------
    def add_doctor(self, name, specialty):
        c = self.conn.cursor()
        c.execute("INSERT INTO doctors(name,specialty) VALUES(?,?)", (name, specialty))
        self.conn.commit()

    def get_doctors(self):
        c = self.conn.cursor()
        c.execute("SELECT name FROM doctors")
        return [x[0] for x in c.fetchall()]

    def book(self, patient, doctor, date, time, notes):
        c = self.conn.cursor()
        c.execute("INSERT INTO appointments(patient,doctor,date,time,notes,status) VALUES(?,?,?,?,?,?)",
                  (patient, doctor, date, time, notes, "Scheduled"))
        self.conn.commit()

    # (Funksionet e tjera mbeten njëlloj si në kodin tënd fillestar...)
    def total_patients(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM patients")
        return c.fetchone()[0]
    
    def total_doctors(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM doctors")
        return c.fetchone()[0]

    def total_appointments(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM appointments")
        return c.fetchone()[0]

# ---------------- APP SETUP ----------------
st.set_page_config(page_title="Pro Clinic System", page_icon="🏥", layout="wide")

db = Database()
notifier = Notifications()

# Session State
if "logged" not in st.session_state: st.session_state.logged = False
if "user" not in st.session_state: st.session_state.user = None
if "role" not in st.session_state: st.session_state.role = None

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.title("🏥 Clinic Pro")
    if not st.session_state.logged:
        mode = st.radio("Llogaria", ["Login", "Register"])
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if mode == "Register":
            r = st.selectbox("Roli", ["patient", "doctor", "admin"])
            if st.button("Krijo"):
                if db.register(u, p, r): st.success("U krijua!")
                else: st.error("Ekziston!")
        else:
            if st.button("Hyr"):
                user = db.login(u, p)
                if user:
                    st.session_state.logged, st.session_state.user, st.session_state.role = True, user[0], user[1]
                    st.rerun()
                else: st.error("Gabim!")
    else:
        st.success(f"Mirëseerdhe, {st.session_state.user}")
        if st.button("Logout"):
            st.session_state.logged = False
            st.rerun()

# ---------------- DASHBOARDS ----------------

if st.session_state.logged and st.session_state.role == "patient":
    st.title("Paneli i Pacientit")
    tab1, tab2 = st.tabs(["Profili", "Rezervo Takim"])
    
    with tab1:
        st.subheader("Të dhënat Personale")
        name = st.text_input("Emër Mbiemër")
        phone = st.text_input("Tel (p.sh +355...)")
        email = st.text_input("Email")
        birth = st.date_input("Datëlindja")
        if st.button("Ruaj Profilin"):
            db.save_patient(st.session_state.user, name, phone, email, str(birth), "Adresa")
            st.success("U ruajt!")

    with tab2:
        st.subheader("Rezervo një orar")
        docs = db.get_doctors()
        if docs:
            doc = st.selectbox("Zgjidh Doktorin", docs)
            d_date = st.date_input("Data")
            d_time = st.time_input("Ora")
            if st.button("Konfirmo Rezervimin"):
                db.book(st.session_state.user, doc, str(d_date), str(d_time), "Kontroll")
                
                # --- NJOFTIMET ---
                info = db.get_patient_info(st.session_state.user)
                if info:
                    p_phone, p_email = info
                    # Dërgo Email
                    notifier.send_email(p_email, "Konfirmim Takimi", f"I nderuar pacient, takimi juaj me Dr. {doc} u konfirmua për datën {d_date} ora {d_time}.")
                    # Dërgo SMS
                    notifier.send_sms(p_phone, f"Klinika: Takimi juaj u rezervua me sukses më {d_date}!")
                
                st.success("Rezervimi u krye dhe njoftimet u dërguan!")

elif st.session_state.logged and st.session_state.role == "admin":
    st.title("Admin Dashboard")
    col1, col2, col3 = st.columns(3)
    col1.metric("Pacientë", db.total_patients())
    col2.metric("Doktorë", db.total_doctors())
    col3.metric("Takime", db.total_appointments())
    
    name = st.text_input("Emri i Doktorit të ri")
    spec = st.text_input("Specialiteti")
    if st.button("Shto Doktor"):
        db.add_doctor(name, spec)
        st.success("Doktori u shtua!")

else:
    st.header("Sistemi i Menaxhimit të Klinikës")
    st.info("Ju lutem hyni në sistem për të vazhduar.")
