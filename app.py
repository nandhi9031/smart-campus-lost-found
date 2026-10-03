import os

import uuid



from flask import Flask, render_template, request, redirect, url_for, session

from werkzeug.utils import secure_filename



from models import db, User, ItemReport, Claim

from ai.match_engine import calculate_match





app = Flask(__name__)





# ============================================================

# CONFIGURATION

# ============================================================



# Use Render PostgreSQL when DATABASE_URL is available.
# Keep SQLite as a local fallback for development.
database_url = os.getenv("DATABASE_URL", "sqlite:///lost_found.db")

# Render may provide postgres://; SQLAlchemy expects postgresql://.
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False



# Secret key

app.secret_key = 'smart-lost-found-secret'



# Upload folder

app.config['UPLOAD_FOLDER'] = 'static/uploads'



os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)





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



    return User.query.get(session['user_id'])





def admin_required():

    """

    Check whether the current user is an administrator.

    """

    user = get_current_user()



    if not user:

        return None



    if user.role != 'Admin':

        return None



    return user





def save_uploaded_image(image):

    """

    Save uploaded image using a unique filename.

    Prevents two users from accidentally overwriting

    files with the same filename.

    """



    if not image or not image.filename:

        return None



    original_name = secure_filename(image.filename)



    if not original_name:

        return None



    extension = os.path.splitext(original_name)[1]



    unique_filename = f"{uuid.uuid4().hex}{extension}"



    file_path = os.path.join(

        app.config['UPLOAD_FOLDER'],

        unique_filename

    )



    image.save(file_path)



    return unique_filename





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



        name = request.form['name'].strip()

        email = request.form['email'].strip().lower()

        password = request.form['password']



        # Check existing email

        existing_user = User.query.filter_by(

            email=email

        ).first()



        if existing_user:

            return "Email already registered!"



        # IMPORTANT:

        # Every newly registered account is a normal User.

        # Admin accounts must be created separately.

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

#

# Example:

#

# /make-admin?email=testuser123@gmail.com

#

# This route is ONLY for setting up the admin account.

# Remove this route after creating the admin.

#

# ============================================================







# ============================================================

# CHECK USER

# ============================================================

#

# Example:

#

# /check-user?email=testuser123@gmail.com

#

# Used to verify whether the Render database contains

# the registered account and what its current role is.

#

# ============================================================



@app.route('/check-user')

def check_user():



    email = request.args.get('email', '').strip().lower()



    if not email:

        return """

        <h2>Check User</h2>



        <p>Please provide an email.</p>



        <p>Example:</p>



        <p>/check-user?email=testuser123@gmail.com</p>

        """



    user = User.query.filter_by(

        email=email

    ).first()



    if not user:

        return f"""

        <h2>User Not Found</h2>



        <p>The database does not contain:</p>



        <p><b>{email}</b></p>

        """



    return f"""

    <h2>User Found</h2>



    <p><b>ID:</b> {user.id}</p>



    <p><b>Name:</b> {user.name}</p>



    <p><b>Email:</b> {user.email}</p>



    <p><b>Role:</b> {user.role}</p>



    <br>



    <a href="/login">Go to Login</a>

    """





# ============================================================

# LOGIN

# ============================================================



@app.route('/login', methods=['GET', 'POST'])

def login():



    if request.method == 'POST':



        email = request.form['email'].strip().lower()

        password = request.form['password']



        user = User.query.filter_by(

            email=email,

            password=password

        ).first()



        if user:



            # Store user information in session

            session['user_id'] = user.id

            session['user_name'] = user.name

            session['user_role'] = user.role



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



    user = admin_required()



    if not user:

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



    user = get_current_user()



    if not user:

        session.clear()

        return redirect(url_for('login'))



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



    if 'user_id' not in session:

        return redirect(url_for('login'))



    if request.method == 'POST':



        title = request.form['title']

        description = request.form['description']

        category = request.form['category']

        color = request.form['color']

        location = request.form['location']

        date = request.form['date']



        # Upload image

        image = request.files.get('image')



        image_filename = save_uploaded_image(image)



        # Create Lost report

        report = ItemReport(

            user_id=session['user_id'],

            report_type='Lost',

            title=title,

            description=description,

            category=category,

            color=color,

            location=location,

            date=date,

            image=image_filename,

            status='Active'

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



    if 'user_id' not in session:

        return redirect(url_for('login'))



    if request.method == 'POST':



        title = request.form['title']

        description = request.form['description']

        category = request.form['category']

        color = request.form['color']

        location = request.form['location']

        date = request.form['date']



        # Upload image

        image = request.files.get('image')



        image_filename = save_uploaded_image(image)



        # Create Found report

        report = ItemReport(

            user_id=session['user_id'],

            report_type='Found',

            title=title,

            description=description,

            category=category,

            color=color,

            location=location,

            date=date,

            image=image_filename,

            status='Active'

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



    if 'user_id' not in session:

        return redirect(url_for('login'))



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

# LOGOUT

# ============================================================



@app.route('/logout')

def logout():



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



            # Don't compare an item with itself

            if lost.id == found.id:

                continue



            result = calculate_match(

                lost,

                found

            )



            # Keep meaningful matches

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



    # Only Found items can be claimed

    if item.report_type != 'Found':

        return "Only found items can be claimed."



    # Don't allow claiming already claimed item

    if item.status != 'Active':

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



@app.route('/admin/claims/approve/<int:claim_id>')

def approve_claim(claim_id):



    if 'user_id' not in session:

        return redirect(url_for('login'))



    user = admin_required()



    if not user:

        return "Access Denied! Admins only."



    claim = Claim.query.get_or_404(claim_id)



    # Approve claim

    claim.status = 'Approved'



    # Mark item as claimed

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



    user = admin_required()



    if not user:

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