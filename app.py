import os
import uuid
import base64
import json
import cloudinary
import cloudinary.uploader
from ai.report_analyzer import analyze_report
from flask import Flask, render_template, request, redirect, url_for, session
from flask_wtf.csrf import CSRFProtect
from pywebpush import webpush, WebPushException
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models import (
    db,
    User,
    ItemReport,
    Claim,
    Notification,
    PushSubscription
)

from ai.match_engine import calculate_match
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
csrf = CSRFProtect(app)


# ============================================================
# CONFIGURATION
# ============================================================

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Use Render PostgreSQL when DATABASE_URL is available.
# Keep SQLite as a local fallback for development.
database_url = os.getenv(
    "DATABASE_URL",
    "sqlite:///lost_found.db"
)

# Render may provide postgres://
# SQLAlchemy expects postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.secret_key = os.getenv(
    "SECRET_KEY",
    "development-secret-key"
)

# Upload folder
app.config['UPLOAD_FOLDER'] = 'static/uploads'

os.makedirs(
    app.config['UPLOAD_FOLDER'],
    exist_ok=True
)


# ============================================================
# DATABASE
# ============================================================

db.init_app(app)

with app.app_context():
    db.create_all()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_current_user():

    """
    Get the currently logged-in user.
    """

    if 'user_id' not in session:
        return None

    return User.query.get(
        session['user_id']
    )


def admin_required():

    """
    Check whether the current user is an administrator.

    Returns:
        User object if the user is an Admin.
        None if the user is not logged in or is not an Admin.
    """

    user = get_current_user()

    if not user:
        return None

    if user.role != 'Admin':
        return None

    return user


def save_uploaded_image(image):

    """
    Upload image to Cloudinary and return
    the permanent secure image URL.
    """

    if not image or not image.filename:
        return None

    original_name = secure_filename(
        image.filename
    )

    if not original_name:
        return None

    try:

        result = cloudinary.uploader.upload(
            image,
            folder="smart-lost-found"
        )

        return result.get("secure_url")

    except Exception as e:

        print(
            "Cloudinary upload failed:",
            e
        )

        return None

# ============================================================
# PUSH NOTIFICATION
# ============================================================

def get_vapid_private_key():

    # --------------------------------------------------------
    # PRODUCTION: Render Environment Variable
    # --------------------------------------------------------

    vapid_key_base64 = os.getenv(
        "VAPID_PRIVATE_KEY_B64"
    )

    if vapid_key_base64:

        try:

            vapid_key_bytes = base64.b64decode(
                vapid_key_base64
            )

            vapid_key_path = os.path.join(
                app.instance_path,
                "vapid_private_key.pem"
            )

            os.makedirs(
                app.instance_path,
                exist_ok=True
            )

            with open(
                vapid_key_path,
                "wb"
            ) as key_file:

                key_file.write(
                    vapid_key_bytes
                )

            return vapid_key_path

        except Exception as e:

            print(
                "Error loading VAPID key from environment:",
                e
            )

            return None


    # --------------------------------------------------------
    # LOCAL DEVELOPMENT: private_key.pem
    # --------------------------------------------------------

    local_key_path = os.path.join(
        app.root_path,
        "private_key.pem"
    )

    if os.path.exists(
        local_key_path
    ):

        return local_key_path


    # --------------------------------------------------------
    # NO KEY AVAILABLE
    # --------------------------------------------------------

    print(
        "VAPID private key not found."
    )

    return None


# ============================================================
# SEND PUSH NOTIFICATION
# ============================================================

def send_push_notification(
    recipient_id,
    title,
    message
):

    subscriptions = PushSubscription.query.filter_by(
        user_id=recipient_id
    ).all()

    if not subscriptions:

        print(
            "No push subscription found for user:",
            recipient_id
        )

        return


    # --------------------------------------------------------
    # GET VAPID PRIVATE KEY
    # --------------------------------------------------------

    vapid_private_key = get_vapid_private_key()

    if not vapid_private_key:

        print(
            "Push notification skipped: VAPID key unavailable."
        )

        return


    # --------------------------------------------------------
    # SEND TO ALL USER DEVICES
    # --------------------------------------------------------

    for subscription in subscriptions:

        try:

            webpush(

                subscription_info={

                    "endpoint": subscription.endpoint,

                    "keys": {

                        "p256dh": subscription.p256dh,

                        "auth": subscription.auth

                    }

                },

                data=json.dumps({

                    "title": title,

                    "message": message

                }),

                vapid_private_key=vapid_private_key,

                vapid_claims={

                    "sub": "mailto:test@example.com"

                }

            )

            print(
                "Push notification sent to user:",
                recipient_id
            )


        except WebPushException as e:

            print(
                "Push notification error:",
                e
            )


        except Exception as e:

            print(
                "Push notification failed:",
                e
            )


# ============================================================
# CREATE DATABASE NOTIFICATION
# ============================================================

def create_notification(
    recipient_id,
    title,
    message,
    notification_type,
    item_id=None
):

    notification = Notification(

        recipient_id=recipient_id,

        title=title,

        message=message,

        notification_type=notification_type,

        item_id=item_id,

        is_read=False

    )

    db.session.add(
        notification
    )

    # --------------------------------------------------------
    # SEND BROWSER PUSH
    # --------------------------------------------------------

    send_push_notification(

        recipient_id=recipient_id,

        title=title,

        message=message

    )


# ============================================================
# SAVE PUSH SUBSCRIPTION
# ============================================================

@app.route(
    '/save-push-subscription',
    methods=['POST']
)
def save_push_subscription():

    # --------------------------------------------------------
    # CHECK LOGIN
    # --------------------------------------------------------

    if 'user_id' not in session:

        return {

            "success": False,

            "message": "User not logged in"

        }, 401


    # --------------------------------------------------------
    # READ JSON DATA
    # --------------------------------------------------------

    data = request.get_json()

    if not data:

        return {

            "success": False,

            "message": "Invalid request data"

        }, 400


    # --------------------------------------------------------
    # GET SUBSCRIPTION DATA
    # --------------------------------------------------------

    endpoint = data.get(
        "endpoint"
    )

    keys = data.get(
        "keys",
        {}
    )

    p256dh = keys.get(
        "p256dh"
    )

    auth = keys.get(
        "auth"
    )


    # --------------------------------------------------------
    # VALIDATE SUBSCRIPTION
    # --------------------------------------------------------

    if not endpoint or not p256dh or not auth:

        return {

            "success": False,

            "message": "Invalid subscription data"

        }, 400


    # --------------------------------------------------------
    # CHECK EXISTING SUBSCRIPTION
    # --------------------------------------------------------

    existing = PushSubscription.query.filter_by(
        endpoint=endpoint
    ).first()

    if existing:

        return {

            "success": True,

            "message": "Subscription already saved"

        }


    # --------------------------------------------------------
    # SAVE NEW SUBSCRIPTION
    # --------------------------------------------------------

    subscription = PushSubscription(

        user_id=session['user_id'],

        endpoint=endpoint,

        p256dh=p256dh,

        auth=auth

    )

    db.session.add(
        subscription
    )

    db.session.commit()


    return {

        "success": True,

        "message": "Push subscription saved"

    }

# ============================================================
# HOME
# ============================================================

@app.route('/')
def home():

    return render_template(
        'index.html'
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    '/register',
    methods=['GET', 'POST']
)
def register():

    if request.method == 'POST':

        name = request.form['name'].strip()

        email = request.form['email'].strip().lower()

        password = request.form['password']

        # ----------------------------------------------------
        # Validate Gmail address
        # ----------------------------------------------------

        if not email.endswith('@gmail.com'):

            return "Please use a valid Gmail address ending with @gmail.com."

        # Check existing email

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            return "Email already registered!"

        # Every newly registered account is a normal User.
        hashed_password = generate_password_hash(password)

        user = User(

            name=name,

            email=email,

            password=hashed_password,

            role='User'
        )

        db.session.add(user)

        db.session.commit()

        return redirect(
            url_for('login')
        )

    return render_template(
        'register.html'
    )

# ============================================================
# ADMIN SETUP
# ============================================================

# /make-admin route has been removed for security.


# ============================================================
# LOGIN
# ============================================================

@app.route(
    '/login',
    methods=['GET', 'POST']
)
def login():

    if request.method == 'POST':

        email = request.form['email'].strip().lower()

        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):

            # Store user information in session

            session['user_id'] = user.id

            session['user_name'] = user.name

            session['user_role'] = user.role

            return redirect(
                url_for('dashboard')
            )

        return "Invalid email or password!"

    return render_template(
        'login.html'
    )
# ============================================================
# ADMIN - VIEW CLAIMS
# ============================================================

@app.route('/admin/claims')
def admin_claims():

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    user = admin_required()

    if not user:

        return "Access Denied! Admins only.", 403

    claims = Claim.query.order_by(
        Claim.created_at.desc()
    ).all()

    return render_template(
        'admin_claims.html',
        claims=claims
    )
# ============================================================
# ADMIN - MANAGE USERS
# ============================================================

@app.route('/admin/users')
def admin_users():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = admin_required()

    if not user:
        return "Access Denied! Admins only.", 403

    users = User.query.order_by(
        User.id.asc()
    ).all()

    return render_template(
        'admin_users.html',
        users=users
    )


# ============================================================
# ADMIN - DELETE USER
# ============================================================

@app.route(
    '/admin/users/delete/<int:user_id>',
    methods=['POST']
)
def delete_user(user_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    admin = admin_required()

    if not admin:
        return "Access Denied! Admins only.", 403

    # Prevent admin from deleting their own account
    if user_id == session['user_id']:
        return "You cannot delete your own admin account."

    user = User.query.get_or_404(user_id)
    if user.role == 'Admin':
        return "Admin accounts cannot be deleted."
    # --------------------------------------------------------
    # Delete claims related to this user's reports
    # --------------------------------------------------------

    user_reports = ItemReport.query.filter_by(
        user_id=user.id
    ).all()

    for report in user_reports:

        Claim.query.filter_by(
            item_id=report.id
        ).delete(
            synchronize_session=False
        )

        Notification.query.filter_by(
            item_id=report.id
        ).delete(
            synchronize_session=False
        )

    # --------------------------------------------------------
    # Delete claims made by this user
    # --------------------------------------------------------

    Claim.query.filter_by(
        claimant_id=user.id
    ).delete(
        synchronize_session=False
    )

    # --------------------------------------------------------
    # Delete notifications received by this user
    # --------------------------------------------------------

    Notification.query.filter_by(
        recipient_id=user.id
    ).delete(
        synchronize_session=False
    )

    # --------------------------------------------------------
    # Delete push subscriptions
    # --------------------------------------------------------

    PushSubscription.query.filter_by(
        user_id=user.id
    ).delete(
        synchronize_session=False
    )

    # --------------------------------------------------------
    # Delete user's reports
    # --------------------------------------------------------

    for report in user_reports:
        db.session.delete(report)

    # --------------------------------------------------------
    # Finally delete the user
    # --------------------------------------------------------

    db.session.delete(user)

    db.session.commit()

    return redirect(
        url_for('admin_users')
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    user = get_current_user()

    if not user:

        session.clear()

        return redirect(
            url_for('login')
        )

    return render_template(

        'dashboard.html',

        name=user.name,

        role=user.role
    )


# ============================================================
# REPORT LOST ITEM
# ============================================================

@app.route(
    '/report/lost',
    methods=['GET', 'POST']
)
def report_lost():

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    if request.method == 'POST':

        print(
            "LOST REPORT POST RECEIVED"
        )

        # ====================================================
        # GET FORM DATA
        # ====================================================

        title = request.form['title'].strip()

        description = request.form['description'].strip()

        category = request.form['category'].strip()

        color = request.form['color'].strip()

        location = request.form['location'].strip()

        report_date = request.form['date'].strip()

        # ====================================================
        # DATE VALIDATION
        # ====================================================

        if not report_date:

            return "Date is required."

        try:

            selected_date = datetime.strptime(
                report_date,
                "%Y-%m-%d"
            ).date()

            today_date = datetime.now().date()

            if selected_date > today_date:

                return "Future dates are not allowed."

        except ValueError:

            return "Invalid date."

        # ====================================================
        # AI REPORT ANALYSIS
        # ====================================================

        ai_analysis = analyze_report(

            report_type="LOST",

            title=title,

            description=description,

            category=category,

            color=color,

            location=location,

            date=report_date
        )

        print(
            "AI REPORT ANALYSIS:"
        )

        print(
            ai_analysis["explanation"]
        )

        # ====================================================
        # UPLOAD IMAGE
        # ====================================================

        image = request.files.get(
            'image'
        )

        image_filename = save_uploaded_image(
            image
        )

        # ====================================================
        # CREATE LOST REPORT
        # ====================================================

        report = ItemReport(

            user_id=session['user_id'],

            report_type='Lost',

            title=title,

            description=description,

            category=category,

            color=color,

            location=location,

            date=report_date,

            image=image_filename,

            status='Pending Approval',
            ai_analysis=ai_analysis["explanation"]
        )

        db.session.add(
            report
        )

        db.session.commit()

        # ====================================================
        # NOTIFY ALL USERS
        # ====================================================

        users = User.query.all()

        for user in users:

            # Don't notify the person who created the report

            if user.id == session['user_id']:

                continue

            create_notification(

                recipient_id=user.id,

                title='New Lost Item Reported',

                message=(
                    f'{title} has been reported as lost.'
                ),

                notification_type='lost_report',

                item_id=report.id
            )

        db.session.commit()

        # ====================================================
        # REDIRECT
        # ====================================================

        return redirect(
            url_for('my_reports')
        )

    return render_template(

        'report_item.html',

        report_type='Lost',

        today=datetime.now().strftime(
            "%Y-%m-%d"
        )
    )


# ============================================================
# REPORT FOUND ITEM
# ============================================================

@app.route(
    '/report/found',
    methods=['GET', 'POST']
)
def report_found():

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    if request.method == 'POST':

        print(
            "FOUND REPORT POST RECEIVED"
        )

        # ====================================================
        # GET FORM DATA
        # ====================================================

        title = request.form['title'].strip()

        description = request.form['description'].strip()

        category = request.form['category'].strip()

        color = request.form['color'].strip()

        location = request.form['location'].strip()

        report_date = request.form['date'].strip()

        # ====================================================
        # DATE VALIDATION
        # ====================================================

        if not report_date:

            return "Date is required."

        try:

            selected_date = datetime.strptime(
                report_date,
                "%Y-%m-%d"
            ).date()

            today_date = datetime.now().date()

            if selected_date > today_date:

                return "Future dates are not allowed."

        except ValueError:

            return "Invalid date."

        # ====================================================
        # AI REPORT ANALYSIS
        # ====================================================

        ai_analysis = analyze_report(

            report_type="FOUND",

            title=title,

            description=description,

            category=category,

            color=color,

            location=location,

            date=report_date
        )

        print(
            "AI REPORT ANALYSIS:"
        )

        print(
            ai_analysis["explanation"]
        )

        # ====================================================
        # UPLOAD IMAGE
        # ====================================================

        image = request.files.get(
            'image'
        )

        image_filename = save_uploaded_image(
            image
        )

        # ====================================================
        # CREATE FOUND REPORT
        # ====================================================

        report = ItemReport(

            user_id=session['user_id'],

            report_type='Found',

            title=title,

            description=description,

            category=category,

            color=color,

            location=location,

            date=report_date,

            image=image_filename,

            status='Pending Approval',
            ai_analysis=ai_analysis["explanation"]
        )

        db.session.add(
            report
        )

        db.session.commit()

        # ====================================================
        # NOTIFY ALL ADMINS
        # ====================================================

        admins = User.query.filter_by(
            role='Admin'
        ).all()

        for admin in admins:

            # Don't send duplicate notification
            # if admin reported the found item

            if admin.id == session['user_id']:

                continue

            create_notification(

                recipient_id=admin.id,

                title='New Found Item Reported',

                message=(
                    f'{title} has been reported as found '
                    f'and is waiting for admin approval.'
                ),

                notification_type='found_report',

                item_id=report.id
            )

        db.session.commit()

        # ====================================================
        # REDIRECT
        # ====================================================

        return redirect(
            url_for('my_reports')
        )

    return render_template(

        'report_item.html',

        report_type='Found',

        today=datetime.now().strftime(
            "%Y-%m-%d"
        )
    )


# ============================================================
# MY REPORTS
# ============================================================

@app.route('/my-reports')
def my_reports():

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    reports = ItemReport.query.filter_by(

        user_id=session['user_id']

    ).order_by(

        ItemReport.created_at.desc()

    ).all()

    return render_template(

        'my_reports.html',

        reports=reports
        
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route('/notifications')
def notifications():

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    user_notifications = Notification.query.filter_by(

        recipient_id=session['user_id']

    ).order_by(

        Notification.created_at.desc()

    ).all()

    return render_template(

        'notifications.html',

        notifications=user_notifications
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect(
        url_for('login')
    )


# ============================================================
# AI MATCHES
# ============================================================

@app.route('/matches')
def matches():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    # --------------------------------------------------------
    # GET APPROVED LOST AND FOUND REPORTS
    # --------------------------------------------------------

    lost_items = ItemReport.query.filter_by(
        report_type='Lost',
        status='Approved'
    ).all()

    found_items = ItemReport.query.filter_by(
        report_type='Found',
        status='Approved'
    ).all()

    print("================================")
    print("AI MATCH DEBUG")
    print("Lost items:", len(lost_items))
    print("Found items:", len(found_items))
    print("================================")

    match_results = []
    all_results = []

    # --------------------------------------------------------
    # COMPARE EVERY LOST ITEM WITH EVERY FOUND ITEM
    # --------------------------------------------------------

    for lost in lost_items:

        for found in found_items:

            print("Comparing:")
            print("Lost ID:", lost.id)
            print("Found ID:", found.id)

            if lost.id == found.id:
                continue

            result = calculate_match(
                lost,
                found
            )

            # ------------------------------------------------
            # PRINT COMPLETE AI MATCH RESULT
            # ------------------------------------------------

            print("TEXT:", result['text'])
            print("IMAGE:", result['image'])
            print("CATEGORY:", result['category'])
            print("COLOR:", result['color'])
            print("LOCATION:", result['location'])
            print("DATE:", result['date'])
            print("FINAL SCORE:", result['final_score'])
            print("LEVEL:", result['level'])

            print("Lost image:", lost.image)
            print("Found image:", found.image)

            print("--------------------------------")

            match_data = {
                'lost': lost,
                'found': found,
                'score': result['final_score'],
                'level': result['level'],
                'text': result['text'],
                'image': result['image'],
                'category': result['category'],
                'color': result['color'],
                'location': result['location'],
                'date': result['date']
            }

            # Store every comparison for debugging
            all_results.append(match_data)

            # ------------------------------------------------
            # ONLY 60%+ ARE NORMAL MATCHES
            # ------------------------------------------------

            if result['final_score'] >= 60:

                match_results.append(match_data)

    # --------------------------------------------------------
    # SORT NORMAL MATCHES
    # --------------------------------------------------------

    match_results.sort(
        key=lambda x: x['score'],
        reverse=True
    )

    # --------------------------------------------------------
    # FIND BEST MATCH EVEN IF BELOW 60%
    # --------------------------------------------------------

    best_match = None

    if all_results:

        all_results.sort(
            key=lambda x: x['score'],
            reverse=True
        )

        best_match = all_results[0]

    print("TOTAL MATCHES:", len(match_results))

    if best_match:
        print(
            "BEST MATCH:",
            best_match['lost'].id,
            "->",
            best_match['found'].id,
            "SCORE:",
            best_match['score']
        )

    print("================================")

    return render_template(
        'matches.html',
        matches=match_results,
        best_match=best_match
    )
@app.route('/admin/migrate-ai')
def migrate_ai():

    if 'user_id' not in session:
        return "Login required.", 401

    user = User.query.get(session['user_id'])

    if not user or user.role != 'Admin':
        return "Access Denied!", 403

    try:
        from sqlalchemy import text

        db.session.execute(text("""
            ALTER TABLE item_report
            ADD COLUMN IF NOT EXISTS ai_analysis TEXT
        """))

        db.session.commit()

        return "Database migration successful! ai_analysis column is ready."

    except Exception as e:

        db.session.rollback()

        return f"Migration failed: {str(e)}", 500
# ============================================================
# ADMIN - VIEW REPORTS
# ============================================================

@app.route('/admin/reports')
def admin_reports():

    if 'user_id' not in session:
        return redirect(
            url_for('login')
        )

    user = admin_required()

    if not user:
        return "Access Denied! Admins only.", 403

    reports = ItemReport.query.order_by(
        ItemReport.created_at.desc()
    ).all()

    return render_template(
        'admin_reports.html',
        reports=reports
    )


# ============================================================
# ADMIN - APPROVE REPORT
# ============================================================

@app.route(
    '/admin/reports/approve/<int:report_id>',
    methods=['POST']
)
def approve_report(report_id):

    if 'user_id' not in session:
        return redirect(
            url_for('login')
        )

    user = admin_required()

    if not user:
        return "Access Denied! Admins only.", 403

    report = ItemReport.query.get_or_404(
        report_id
    )

    if report.status != 'Pending Approval':
        return "This report has already been processed."

    report.status = 'Approved'

    db.session.commit()

    # Notify report owner
    create_notification(
        recipient_id=report.user_id,
        title='Report Approved',
        message=(
            f'Your {report.report_type.lower()} report '
            f'"{report.title}" has been approved.'
        ),
        notification_type='report_approved',
        item_id=report.id
    )

    db.session.commit()

    return redirect(
        url_for('admin_reports')
    )


# ============================================================
# ADMIN - REJECT REPORT
# ============================================================

@app.route(
    '/admin/reports/reject/<int:report_id>',
    methods=['POST']
)
def reject_report(report_id):

    if 'user_id' not in session:
        return redirect(
            url_for('login')
        )

    user = admin_required()

    if not user:
        return "Access Denied! Admins only.", 403

    report = ItemReport.query.get_or_404(
        report_id
    )

    if report.status != 'Pending Approval':
        return "This report has already been processed."

    report.status = 'Rejected'

    db.session.commit()

    # Notify report owner
    create_notification(
        recipient_id=report.user_id,
        title='Report Rejected',
        message=(
            f'Your {report.report_type.lower()} report '
            f'"{report.title}" has been rejected by the administrator.'
        ),
        notification_type='report_rejected',
        item_id=report.id
    )

    db.session.commit()

    return redirect(
        url_for('admin_reports')
    )
# ============================================================
# CLAIM ITEM
# ============================================================

@app.route('/claim/<int:item_id>', methods=['POST'])
def claim_item(item_id):

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    item = ItemReport.query.get_or_404(
        item_id
    )

    # Only Found items can be claimed

    if item.report_type != 'Found':

        return "Only found items can be claimed."

    # Don't allow claiming already claimed item

    if item.status != 'Approved':

        return "This item is no longer available for claiming."

    # Check whether this user already submitted a claim

    existing_claim = Claim.query.filter_by(

        item_id=item.id,

        claimant_id=session['user_id']

    ).first()

    if existing_claim:

        return """

        <h2>Claim Already Submitted</h2>

        <p>You have already submitted a claim for this item.</p>

        <a href="/matches">Back to Matches</a>

        """

    claim = Claim(

        item_id=item.id,

        claimant_id=session['user_id'],

        status='Pending'
    )

    db.session.add(claim)

    db.session.commit()

    return """

    <h2>Claim Submitted Successfully!</h2>

    <p>Your claim has been sent to the administrator.</p>

    <p>Status: Pending</p>

    <a href="/matches">Back to Matches</a>

    """


# ============================================================
# ADMIN - APPROVE CLAIM
# ============================================================

@app.route(
    '/admin/claims/approve/<int:claim_id>',
    methods=['POST']
)
def approve_claim(claim_id):

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    user = admin_required()

    if not user:

        return "Access Denied! Admins only.", 403

    claim = Claim.query.get_or_404(
        claim_id
    )

    # Approve claim

    claim.status = 'Approved'

    # Mark item as claimed

    claim.item.status = 'Claimed'

    db.session.commit()

    return redirect(
        url_for('admin_claims')
    )


# ============================================================
# ADMIN - REJECT CLAIM
# ============================================================

@app.route(
    '/admin/claims/reject/<int:claim_id>',
    methods=['POST']
)
def reject_claim(claim_id):

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )

    user = admin_required()

    if not user:

        return "Access Denied! Admins only.", 403

    claim = Claim.query.get_or_404(
        claim_id
    )

    claim.status = 'Rejected'

    db.session.commit()

    return redirect(
        url_for('admin_claims')
    )

# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == '__main__':

    app.run(
        debug=True
    )