import streamlit as st
import sqlite3
import bcrypt
import smtplib
from email.message import EmailMessage
from twilio.rest import Client
from datetime import datetime
import pandas as pd
from contextlib import contextmanager

# ==============================================================
# PROFESSIONAL CLINIC MANAGEMENT SYSTEM — OPTIMIZED
# ==============================================================

# ---------------- CONFIGURATION ----------------
# Vendos vlerat reale te Streamlit Secrets ose .env
EMAIL_ADDRESS = st.secrets.get("EMAIL_USER", "email@yt.com")
EMAIL_PASSWORD = st.secrets.get("EMAIL_PASS", "fjalekalimi_app")
TWILIO_SID    = st.secrets.get("TWILIO_SID",   "sid_yt_ketu")
TWILIO_TOKEN  = st.secrets.get("TWILIO_TOKEN", "token_yt_ketu")
TWILIO_PHONE  = st.secrets.get("TWILIO_PHONE", "+123456789")

DB_PATH = "clinic_system.db"

# ================================================================
# NOTIFICATIONS
# ================================================================

class Notifications:
    """Dërgon email dhe SMS duke përdorur context managers për lidhjet."""

    @staticmethod
    def send_email(to_email: str, subject: str, content: str) -> bool:
        """Dërgon email; kthen True nëse ka sukses."""
        msg = EmailMessage()
        msg.set_content(content)
        msg["Subject"] = subject
        msg["From"]    = EMAIL_ADDRESS
        msg["To"]      = to_email
        try:
            # smtplib.SMTP_SSL si context manager — mbyll lidhjen automatikisht
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
            return True
        except Exception as e:
            st.error(f"Gabim email: {e}")
            return False

    @staticmethod
    def send_sms(to_phone: str, body: str) -> bool:
        """Dërgon SMS; kthen True nëse ka sukses."""
        try:
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            client.messages.create(from_=TWILIO_PHONE, body=body, to=to_phone)
            return True
        except Exception as e:
            st.error(f"Gabim SMS: {e}")
            return False


# ================================================================
# DATABASE
# ================================================================

# SQL-et e krijimit të tabelave — konstante, jo brenda funksioneve
_CREATE_TABLES_SQL = [
    """CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password BLOB NOT NULL,
        role     TEXT NOT NULL DEFAULT 'patient'
    )""",
    """CREATE TABLE IF NOT EXISTS patients (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        username   TEXT NOT NULL,
        full_name  TEXT,
        phone      TEXT,
        email      TEXT,
        birth_date TEXT,
        address    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS doctors (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        name      TEXT NOT NULL,
        specialty TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS appointments (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        patient TEXT NOT NULL,
        doctor  TEXT NOT NULL,
        date    TEXT NOT NULL,
        time    TEXT NOT NULL,
        notes   TEXT,
        status  TEXT NOT NULL DEFAULT 'Scheduled'
    )""",
    """CREATE TABLE IF NOT EXISTS records (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        patient      TEXT NOT NULL,
        doctor       TEXT NOT NULL,
        diagnosis    TEXT,
        prescription TEXT,
        date         TEXT NOT NULL
    )""",
]


class Database:
    """
    Menaxhon SQLite me:
    - Një lidhje të vetme (check_same_thread=False për Streamlit)
    - Context manager për cursor → commit/rollback automatik
    - Bcrypt për fjalëkalimet
    """

    def __init__(self, db_path: str = DB_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # akseso kolonat me emër
        self._create_tables()

    @contextmanager
    def _cursor(self):
        """Context manager: commit nëse gjithçka shkoi mirë, rollback nëse jo."""
        c = self.conn.cursor()
        try:
            yield c
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            c.close()

    def _create_tables(self):
        with self._cursor() as c:
            for sql in _CREATE_TABLES_SQL:
                c.execute(sql)

    # ---------- SECURITY ----------

    @staticmethod
    def _hash_pw(password: str) -> bytes:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    @staticmethod
    def _check_pw(password: str, hashed: bytes) -> bool:
        return bcrypt.checkpw(password.encode(), hashed)

    # ---------- USERS ----------

    def register(self, username: str, password: str, role: str = "patient") -> bool:
        """Regjistron përdorues të ri; kthen False nëse username ekziston."""
        try:
            with self._cursor() as c:
                c.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                    (username, self._hash_pw(password), role),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def login(self, username: str, password: str):
        """Kthen (username, role) nëse kredencialet janë të sakta, ose None."""
        with self._cursor() as c:
            c.execute(
                "SELECT username, password, role FROM users WHERE username = ?",
                (username,),
            )
            row = c.fetchone()
        if row and self._check_pw(password, row["password"]):
            return row["username"], row["role"]
        return None

    # ---------- PATIENTS ----------

    def save_patient(
        self, username: str, name: str, phone: str,
        email: str, birth: str, address: str,
    ):
        with self._cursor() as c:
            c.execute(
                """INSERT INTO patients
                   (username, full_name, phone, email, birth_date, address)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username, name, phone, email, birth, address),
            )

    def get_patient_info(self, username: str):
        """Kthen (phone, email) të pacientit të fundit."""
        with self._cursor() as c:
            c.execute(
                """SELECT phone, email FROM patients
                   WHERE username = ? ORDER BY id DESC LIMIT 1""",
                (username,),
            )
            return c.fetchone()

    def get_patients(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM patients", self.conn)

    # ---------- DOCTORS ----------

    def add_doctor(self, name: str, specialty: str):
        with self._cursor() as c:
            c.execute(
                "INSERT INTO doctors (name, specialty) VALUES (?, ?)",
                (name, specialty),
            )

    def get_doctors(self) -> list[str]:
        with self._cursor() as c:
            c.execute("SELECT name FROM doctors ORDER BY name")
            return [r["name"] for r in c.fetchall()]

    def get_doctors_full(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM doctors", self.conn)

    # ---------- APPOINTMENTS ----------

    def book(
        self, patient: str, doctor: str,
        date: str, time: str, notes: str,
    ):
        with self._cursor() as c:
            c.execute(
                """INSERT INTO appointments
                   (patient, doctor, date, time, notes, status)
                   VALUES (?, ?, ?, ?, ?, 'Scheduled')""",
                (patient, doctor, date, time, notes),
            )

    def get_appointments(self, patient: str | None = None) -> pd.DataFrame:
        if patient:
            return pd.read_sql_query(
                "SELECT * FROM appointments WHERE patient = ? ORDER BY date, time",
                self.conn, params=(patient,),
            )
        return pd.read_sql_query(
            "SELECT * FROM appointments ORDER BY date, time", self.conn
        )

    def get_appointments_for_doctor(self, doctor: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM appointments WHERE doctor = ? ORDER BY date, time",
            self.conn, params=(doctor,),
        )

    def update_appointment_status(self, appt_id: int, status: str):
        with self._cursor() as c:
            c.execute(
                "UPDATE appointments SET status = ? WHERE id = ?",
                (status, appt_id),
            )

    # ---------- MEDICAL RECORDS ----------

    def add_record(
        self, patient: str, doctor: str,
        diagnosis: str, prescription: str,
    ):
        with self._cursor() as c:
            c.execute(
                """INSERT INTO records
                   (patient, doctor, diagnosis, prescription, date)
                   VALUES (?, ?, ?, ?, ?)""",
                (patient, doctor, diagnosis, prescription,
                 datetime.now().strftime("%Y-%m-%d")),
            )

    def get_records(self, patient: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM records WHERE patient = ? ORDER BY date DESC",
            self.conn, params=(patient,),
        )

    # ---------- STATISTICS ----------

    def _count(self, table: str) -> int:
        with self._cursor() as c:
            c.execute(f"SELECT COUNT(*) AS n FROM {table}")
            return c.fetchone()["n"]

    def total_patients(self)     -> int: return self._count("patients")
    def total_doctors(self)      -> int: return self._count("doctors")
    def total_appointments(self) -> int: return self._count("appointments")


# ================================================================
# SESSION STATE HELPER
# ================================================================

def _init_session():
    defaults = {"logged": False, "user": None, "role": None}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


# ================================================================
# UI — SIDEBAR (Login / Register)
# ================================================================

def render_sidebar(db: Database):
    with st.sidebar:
        st.title("🏥 Clinic Pro")

        if not st.session_state.logged:
            mode = st.radio("Llogaria", ["Login", "Regjistrohu"])
            username = st.text_input("Username")
            password = st.text_input("Fjalëkalimi", type="password")

            if mode == "Regjistrohu":
                role = st.selectbox("Roli", ["patient", "doctor", "admin"])
                if st.button("Krijo llogari"):
                    if not username or not password:
                        st.warning("Plotëso të gjitha fushat.")
                    elif db.register(username, password, role):
                        st.success("Llogaria u krijua! Mund të hysh tani.")
                    else:
                        st.error("Ky username ekziston.")
            else:
                if st.button("Hyr"):
                    result = db.login(username, password)
                    if result:
                        st.session_state.logged = True
                        st.session_state.user   = result[0]
                        st.session_state.role   = result[1]
                        st.rerun()
                    else:
                        st.error("Username ose fjalëkalim i gabuar.")
        else:
            st.success(f"👤 {st.session_state.user}")
            st.caption(f"Roli: **{st.session_state.role}**")
            if st.button("🚪 Dil"):
                for k in ("logged", "user", "role"):
                    st.session_state[k] = None
                st.session_state.logged = False
                st.rerun()


# ================================================================
# UI — PATIENT DASHBOARD
# ================================================================

def render_patient(db: Database, notifier: Notifications):
    st.title("🧑‍⚕️ Paneli i Pacientit")
    tab1, tab2, tab3 = st.tabs(["📋 Profili", "📅 Rezervo Takim", "📂 Historia Mjekësore"])

    with tab1:
        st.subheader("Të Dhënat Personale")
        with st.form("profile_form"):
            name    = st.text_input("Emër Mbiemër")
            phone   = st.text_input("Telefon (p.sh. +355...)")
            email   = st.text_input("Email")
            birth   = st.date_input("Datëlindja")
            address = st.text_input("Adresa")
            if st.form_submit_button("💾 Ruaj Profilin"):
                if not name or not phone or not email:
                    st.warning("Plotëso emrin, telefonin dhe emailin.")
                else:
                    db.save_patient(
                        st.session_state.user, name, phone,
                        email, str(birth), address,
                    )
                    st.success("Profili u ruajt!")

    with tab2:
        st.subheader("Rezervo Orar")
        docs = db.get_doctors()
        if not docs:
            st.info("Nuk ka doktorë të regjistruar ende.")
        else:
            with st.form("book_form"):
                doc    = st.selectbox("Zgjidh Doktorin", docs)
                d_date = st.date_input("Data", min_value=datetime.today())
                d_time = st.time_input("Ora")
                notes  = st.text_area("Shënime (opsionale)")
                if st.form_submit_button("✅ Konfirmo Rezervimin"):
                    db.book(
                        st.session_state.user, doc,
                        str(d_date), str(d_time), notes,
                    )
                    info = db.get_patient_info(st.session_state.user)
                    if info:
                        msg = (f"I nderuar pacient, takimi juaj me Dr. {doc} "
                               f"u konfirmua për {d_date} ora {d_time}.")
                        notifier.send_email(info["email"], "Konfirmim Takimi", msg)
                        notifier.send_sms(info["phone"],
                                          f"Klinika: Takimi u rezervua më {d_date} ora {d_time}.")
                    st.success("Rezervimi u krye! Njoftimet u dërguan.")

        st.divider()
        st.subheader("Takimet e Mia")
        appts = db.get_appointments(st.session_state.user)
        if appts.empty:
            st.info("Nuk ke takime të rezervuara.")
        else:
            st.dataframe(appts, use_container_width=True)

    with tab3:
        st.subheader("Historia Mjekësore")
        records = db.get_records(st.session_state.user)
        if records.empty:
            st.info("Nuk ka rekorde mjekësore.")
        else:
            st.dataframe(records, use_container_width=True)


# ================================================================
# UI — DOCTOR DASHBOARD
# ================================================================

def render_doctor(db: Database):
    st.title("🩺 Paneli i Doktorit")
    tab1, tab2 = st.tabs(["📅 Takimet e Mia", "📝 Shto Rekord Mjekësor"])

    with tab1:
        appts = db.get_appointments_for_doctor(st.session_state.user)
        if appts.empty:
            st.info("Nuk ke takime të caktuara.")
        else:
            st.dataframe(appts, use_container_width=True)
            st.subheader("Ndrysho Status")
            appt_id = st.number_input("ID e takimit", min_value=1, step=1)
            new_status = st.selectbox("Statusi i ri",
                                      ["Scheduled", "Completed", "Cancelled"])
            if st.button("Përditëso"):
                db.update_appointment_status(int(appt_id), new_status)
                st.success("Statusi u përditësua!")
                st.rerun()

    with tab2:
        st.subheader("Shto Rekord për Pacientin")
        with st.form("record_form"):
            patient      = st.text_input("Username i Pacientit")
            diagnosis    = st.text_area("Diagnoza")
            prescription = st.text_area("Receta")
            if st.form_submit_button("💾 Ruaj Rekordin"):
                if not patient or not diagnosis:
                    st.warning("Plotëso pacientin dhe diagnozën.")
                else:
                    db.add_record(patient, st.session_state.user,
                                  diagnosis, prescription)
                    st.success("Rekordi u ruajt!")


# ================================================================
# UI — ADMIN DASHBOARD
# ================================================================

def render_admin(db: Database):
    st.title("⚙️ Admin Dashboard")

    col1, col2, col3 = st.columns(3)
    col1.metric("👥 Pacientë",  db.total_patients())
    col2.metric("🩺 Doktorë",   db.total_doctors())
    col3.metric("📅 Takime",    db.total_appointments())

    st.divider()
    tab1, tab2, tab3 = st.tabs(["➕ Shto Doktor", "📋 Lista Pacientëve", "📅 Të gjitha Takimet"])

    with tab1:
        with st.form("add_doctor_form"):
            name = st.text_input("Emri i Doktorit")
            spec = st.text_input("Specialiteti")
            if st.form_submit_button("➕ Shto"):
                if not name or not spec:
                    st.warning("Plotëso të dyja fushat.")
                else:
                    db.add_doctor(name, spec)
                    st.success(f"Dr. {name} u shtua!")

        st.subheader("Doktorët aktualë")
        st.dataframe(db.get_doctors_full(), use_container_width=True)

    with tab2:
        st.dataframe(db.get_patients(), use_container_width=True)

    with tab3:
        st.dataframe(db.get_appointments(), use_container_width=True)


# ================================================================
# MAIN
# ================================================================

def main():
    st.set_page_config(
        page_title="Pro Clinic System",
        page_icon="🏥",
        layout="wide",
    )

    _init_session()

    # Inicializo objektet një herë duke përdorur st.cache_resource
    db       = _get_db()
    notifier = Notifications()

    render_sidebar(db)

    if not st.session_state.logged:
        st.header("🏥 Sistemi i Menaxhimit të Klinikës")
        st.info("Ju lutem hyni në sistem për të vazhduar.")
        return

    role = st.session_state.role
    if role == "patient":
        render_patient(db, notifier)
    elif role == "doctor":
        render_doctor(db)
    elif role == "admin":
        render_admin(db)
    else:
        st.error(f"Rol i panjohur: {role}")


@st.cache_resource
def _get_db() -> Database:
    """Krijon Database një herë dhe e ri-përdor për gjithë sesionin."""
    return Database()


if __name__ == "__main__":
    main()
