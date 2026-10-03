import os

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

from models import db, User, ItemReport, Claim
from ai.match_engine import calculate_match

app = Flask(__name__)


# ============================================================
# Configuration
# ============================================================

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lost_found.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Secret key for session
app.secret_key = 'smart-lost-found-secret'

# Image upload folder
app.config['UPLOAD_FOLDER'] = 'static/uploads'


# Create upload folder if it does not exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# Connect database
db.init_app(app)


# Create database tables
with app.app_context():
    db.create_all()


# ============================================================
# HOME
# ============================================================

@app.route('/')
def home():
    return render_template('index.html')


# ============================================================
# REGISTER
# ============================================================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Check whether email already exists
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            return "Email already registered!"

        # Create new user
        user = User(
            name=name,
            email=email,
            password=password,
            role='User'
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')

# ============================================================
# TEMPORARY ADMIN SETUP
# ============================================================

@app.route('/make-admin')
def make_admin():

    email = "testuser123@gmail.com"

    user = User.query.filter_by(email=email).first()

    if not user:
        return "User not found!"

    user.role = "Admin"
    user.password = "Admin@123"

    db.session.commit()

    return """
    <h2>Admin setup successful!</h2>
    <p>Email: testuser123@gmail.com</p>
    <p>Temporary Password: Admin@123</p>
    <p>Role: Admin</p>
    <a href="/login">Go to Login</a>
    """
# ============================================================
# LOGIN
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        # Find user
        user = User.query.filter_by(
            email=email,
            password=password
        ).first()

        if user:

            # Store user information in session
            session['user_id'] = user.id
            session['user_name'] = user.name

            return redirect(url_for('dashboard'))

        return "Invalid email or password!"

    return render_template('login.html')
# ============================================================
# ADMIN - VIEW CLAIMS
# ============================================================

@app.route('/admin/claims')
def admin_claims():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Check Admin role
    user = User.query.get(session['user_id'])

    if not user or user.role != 'Admin':
        return "Access Denied! Admins only."

    claims = Claim.query.order_by(
        Claim.created_at.desc()
    ).all()

    return render_template(
        'admin_claims.html',
        claims=claims
    )
# ============================================================
# DASHBOARD
# ============================================================

@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    return render_template(
        'dashboard.html',
        name=user.name,
        role=user.role
    )
# ============================================================
# REPORT LOST ITEM
# ============================================================

@app.route('/report/lost', methods=['GET', 'POST'])
def report_lost():

    # Check login
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':

        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        color = request.form['color']
        location = request.form['location']
        date = request.form['date']

        # Get uploaded image
        image = request.files.get('image')
        image_filename = None

        if image and image.filename:

            image_filename = secure_filename(image.filename)

            image.save(
                os.path.join(
                    app.config['UPLOAD_FOLDER'],
                    image_filename
                )
            )

        # Create lost item report
        report = ItemReport(
            user_id=session['user_id'],
            report_type='Lost',
            title=title,
            description=description,
            category=category,
            color=color,
            location=location,
            date=date,
            image=image_filename
        )

        db.session.add(report)
        db.session.commit()

        return redirect(url_for('my_reports'))

    return render_template(
        'report_item.html',
        report_type='Lost'
    )


# ============================================================
# REPORT FOUND ITEM
# ============================================================

@app.route('/report/found', methods=['GET', 'POST'])
def report_found():

    # Check login
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':

        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        color = request.form['color']
        location = request.form['location']
        date = request.form['date']

        # Get uploaded image
        image = request.files.get('image')
        image_filename = None

        if image and image.filename:

            image_filename = secure_filename(image.filename)

            image.save(
                os.path.join(
                    app.config['UPLOAD_FOLDER'],
                    image_filename
                )
            )

        # Create found item report
        report = ItemReport(
            user_id=session['user_id'],
            report_type='Found',
            title=title,
            description=description,
            category=category,
            color=color,
            location=location,
            date=date,
            image=image_filename
        )

        db.session.add(report)
        db.session.commit()

        return redirect(url_for('my_reports'))

    return render_template(
        'report_item.html',
        report_type='Found'
    )


# ============================================================
# MY REPORTS
# ============================================================

@app.route('/my-reports')
def my_reports():

    # Check login
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get reports submitted by current user
    reports = ItemReport.query.filter_by(
        user_id=session['user_id']
    ).all()

    return render_template(
        'my_reports.html',
        reports=reports
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route('/logout')
def logout():

    # Clear session
    session.clear()

    return redirect(url_for('login'))

# ============================================================
# AI MATCHES
# ============================================================

@app.route('/matches')
def matches():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    lost_items = ItemReport.query.filter_by(
        report_type='Lost',
        status='Active'
    ).all()

    found_items = ItemReport.query.filter_by(
        report_type='Found',
        status='Active'
    ).all()

    match_results = []

    for lost in lost_items:

        for found in found_items:

            result = calculate_match(
                lost,
                found
            )

            # Only keep meaningful matches
            if result['final_score'] >= 60:

                match_results.append({

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

                })

    # Highest score first
    match_results.sort(
        key=lambda x: x['score'],
        reverse=True
    )

    return render_template(
        'matches.html',
        matches=match_results
    )
# ============================================================
# CLAIM ITEM
# ============================================================

@app.route('/claim/<int:item_id>')
def claim_item(item_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    item = ItemReport.query.get_or_404(item_id)

    # Only found items can be claimed
    if item.report_type != 'Found':
        return "Only found items can be claimed."

    # Check whether user already claimed this item
    existing_claim = Claim.query.filter_by(
        item_id=item.id,
        claimant_id=session['user_id']
    ).first()

    if existing_claim:
        return "You have already submitted a claim for this item."

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

@app.route('/admin/claims/approve/<int:claim_id>')
def approve_claim(claim_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if not user or user.role != 'Admin':
        return "Access Denied! Admins only."

    claim = Claim.query.get_or_404(claim_id)

    claim.status = 'Approved'
    claim.item.status = 'Claimed'

    db.session.commit()

    return redirect(url_for('admin_claims'))
# ============================================================
# ADMIN - REJECT CLAIM
# ============================================================

@app.route('/admin/claims/reject/<int:claim_id>')
def reject_claim(claim_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if not user or user.role != 'Admin':
        return "Access Denied! Admins only."

    claim = Claim.query.get_or_404(claim_id)

    claim.status = 'Rejected'

    db.session.commit()

    return redirect(url_for('admin_claims'))
# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == '__main__':
    app.run(debug=True)