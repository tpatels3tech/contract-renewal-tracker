import os
import re
import sqlite3
from datetime import datetime, timedelta
import fitz  # PyMuPDF
import smtplib
from email.mime.text import MIMEText
import streamlit as st

# --- CONFIGURATION ---
PDF_FOLDER = "./contracts"
DB_FILE = "contracts.db"
NOTIFY_DAYS_BEFORE = 30
EMAIL_SENDER = "your_email@example.com"
EMAIL_RECEIVER = "receiver@example.com"
SMTP_SERVER = "smtp.example.com"
SMTP_PORT = 587
SMTP_USERNAME = "your_email@example.com"
SMTP_PASSWORD = "your_password"

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            renewal_date TEXT,
            notified INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# --- PDF PARSING ---
def extract_renewal_date(text):
    date_patterns = [
        r"renewal date[:\s]*([A-Za-z]+ \d{1,2}, \d{4})",
        r"expires on[:\s]*([A-Za-z]+ \d{1,2}, \d{4})",
        r"renewal date[:\s]*(\d{4}-\d{2}-\d{2})",
        r"expires on[:\s]*(\d{4}-\d{2}-\d{2})"
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return datetime.strptime(match.group(1), "%B %d, %Y")
            except:
                try:
                    return datetime.strptime(match.group(1), "%Y-%m-%d")
                except:
                    continue
    return None

def parse_pdfs():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for filename in os.listdir(PDF_FOLDER):
        if filename.endswith(".pdf"):
            filepath = os.path.join(PDF_FOLDER, filename)
            doc = fitz.open(filepath)
            text = "\n".join(page.get_text() for page in doc)
            renewal_date = extract_renewal_date(text)
            if renewal_date:
                cursor.execute("SELECT * FROM contracts WHERE filename = ?", (filename,))
                if cursor.fetchone() is None:
                    cursor.execute("INSERT INTO contracts (filename, renewal_date) VALUES (?, ?)",
                                   (filename, renewal_date.strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

# --- NOTIFICATION ---
def send_notification(filename, renewal_date):
    msg = MIMEText(f"Contract '{filename}' is due for renewal on {renewal_date}.")
    msg['Subject'] = f"Contract Renewal Reminder: {filename}"
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

def check_and_notify():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    today = datetime.today()
    notify_date = today + timedelta(days=NOTIFY_DAYS_BEFORE)

    cursor.execute("SELECT id, filename, renewal_date FROM contracts WHERE notified = 0")
    for contract_id, filename, renewal_date_str in cursor.fetchall():
        renewal_date = datetime.strptime(renewal_date_str, "%Y-%m-%d")
        if today <= renewal_date <= notify_date:
            send_notification(filename, renewal_date_str)
            cursor.execute("UPDATE contracts SET notified = 1 WHERE id = ?", (contract_id,))

    conn.commit()
    conn.close()

# --- STREAMLIT DASHBOARD ---
def run_dashboard():
    st.title("Contract Renewal Tracker")

    if st.button("Parse PDFs"):
        parse_pdfs()
        st.success("PDFs parsed and contracts updated.")

    if st.button("Run Notification Check"):
        check_and_notify()
        st.success("Notifications checked.")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT filename, renewal_date, notified FROM contracts")
    data = cursor.fetchall()
    conn.close()

    if data:
        st.subheader("Tracked Contracts")
        for filename, renewal_date, notified in data:
            st.write(f"**{filename}** - Renewal Date: {renewal_date} - Notified: {'Yes' if notified else 'No'}")
    else:
        st.info("No contracts found.")

# --- MAIN LOGIC ---
if __name__ == "__main__":
    init_db()
    run_dashboard()
