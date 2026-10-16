from datetime import (
    datetime,
    timezone
)

from flask_login import UserMixin

from extensions import db

def utc_now():

    return (
        datetime.now(timezone.utc)
        .replace(tzinfo=None)
    )

class User(db.Model, UserMixin):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )


class Project(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # 作品所屬的使用者 ID

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )
    
    # 作品建立時選擇的品牌
    brand_id = db.Column(
        db.Integer,
        db.ForeignKey("brand.id"),
        nullable=True
    )

    topic = db.Column(
        db.String(200),
        nullable=False
    )

    platform = db.Column(
        db.String(50)
    )

    tone = db.Column(
        db.String(50)
    )

    extra_requirement = db.Column(
        db.Text
    )

    title = db.Column(
        db.String(300)
    )

    caption = db.Column(
        db.Text
    )

    cta = db.Column(
        db.String(300)
    )

    hashtags = db.Column(
        db.Text
    )

    image_prompt = db.Column(
        db.Text
    )

    image_filename = db.Column(
        db.String(300)
    )

    image_style = db.Column(
        db.String(50)
    )

    image_size = db.Column(
        db.String(50)
    )

    image_quality = db.Column(
        db.String(50)
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )
    

class Brand(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # 品牌所屬的使用者 ID

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    name = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    target_audience = db.Column(
        db.Text
    )

    brand_tone = db.Column(
        db.String(200)
    )

    brand_features = db.Column(
        db.Text
    )

    products_services = db.Column(
        db.Text
    )

    banned_words = db.Column(
        db.Text
    )

    notes = db.Column(
        db.Text
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )
    

class BrandDocument(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    brand_id = db.Column(
        db.Integer,
        db.ForeignKey("brand.id"),
        nullable=False
    )

    filename = db.Column(
        db.String(300),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )


class BrandChunk(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    brand_id = db.Column(
        db.Integer,
        db.ForeignKey("brand.id"),
        nullable=False
    )

    document_id = db.Column(
        db.Integer,
        db.ForeignKey("brand_document.id"),
        nullable=False
    )

    content = db.Column(
        db.Text,
        nullable=False
    )

    embedding = db.Column(
        db.Text,
        nullable=False
    )


class ProjectVariant(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("project.id"),
        nullable=False
    )

    platform = db.Column(
        db.String(50),
        nullable=False
    )

    title = db.Column(
        db.String(300)
    )

    caption = db.Column(
        db.Text
    )

    cta = db.Column(
        db.String(300)
    )

    hashtags = db.Column(
        db.Text
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )
