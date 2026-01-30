
from flask import Flask, request, jsonify
from flask_cors import CORS
import razorpay
import pymysql
from flask_mail import Mail, Message
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.background import BackgroundScheduler
from config import Config   

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configure logging with RotatingFileHandler
log_handler = RotatingFileHandler('payment_service.log', maxBytes=1000000, backupCount=5)
log_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)
app.logger.addHandler(log_handler)
app.logger.setLevel(logging.DEBUG)

# ✅ MySQL connection configurations (using Config)
pay_dcfg = {
    "mysql": {
        "host": Config.MYSQL_HOST,
        "user": Config.MYSQL_USER,
        "passwd": Config.PASSWORD,
        "db": Config.MYSQL_DB_PAYMENT ,
        "port": Config.PORT
    }
}
ielts_dcfg = {
    "mysql": {
        "host": Config.MYSQL_HOST,
        "user": Config.MYSQL_USER,
        "passwd": Config.PASSWORD,
        "db": Config.MYSQL_DB_IELTS,
        "port": Config.PORT
    }
}

# Razorpay client initialization
razorpay_client = Config.razorpay_client


# ✅ Email configurations (using Config)
app.config['MAIL_SERVER'] = Config.MAIL_SERVER
app.config['MAIL_PORT'] = Config.MAIL_PORT
app.config['MAIL_USERNAME'] = Config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = Config.MAIL_PASSWORD
app.config['MAIL_USE_TLS'] = Config.MAIL_USE_TLS
app.config['MAIL_USE_SSL'] = Config.MAIL_USE_SSL
mail = Mail(app)

# Initialize scheduler  
scheduler = BackgroundScheduler()
scheduler.start()

# ✅ MySQL connection helper
def mysqlconnect(dcfg):
    app.logger.info("Attempting to connect to MySQL database: %s", dcfg["mysql"]["db"])
    try:
        return pymysql.connect(
            host=dcfg["mysql"]["host"],
            user=dcfg["mysql"]["user"],
            passwd=dcfg["mysql"]["passwd"],
            db=dcfg["mysql"]["db"],
            port=dcfg["mysql"]["port"]
        )
    except pymysql.Error as e:
        app.logger.error("Error connecting to MySQL: %s", e)
        return None
 
# Check if user has an active plan
def has_active_plan(user_id):
    ielts_db_connection = mysqlconnect(ielts_dcfg)
    if ielts_db_connection is None:
        return False
    try:
        cursor = ielts_db_connection.cursor()
        query = "SELECT plan_expiry, plan_status FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        if result:
            expiry_date, status = result
            current_date = datetime.now()
            if status == 'success' and expiry_date > current_date:
                return True  # User has an active plan
        return False  # No active plan
    except pymysql.Error as e:
        app.logger.error("MySQL error: %s", e)
        return False
    finally:
        if 'cursor' in locals() and cursor is not None:
            cursor.close()
        if 'ielts_db_connection' in locals() and ielts_db_connection is not None:
            ielts_db_connection.close()
 
# Check plan status endpoint
@app.route('/check_plan_status', methods=['GET'])
def check_plan_status():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id parameter is required"}), 400
    return jsonify({"status": "active" if has_active_plan(user_id) else "inactive"})
 
# Create payment order endpoint
@app.route('/create_order', methods=['POST'])
def create_order():
    app.logger.debug("Received request to create order")
    data = request.json
    user_id = data.get('user_id')
    order_amount = data.get('amount')
    currency = data.get('currency')
   
    # Check if user has an active plan
    if has_active_plan(user_id):
        app.logger.warning("User ID: %s has an active plan and cannot create a new order.", user_id)
        return jsonify({"error": "Sorry, you have an active plan. You cannot create a new order."}), 403
    try:
        order = razorpay_client.order.create({
            "amount": order_amount,
            "currency": currency,
            "payment_capture": '1'
        })
        app.logger.info("Order created successfully with ID: %s", order['id'])
        return jsonify(order_id=order['id'])
    except Exception as e:
        app.logger.error("Error creating order: %s", e)
        return jsonify({"error": "Failed to create order"}), 500
 
# Payment success endpoint
@app.route('/payment_success', methods=['POST'])
def payment_success():
    app.logger.debug("Received payment success notification")
    try:
        if not request.is_json:
            app.logger.error("Request is not JSON")
            return jsonify({"error": "Request must be JSON"}), 400
 
        payment_data = request.json
        app.logger.debug(f"Payment data received: {payment_data}")
 
        # Require payment_id, user_id, and plan_id
        required_keys = ['payment_id', 'user_id', 'plan_id']
        for key in required_keys:
            if key not in payment_data:
                app.logger.error(f"Missing required field: {key}")
                return jsonify({"error": f"Missing required field: {key}"}), 400
 
        payment_id = payment_data['payment_id']
        user_id = payment_data['user_id']
        plan_id = payment_data['plan_id']
 
        # Retrieve order_id if not provided
        order_id = payment_data.get('order_id')
        if not order_id:
            try:
                app.logger.info("Order ID not provided in payload, fetching from Razorpay for payment_id: %s", payment_id)
                payment_details = razorpay_client.payment.fetch(payment_id)
                order_id = payment_details.get('order_id')
                if not order_id:
                    app.logger.error("Order ID not found in fetched payment details")
                    return jsonify({"error": "Order ID not found"}), 400
            except Exception as e:
                app.logger.error("Error fetching payment details: %s", e)
                return jsonify({"error": "Error fetching payment details"}), 500
 
        # Handle signature; verify if provided
        signature = payment_data.get('signature')
        if signature:
            try:
                razorpay_client.utility.verify_payment_signature({
                    'razorpay_order_id': order_id,
                    'razorpay_payment_id': payment_id,
                    'razorpay_signature': signature
                })
            except razorpay.errors.SignatureVerificationError as e:
                app.logger.error(f"Signature verification failed: {e}")
                return jsonify({"error": "Invalid signature"}), 400
        else:
            app.logger.warning("Signature not provided; skipping verification.")
 
        # Fetch email and center_code from ielts_database.users
        ielts_db_connection = mysqlconnect(ielts_dcfg)
        if ielts_db_connection is None:
            return jsonify({"error": "Database connection failed"}), 500
        ielts_cursor = ielts_db_connection.cursor()
        user_query = "SELECT email, center_code FROM users WHERE id = %s"
        ielts_cursor.execute(user_query, (user_id,))
        result = ielts_cursor.fetchone()
        if not result:
            app.logger.error("User ID: %s not found in database", user_id)
            return jsonify({"error": "User not found"}), 404
        user_email, center_code = result
 
        # Log center_code usage
        if center_code:
            app.logger.info("Using center_code: %s for user ID: %s", center_code, user_id)
        else:
            app.logger.info("No center_code for user ID: %s", user_id)
 
        # Calculate expiry date
        expiry_map = {
            'prod_7DaysPlan': timedelta(days=7),
            'prod_1MonthPlan': timedelta(days=30),
            'prod_3MonthPlan': timedelta(days=90),
            'prod_6MonthPlan': timedelta(days=180),
        }
        expiry_date = datetime.now() + expiry_map.get(plan_id, timedelta())
        created_at = datetime.now()
        status = 'success'
 
        # Insert payment details into ielts_payment.payment_details
        pay_db_connection = mysqlconnect(pay_dcfg)
        if pay_db_connection is None:
            return jsonify({"error": "Database connection failed"}), 500
        pay_cursor = pay_db_connection.cursor()
        pay_query = """
            INSERT INTO payment_details
            (payment_id, order_id, signature, user_id, plan_id, expiry_date, created_at, status, center_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        pay_cursor.execute(pay_query, (payment_id, order_id, signature, str(user_id), plan_id, expiry_date, created_at, status, center_code))
        pay_db_connection.commit()
        pay_cursor.close()  # Close cursor only, not the connection
 
        # Send thank-you email if email is available
        if user_email:
            msg = Message('Thank You for Your Purchase',
                          sender=Config.MAIL_USERNAME,
                          recipients=[user_email])
            msg.html = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; margin: 0; padding: 0;}
                    .container {max-width: 600px; margin: 20px auto; padding: 20px; background-color: #fff; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
                    .header {text-align: center; padding: 10px 0; background-color: #4CAF50; color: #fff; border-radius: 8px 8px 0 0;}
                    .content {padding: 20px;}
                    .footer {font-size: 0.8em; text-align: center; color: #999; margin-top: 20px;}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>Thank You for Your Purchase!</h2>
                    </div>
                    <div class="content">
                        <p>Hi,</p>
                        <p>Thank you for being a member of <strong>IELTSGenAI</strong>.</p>
                        <p>Learn the courses and leverage your skills.</p>
                        <p>Thank you!</p>
                    </div>
                    <div class="footer">
                        <p>Regards,<br>IELTSGenAI</p>
                    </div>
                </div>
            </body>
            </html>
            """
            mail.send(msg)
            app.logger.info("Thank you email sent to: %s", user_email)
 
        # Update user's plan details in ielts_database.users
        ielts_query = """
            UPDATE users
            SET plan_id = %s, plan_expiry = %s, plan_status = %s, payment_created_at = %s
            WHERE id = %s
        """
        ielts_cursor.execute(ielts_query, (plan_id, expiry_date, status, created_at, user_id))
        ielts_db_connection.commit()
        app.logger.info("User details updated in ielts_database for user ID: %s", user_id)
 
        return jsonify({"message": "Payment and user details updated successfully"})
 
    except pymysql.Error as e:
        app.logger.error("MySQL error: %s", e)
        return jsonify({"error": f"MySQL error: {e}"}), 500
    except Exception as e:
        app.logger.error("General error: %s", e)
        return jsonify({"error": f"General error: {e}"}), 500
    finally:
        # Close connections only once, here in the finally block
        if 'pay_db_connection' in locals() and pay_db_connection is not None:
            pay_db_connection.close()
        if 'ielts_db_connection' in locals() and ielts_db_connection is not None:
            ielts_db_connection.close()
 
# User profile endpoint
@app.route('/user_profile', methods=['GET'])
def user_profile():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id parameter is required"}), 400
    ielts_db_connection = mysqlconnect(ielts_dcfg)
    if ielts_db_connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cursor = ielts_db_connection.cursor()
        query = "SELECT username, email, plan_expiry, plan_status FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        if result:
            username, email, plan_expiry, plan_status = result
            current_date = datetime.now()
            remaining_days = 0
            if plan_status == 'success' and plan_expiry and plan_expiry > current_date:
                remaining_days = (plan_expiry - current_date).days
            return jsonify({
                "user_id": user_id,
                "username": username,
                "email": email,
                "remaining_days": remaining_days,
                "plan_status": plan_status
            })
        else:
            return jsonify({"error": "User not found"}), 404
    except Exception as e:
        app.logger.error("Error retrieving user profile: %s", e)
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor is not None:
            cursor.close()
        if ielts_db_connection is not None:
            ielts_db_connection.close()
 
# Plan notification checker
def check_plan_notifications():
    try:
        db = mysqlconnect(ielts_dcfg)
        if db is None:
            app.logger.error("Database connection failed for notifications.")
            return
        cursor = db.cursor()
        query = "SELECT id, email, plan_expiry, plan_status FROM users WHERE plan_expiry IS NOT NULL AND plan_status = 'success'"
        cursor.execute(query)
        results = cursor.fetchall()
        current_date = datetime.now()
        for user in results:
            user_id, email, plan_expiry, plan_status = user
            if plan_expiry is None:
                continue
            remaining_days = (plan_expiry - current_date).days
            if remaining_days == 2:
                msg = Message('Reminder: Your plan expires soon',
                              sender=Config.MAIL_USERNAME,
                              recipients=[email])
                msg.html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f9f9f9;}
                        .container {max-width: 600px; margin: 20px auto; padding: 20px; background-color: #fff; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);}
                        .header {text-align: center; padding: 10px 0; background-color: #4CAF50; color: white; border-radius: 8px 8px 0 0;}
                        .content {padding: 20px;}
                        .footer {font-size: 0.8em; text-align: center; color: #999; margin-top: 20px;}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h2>Subscription Expiry Notice</h2>
                        </div>
                        <div class="content">
                            <p>Hi,</p>
                            <p>Your subscription with <strong>IELTSGenAI</strong> is expiring in <strong>2 days</strong>. To continue enjoying uninterrupted access, please renew your plan.</p>
                            <p>Thank you!</p>
                        </div>
                        <div class="footer">
                            <p>Regards,<br>IELTSGenAI</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                mail.send(msg)
                app.logger.info("Sent 2-day reminder email to: %s", email)
            elif remaining_days <= 0:
                msg = Message('Notice: Your plan has expired',
                              sender=Config.MAIL_USERNAME,
                              recipients=[email])
                msg.html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f9f9f9;}
                        .container {max-width: 600px; margin: 20px auto; padding: 20px; background-color: #fff; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);}
                        .header {text-align: center; padding: 10px 0; background-color: #d9534f; color: white; border-radius: 8px 8px 0 0;}
                        .content {padding: 20px;}
                        .footer {font-size: 0.8em; text-align: center; color: #999; margin-top: 20px;}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h2>Subscription Expired</h2>
                        </div>
                        <div class="content">
                            <p>Hi,</p>
                            <p>Your subscription with <strong>IELTSGenAI</strong> has expired. To continue enjoying our services, please renew your plan.</p>
                            <p>Thank you!</p>
                        </div>
                        <div class="footer">
                            <p>Regards,<br>IELTSGenAI</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                mail.send(msg)
                app.logger.info("Sent expiry notification email to: %s", email)
        cursor.close()
        db.close()
    except Exception as e:
        app.logger.error("Error while checking plan notifications: %s", e)
       
    # New endpoint to manually trigger plan notifcations
@app.route('/trigger_notifications', methods=['GET'])
def trigger_notifications():
    """
    Endpoint to manually trigger the check_plan_notifications function.
    This can be useful for testing or on-demand notifications.
    """
    try:
        check_plan_notifications()
        return jsonify({"message": "Notifications triggered successfully"}), 200
    except Exception as e:
        app.logger.error("Error triggering notifications: %s", e)
        return jsonify({"error": str(e)}), 500
 
# Schedule the check_plan_notifications function to run every day
scheduler.add_job(lambda: check_plan_notifications(), 'interval', hours=24)
 
if __name__ == '__main__':
    app.run(port=5000, host="0.0.0.0", debug=True)
 