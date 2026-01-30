# razorpay Payment Service

A Flask-based payment service for managing subscription plans, payments, and user notifications for the  razorpay platform.

## System Architecture

### Core Components
- **Flask Application**: Main web service handling payment operations
- **Razorpay Integration**: Payment gateway for processing transactions
- **MySQL Databases**: Dual database architecture for payment and user data
- **Email Service**: Automated notifications and confirmations
- **Background Scheduler**: Automated plan expiry notifications
- **Docker Containerization**: Deployment and environment management

### Database Architecture
- **ielts_payment.payment_details**: Stores payment transactions and plan details
- **ielts_database.users**: Manages user profiles and subscription status

## Business Logic

### Payment Flow
1. **Plan Status Check**: Validates if user has active subscription before allowing new purchases
2. **Order Creation**: Creates Razorpay order with amount validation and active plan prevention
3. **Payment Processing**: Handles payment success with signature verification and dual database updates
4. **User Profile Updates**: Updates subscription status, expiry dates, and plan details
5. **Email Notifications**: Sends confirmation emails upon successful payment

### Subscription Management
- **Plan Types**: 7-day, 1-month, 3-month, and 6-month plans
- **Expiry Calculation**: Automatic calculation based on plan type
- **Status Tracking**: Real-time plan status and remaining days calculation
- **Center Code Support**: Optional center code tracking for user assignments

### Notification System
- **Welcome Emails**: Sent immediately after successful payment
- **Expiry Reminders**: Automated 2-day advance warning emails
- **Expiry Notifications**: Sent when plans expire
- **Daily Scheduler**: Background job checking all users for notification triggers

## Technical Implementation

### Security Features
- **Signature Verification**: Razorpay webhook signature validation
- **Active Plan Prevention**: Blocks duplicate purchases for active subscribers
- **Database Transaction Safety**: Proper connection handling and error management
- **Input Validation**: Required field validation and type checking

### Error Handling
- **Database Connection Failures**: Graceful handling with proper error responses
- **Payment Gateway Errors**: Comprehensive error logging and user feedback
- **Email Service Failures**: Non-blocking email operations with logging
- **Signature Verification**: Secure payment validation with fallback options

### Logging System
- **Rotating File Handler**: Automatic log rotation with size limits
- **Comprehensive Logging**: All operations logged with timestamps and levels
- **Debug Information**: Detailed request/response logging for troubleshooting

## Configuration Management

### Environment Variables
```
MYSQL_HOST, MYSQL_USER, PASSWORD, MYSQL_PORT
MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
MONGO_URI
```

### Database Configuration
- **Payment Database**: ielts_payment
- **User Database**: ielts_database
- **Connection Pooling**: Separate connections for different operations

## API Endpoints

### 1️⃣ Check Plan Status
**GET** `http://localhost:5000/check_plan_status?user_id=1`

**Logic**: Queries user database to check if current user has active subscription based on expiry date and status.

### 2️⃣ Create Order
**POST** `http://localhost:5000/create_order`

**Body**:
```json
{
  "user_id": "1",
  "amount": 50000,
  "currency": "INR"
}
```

**Logic**: 
- Validates user doesn't have active plan
- Creates Razorpay order with specified amount
- Returns order ID for frontend payment processing

### 3️⃣ Payment Success
**POST** `http://localhost:5000/payment_success`

**Body**:
```json
{
  "payment_id": "pay_L6w1c7Y9dO9a2h",
  "order_id": "order_L6vYQ3x9K7P9Xf",
  "signature": "your_razorpay_signature_here",
  "user_id": "1",
  "plan_id": "prod_7DaysPlan"
}
```

**Logic**:
- Verifies payment signature (if provided)
- Calculates plan expiry based on plan type
- Updates payment database with transaction details
- Updates user database with new subscription status
- Sends confirmation email to user
- Handles center code assignment if applicable

### 4️⃣ User Profile
**GET** `http://localhost:5000/user_profile?user_id=1`

**Response**:
```json
{
  "user_id": "1",
  "username": "Deepak",
  "email": "deepak@example.com",
  "remaining_days": 5,
  "plan_status": "success"
}
```

**Logic**: Retrieves user details and calculates remaining subscription days in real-time.

### 5️⃣ Trigger Notifications
**GET** `http://localhost:5000/trigger_notifications`

**Logic**: Manually triggers the notification system to check all users for expiry reminders and notifications.

## Deployment

### Docker Configuration
- **Base Image**: Python latest
- **Port Exposure**: 5000
- **Log Directory**: /app/logs
- **Environment**: Production-ready with unbuffered output

### CI/CD Pipeline
- **Build Stage**: Docker image creation and registry push
- **Test Stage**: Automated testing (configurable)
- **Release Stage**: Tagged image deployment
- **Deploy Stage**: Automated deployment trigger

## Plan Types and Expiry Logic

```python
expiry_map = {
    'prod_7DaysPlan': timedelta(days=7),
    'prod_1MonthPlan': timedelta(days=30),
    'prod_3MonthPlan': timedelta(days=90),
    'prod_6MonthPlan': timedelta(days=180),
}
```

## Notification Schedule
- **Daily Check**: Background scheduler runs every 24 hours
- **2-Day Warning**: Emails sent when 2 days remain
- **Expiry Notice**: Emails sent when plan expires
- **HTML Templates**: Styled email templates for professional communication


