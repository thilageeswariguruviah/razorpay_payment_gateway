import os
import razorpay
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    # MySQL Config
    MYSQL_HOST = os.getenv("MYSQL_HOST")
    MYSQL_USER = os.getenv("MYSQL_USER")
    PASSWORD = os.getenv("PASSWORD")
    PORT = int(os.getenv("MYSQL_PORT", 3306))

    # SMTP / Mail Config
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_USE_TLS = True  # since you are using port 587
    MAIL_USE_SSL = False

    # Razorpay Config
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

    # Database names
    MYSQL_DB_PAYMENT = "payment"
    MYSQL_DB = "database"

    # MongoDB Config
    MONGO_URI = os.getenv("MONGO_URI")

