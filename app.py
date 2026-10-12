import os

import sqlite3

from functools import wraps

from flask_wtf.csrf import CSRFProtect

from dotenv import load_dotenv

from flask import (

    Flask,

    render_template,

    request,

    redirect,

    url_for,

    flash,

    session

)

from werkzeug.security import generate_password_hash, check_password_hash

# Load private settings from the root .env file

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

if not app.config["SECRET_KEY"]:

    raise RuntimeError(

        "SECRET_KEY is missing. Check your .env file."

    )

# Enable CSRF protection for form submissions

csrf = CSRFProtect(app)

# ==================================================

# DATABASE CONNECTION

# ==================================================

def get_db_connection():

    conn = sqlite3.connect("notes.db")

    conn.row_factory = sqlite3.Row

    return conn

# ==================================================

# DATABASE INITIALIZATION AND MIGRATION

# ==================================================

def init_db():

    conn = sqlite3.connect("notes.db")

    # User accounts

    conn.execute("""

        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT NOT NULL UNIQUE,

            email TEXT NOT NULL UNIQUE,

            password_hash TEXT NOT NULL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP

        )

    """)

    # Notes table

    conn.execute("""

        CREATE TABLE IF NOT EXISTS notes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            content TEXT NOT NULL,

            created_at TEXT,

            is_favorite INTEGER NOT NULL DEFAULT 0,

                       user_id INTEGER,
            category TEXT NOT NULL DEFAULT 'Personal',
            pinned INTEGER NOT NULL DEFAULT 0

        )

    """)

    # Check columns in an existing database

    columns = conn.execute(

        "PRAGMA table_info(notes)"

    ).fetchall()

    column_names = [column[1] for column in columns]

    # Migrate older databases without deleting existing notes

    if "created_at" not in column_names:

        conn.execute(

            "ALTER TABLE notes ADD COLUMN created_at TEXT"

        )

    if "is_favorite" not in column_names:

        conn.execute("""

            ALTER TABLE notes

            ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0

        """)

    if "user_id" not in column_names:

        conn.execute(

            "ALTER TABLE notes ADD COLUMN user_id INTEGER"

        )

  
    if "category" not in column_names:
        conn.execute("""
            ALTER TABLE notes
            ADD COLUMN category TEXT NOT NULL DEFAULT 'Personal'
        """)

    if "pinned" not in column_names:
        conn.execute("""
            ALTER TABLE notes
            ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0
        """)

    # Fill missing creation dates

    conn.execute("""

        UPDATE notes

        SET created_at = datetime('now', 'localtime')

        WHERE created_at IS NULL

    """)

    conn.commit()

    conn.close()

init_db()

# ==================================================

# LOGIN PROTECTION

# ==================================================

def login_required(view_function):

    @wraps(view_function)

    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:

            flash("Please log in to continue. 🌻", "error")

            return redirect(url_for("login"))

        return view_function(*args, **kwargs)

    return wrapped_view

# ==================================================

# WELCOME PAGE

# ==================================================

@app.route("/")

def welcome():

    if "user_id" in session:

        return redirect(url_for("home"))

    return render_template("welcome.html")

# ==================================================

# SIGN UP

# ==================================================

@app.route("/signup", methods=["GET", "POST"])

def signup():

    if "user_id" in session:

        return redirect(url_for("home"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password or not confirm_password:

            flash("Please fill in every field. 🌻", "error")

            return render_template("signup.html")

        if len(username) < 3 or len(username) > 30:

            flash(

                "Username must be between 3 and 30 characters.",

                "error"

            )

            return render_template("signup.html")

        if password != confirm_password:

            flash("Your passwords don't match.", "error")

            return render_template("signup.html")

        if len(password) < 8:

            flash(

                "Your password must have at least 8 characters.",

                "error"

            )

            return render_template("signup.html")

        conn = get_db_connection()

        existing_user = conn.execute(

            """

            SELECT id FROM users

            WHERE username = ? OR email = ?

            """,

            (username, email)

        ).fetchone()

        if existing_user:

            conn.close()

            flash(

                "That username or email is already registered.",

                "error"

            )

            return render_template("signup.html")

        # Determine whether this is the first account

        existing_accounts = conn.execute(

            "SELECT COUNT(*) FROM users"

        ).fetchone()[0]

        password_hash = generate_password_hash(password)

        try:

            cursor = conn.execute(

                """

                INSERT INTO users (username, email, password_hash)

                VALUES (?, ?, ?)

                """,

                (username, email, password_hash)

            )

            new_user_id = cursor.lastrowid

            # Assign older, unowned notes to the first account

            if existing_accounts == 0:

                conn.execute(

                    """

                    UPDATE notes

                    SET user_id = ?

                    WHERE user_id IS NULL

                    """,

                    (new_user_id,)

                )

            conn.commit()

        except sqlite3.IntegrityError:

            conn.rollback()

            conn.close()

            flash(

                "That username or email is already registered.",

                "error"

            )

            return render_template("signup.html")

        conn.close()

        flash(

            "Your account is ready! Please log in. 🌼",

            "success"

        )

        return redirect(url_for("login"))

    return render_template("signup.html")

# ==================================================

# LOGIN

# ==================================================

@app.route("/login", methods=["GET", "POST"])

def login():

    if "user_id" in session:

        return redirect(url_for("home"))

    if request.method == "POST":

        identifier = request.form.get("identifier", "").strip()

        password = request.form.get("password", "")

        conn = get_db_connection()

        user = conn.execute(

            """

            SELECT id, username, email, password_hash

            FROM users

            WHERE username = ? OR email = ?

            """,

            (identifier, identifier.lower())

        ).fetchone()

        conn.close()

        if user and check_password_hash(

            user["password_hash"], password

        ):

            session.clear()

            session["user_id"] = user["id"]

            session["username"] = user["username"]

            flash(

                f"Welcome back, {user['username']}! 🌻",

                "success"

            )

            return redirect(url_for("home"))

        flash(

            "Incorrect username, email, or password.",

            "error"

        )

    return render_template("login.html")

# ==================================================

# LOGOUT

# ==================================================

@app.route("/logout", methods=["POST"])

@login_required

def logout():

    session.clear()

    flash(

        "You've logged out successfully. See you soon! 🌻",

        "success"

    )

    return redirect(url_for("welcome"))

# ==================================================

# YOUR NOTES DASHBOARD

# Only ONE home() function and ONE /notes route

# ==================================================

@app.route("/notes")

@login_required

def home():

    search_query = request.args.get("q", "").strip()

    favorites_only = request.args.get("favorites") == "1"

    selected_category = request.args.get("category", "").strip()

    user_id = session["user_id"]

    conn = get_db_connection()

    # Get the categories used by this user's notes

    category_rows = conn.execute(

        """

        SELECT DISTINCT category

        FROM notes

        WHERE user_id = ?

          AND category IS NOT NULL

          AND category != ''

        ORDER BY category COLLATE NOCASE

        """,

        (user_id,)

    ).fetchall()

    categories = [row["category"] for row in category_rows]

    # Start with this user's notes only

    query = "SELECT * FROM notes WHERE user_id = ?"

    parameters = [user_id]

    # Apply Favorites filter

    if favorites_only:

        query += " AND is_favorite = 1"

    # Apply category filter

    if selected_category:

        query += " AND category = ?"

        parameters.append(selected_category)

    # Search within the selected collection

    if search_query:

        query += " AND (title LIKE ? OR content LIKE ?)"

        parameters.extend([

            f"%{search_query}%",

            f"%{search_query}%"

        ])

    
    query += " ORDER BY pinned DESC, id DESC"


    notes = conn.execute(

        query,

        parameters

    ).fetchall()

    conn.close()

    return render_template(

        "index.html",

        notes=notes,

        search_query=search_query,

        favorites_only=favorites_only,

        categories=categories,

        selected_category=selected_category

    )

# ==================================================

# CREATE A NOTE WITH STANDARD OR CUSTOM CATEGORY

# ==================================================

@app.route("/add", methods=["GET", "POST"])

@login_required

def add_note():

    if request.method == "POST":

        title = request.form.get("title", "").strip()

        content = request.form.get("content", "").strip()

        category_choice = request.form.get(

            "category", "Personal"

        ).strip()

        allowed_categories = {

            "Personal", "College", "Ideas", "Work", "Other"

        }

        if category_choice not in allowed_categories:

            category_choice = "Personal"

        # Use the custom name when Other is selected

        if category_choice == "Other":

            category = request.form.get(

                "custom_category", ""

            ).strip()

            if not category:

                flash(

                    "Please enter your custom category name. 🌼",

                    "error"

                )

                return render_template("add_note.html")

            if len(category) > 40:

                flash(

                    "Category names must be 40 characters or fewer.",

                    "error"

                )

                return render_template("add_note.html")

        else:

            category = category_choice

        if not title or not content:

            flash(

                "Please fill in both title and content! 🌼",

                "error"

            )

            return render_template("add_note.html")

        conn = get_db_connection()

        conn.execute(

            """

            INSERT INTO notes (

                title,

                content,

                created_at,

                is_favorite,

                user_id,

                category

            )

            VALUES (

                ?, ?,

                datetime('now', 'localtime'),

                0, ?, ?

            )

            """,

            (title, content, session["user_id"], category)

        )

        conn.commit()

        conn.close()

        flash(

            "Your note has been saved successfully! 🌻",

            "success"

        )

        return redirect(url_for("home"))

    return render_template("add_note.html")

# ==================================================

# VIEW A NOTE

# ==================================================

@app.route("/note/<int:note_id>")

@login_required

def view_note(note_id):

    conn = get_db_connection()

    note = conn.execute(

        """

        SELECT * FROM notes

        WHERE id = ? AND user_id = ?

        """,

        (note_id, session["user_id"])

    ).fetchone()

    conn.close()

    if note is None:

        return "Note not found", 404

    return render_template("view_note.html", note=note)

# ==================================================

# EDIT A NOTE

# ==================================================

@app.route("/edit/<int:note_id>", methods=["GET", "POST"])

@login_required

def edit_note(note_id):

    conn = get_db_connection()

    note = conn.execute(

        """

        SELECT * FROM notes

        WHERE id = ? AND user_id = ?

        """,

        (note_id, session["user_id"])

    ).fetchone()

    if note is None:

        conn.close()

        return "Note not found", 404

    if request.method == "POST":

        title = request.form.get("title", "").strip()

        content = request.form.get("content", "").strip()

        # Preserve the existing category in this version

        category = note["category"]

        if not title or not content:

            conn.close()

            flash("Please fill in both fields! 🌼", "error")

            return redirect(

                url_for("edit_note", note_id=note_id)

            )

        conn.execute(

            """

            UPDATE notes

            SET title = ?, content = ?, category = ?

            WHERE id = ? AND user_id = ?

            """,

            (

                title,

                content,

                category,

                note_id,

                session["user_id"]

            )

        )

        conn.commit()

        conn.close()

        flash(

            "Your note has been updated successfully! 🌻",

            "success"

        )

        return redirect(url_for("home"))

    conn.close()

    return render_template("edit_note.html", note=note)

# ==================================================

# DELETE A NOTE

# ==================================================

@app.route("/delete/<int:note_id>", methods=["POST"])

@login_required

def delete_note(note_id):

    conn = get_db_connection()

    result = conn.execute(

        """

        DELETE FROM notes

        WHERE id = ? AND user_id = ?

        """,

        (note_id, session["user_id"])

    )

    conn.commit()

    conn.close()

    if result.rowcount == 0:

        flash("Note not found.", "error")

    else:

        flash(

            "Your note has been deleted successfully! 🌻",

            "success"

        )

    return redirect(url_for("home"))

# ==================================================

# TOGGLE FAVORITE FLOWER

# ==================================================

@app.route("/favorite/<int:note_id>", methods=["POST"])

@login_required

def toggle_favorite(note_id):

    conn = get_db_connection()

    result = conn.execute(

        """

        UPDATE notes

        SET is_favorite = CASE

            WHEN is_favorite = 1 THEN 0

            ELSE 1

        END

        WHERE id = ? AND user_id = ?

        """,

        (note_id, session["user_id"])

    )

    conn.commit()

    conn.close()

    if result.rowcount == 0:

        flash("Note not found.", "error")

    # Preserve filters where the form submits them

    search_query = request.form.get("q", "").strip()

    favorites_only = request.form.get("favorites") == "1"

    selected_category = request.form.get("category", "").strip()

    return redirect(

        url_for(

            "home",

            q=search_query or None,

            favorites=1 if favorites_only else None,

            category=selected_category or None

        )

    )

# ==================================================
# PIN OR UNPIN A NOTE
# ==================================================

@app.route("/pin/<int:note_id>", methods=["POST"])
@login_required
def toggle_pin(note_id):

    conn = get_db_connection()

    result = conn.execute(
        """
        UPDATE notes
        SET pinned = CASE
            WHEN pinned = 1 THEN 0
            ELSE 1
        END
        WHERE id = ? AND user_id = ?
        """,
        (note_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    if result.rowcount == 0:
        flash("Note not found.", "error")

    # Preserve the current dashboard filters
    search_query = request.form.get("q", "").strip()
    favorites_only = request.form.get("favorites") == "1"
    selected_category = request.form.get("category", "").strip()

    return redirect(
        url_for(
            "home",
            q=search_query or None,
            favorites=1 if favorites_only else None,
            category=selected_category or None
        )
    )

# ==================================================

# PREVENT PRIVATE PAGES FROM BEING CACHED

# ==================================================

@app.after_request

def prevent_page_caching(response):

    response.headers["Cache-Control"] = (

        "no-store, no-cache, must-revalidate, private"

    )

    response.headers["Pragma"] = "no-cache"

    response.headers["Expires"] = "0"

    return response

# ==================================================

# RUN FLASK

# ==================================================

if __name__ == "__main__":

    app.run(debug=True)
