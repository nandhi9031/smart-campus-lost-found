from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db = SQLAlchemy()


# ============================================================
# USER MODEL
# ============================================================

class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(200),
        nullable=False
    )

    # User or Admin
    role = db.Column(
        db.String(20),
        default='User'
    )

    reports = db.relationship(
        'ItemReport',
        backref='user',
        lazy=True
    )


# ============================================================
# ITEM REPORT MODEL
# ============================================================

class ItemReport(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

    report_type = db.Column(
        db.String(10),
        nullable=False
    )

    title = db.Column(
        db.String(150),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=False
    )

    category = db.Column(
        db.String(50)
    )

    color = db.Column(
        db.String(50)
    )

    location = db.Column(
        db.String(150)
    )

    date = db.Column(
        db.String(20)
    )

    image = db.Column(
        db.String(300)
    )

    status = db.Column(
        db.String(30),
        default='Active'
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# ============================================================
# CLAIM MODEL
# ============================================================

class Claim(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # Found item being claimed
    item_id = db.Column(
        db.Integer,
        db.ForeignKey('item_report.id'),
        nullable=False
    )

    # User who is claiming the item
    claimant_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

    # Pending / Approved / Rejected
    status = db.Column(
        db.String(30),
        default='Pending'
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Relationship with ItemReport
    item = db.relationship(
        'ItemReport',
        backref='claims'
    )

    # Relationship with User
    claimant = db.relationship(
        'User',
        backref='claims'
    )
# ============================================================
# NOTIFICATION MODEL
# ============================================================

class Notification(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # User who receives the notification
    recipient_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

    # Notification title
    title = db.Column(
        db.String(150),
        nullable=False
    )

    # Notification message
    message = db.Column(
        db.Text,
        nullable=False
    )

    # lost_report / found_report / match / claim / admin
    notification_type = db.Column(
        db.String(50),
        nullable=False
    )

    # Optional related item
    item_id = db.Column(
        db.Integer,
        db.ForeignKey('item_report.id'),
        nullable=True
    )

    # False = unread, True = read
    is_read = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Relationship with receiver
    recipient = db.relationship(
        'User',
        backref='notifications'
    )

    # Relationship with item
    item = db.relationship(
        'ItemReport',
        backref='notifications'
    )
# ============================================================
# PUSH SUBSCRIPTION MODEL
# ============================================================

class PushSubscription(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

    endpoint = db.Column(
        db.Text,
        nullable=False
    )

    p256dh = db.Column(
        db.Text,
        nullable=False
    )

    auth = db.Column(
        db.Text,
        nullable=False
    )

    user = db.relationship(
        'User',
        backref='push_subscriptions'
    )