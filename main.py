from datetime import date
from enum import unique
from typing import List
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap5(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

def admin_only(f):
    @wraps(f)
    def decorator_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        else:
            return f(*args, **kwargs)
    return decorator_function

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped["User"] = relationship("User", back_populates="posts")
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="blog_post")

# TODO: Create a User table for all your registered users. 
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(250), nullable=False)
    password: Mapped[str] = mapped_column(String(500), nullable=False)
    posts: Mapped[List["BlogPost"]] = relationship("BlogPost", back_populates="author")
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="user")

class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Integer, ForeignKey("user.id"))
    user: Mapped["User"] = relationship("User", back_populates="comments")
    blog_post: Mapped["BlogPost"] = relationship("BlogPost", back_populates="comments")
    blog_id: Mapped[str] = mapped_column(Integer, ForeignKey("blog_posts.id"))

with app.app_context():
    db.create_all()

# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        data = db.session.query(User).filter_by(email=form.email.data).first()
        if data:
            flash("You've already signed up")
            return redirect(url_for('login'))
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data, method="pbkdf2:sha256", salt_length=8)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form, is_logged_in=current_user.is_authenticated)

# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user_data = db.session.query(User).filter_by(email=form.email.data).scalar()
        if user_data:
            if check_password_hash(user_data.password, form.password.data):
                login_user(user_data)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Incorrect Password")
                return redirect(url_for('login'))
        else:
            flash("User email not found.")
            return redirect(url_for('login'))
    return render_template("login.html", form=form, is_logged_in=current_user.is_authenticated)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))

@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, is_logged_in=current_user.is_authenticated, user_id=current_user.get_id())

# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You have to log in to comment first.")
            return redirect(url_for('login'))
        comment_text = Comment(
            text=form.comment.data,
            blog_id=post_id,
            user_id=current_user.id,
        )
        db.session.add(comment_text)
        db.session.commit()
    return render_template("post.html", post=requested_post, is_logged_in=current_user.is_authenticated, user_id=current_user.get_id(), form=form, gravatar=gravatar)


# TODO: Use a decorator so only an admin user can create a new post

@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, is_logged_in=current_user.is_authenticated)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, is_logged_in=current_user.is_authenticated)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", is_logged_in=current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html", is_logged_in=current_user.is_authenticated)


if __name__ == "__main__":
    app.run(debug=True, port=5002)
