from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3, uuid, base64, requests, io, os
from PIL import Image
from decimal import Decimal
import tempfile
import logging
from dotenv import load_dotenv
load_dotenv()

application = Flask(__name__)
application.secret_key = 'supersecretkey'

# 📁 Local file saving instead of S3
UPLOAD_FOLDER = 'ArtWork/static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# External APIs
PRICE_API = "https://gi96frqbc5.execute-api.eu-west-1.amazonaws.com"
AUTH_API = "https://rf83t8chb1.execute-api.eu-west-1.amazonaws.com"
GEO_API = "https://ipapi.co/json/"
CURRENCY_API = "https://api.exchangerate-api.com/v4/latest/USD"

# SQLite DB Path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")

# 🧱 Init DB
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS artworks (
                id TEXT PRIMARY KEY,
                title TEXT,
                uploader TEXT,
                price TEXT,
                authenticity TEXT,
                caption TEXT,
                color_url TEXT,
                vision_desc TEXT,
                status TEXT,
                currency_price TEXT,
                image_url TEXT
            )
        ''')
        conn.commit()

init_db()

# 💾 Save image locally
def save_image_locally(image_bytes, filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    return f"uploads/{filename}"

# 🧠 Caption API (still huggingface or fallback text)
def huggingface_caption(image_bytes):
    try:
        HF_TOKEN = os.getenv("HF_API_KEY", "")
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/octet-stream"
        }
        response = requests.post(
            "https://api-inference.huggingface.co/models/nlpconnect/vit-gpt2-image-captioning",
            headers=headers,
            data=image_bytes
        )
        result = response.json()
        if isinstance(result, list) and "generated_text" in result[0]:
            return result[0]["generated_text"]
    except Exception as e:
        print("Caption Error:", e)
    return "Could not generate description"

# 💱 Currency Conversion
def get_currency_conversion(price_usd):
    try:
        geo = requests.get(GEO_API).json()
        currency = geo.get("currency", "INR")
        rates = requests.get(CURRENCY_API).json().get("rates", {})
        converted = round(float(price_usd) * rates.get(currency, 1), 2)
        return f"{converted} {currency}"
    except Exception as e:
        print("Currency Conversion Error:", e)
        return f"{price_usd} USD"

# 🏠 Home
@application.route('/')
def home():
    return render_template("home.html")

# 🔐 Register
@application.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            try:
                c.execute("INSERT INTO users VALUES (?, ?, ?)", (username, password, role))
                conn.commit()
                return redirect(url_for("login"))
            except:
                return render_template("register.html", error="Username already exists")
    return render_template("register.html")

# 🔐 Login
@application.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=? AND role=?", (username, password, role))
            user = c.fetchone()
        if user:
            session["user"] = username
            session["role"] = role
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

# 📊 Dashboard
@application.route('/dashboard', methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    role = session["role"]

    if role == "seller":
        if request.method == "POST":
            try:
                title = request.form["title"]
                image = request.files.get("image")

                if not image:
                    return render_template("seller_dashboard.html", error="No image uploaded.")

                image_bytes = image.read()
                b64img = base64.b64encode(image_bytes).decode()

                # Price API
                price_resp = requests.post(PRICE_API, json={"file": b64img})
                price_data = price_resp.json() if price_resp.status_code == 200 else {}
                price = str(price_data.get("predicted_price", "Not Available"))

                # Auth API
                auth_resp = requests.post(AUTH_API, json={"file": b64img})
                auth_data = auth_resp.json() if auth_resp.status_code == 200 else {}
                auth = auth_data.get("status", "Unknown")

                # Caption
                vision = huggingface_caption(image_bytes)

                # Color
                avg = Image.open(io.BytesIO(image_bytes)).resize((1, 1)).getpixel((0, 0))
                hex_color = '%02x%02x%02x' % avg
                caption = f"Dominant color: RGB({avg[0]}, {avg[1]}, {avg[2]})"
                color_url = f"https://www.thecolorapi.com/id?hex={hex_color}"

                # Currency
                currency_price = get_currency_conversion(price)

                # Save locally
                filename = f"{uuid.uuid4()}.jpg"
                image_url = save_image_locally(image_bytes, filename)

                # Store in DB
                art_id = str(uuid.uuid4())
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute('''INSERT INTO artworks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                        art_id, title, username, price, auth, caption, color_url, vision,
                        "Available", currency_price, image_url
                    ))
                    conn.commit()
            except Exception as e:
                print("Error during artwork upload:", e)
                return render_template("seller_dashboard.html", error="Upload failed.")

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM artworks WHERE uploader=?", (username,))
            columns = [desc[0] for desc in c.description]
            artworks = [dict(zip(columns, row)) for row in c.fetchall()]
        return render_template("seller_dashboard.html", artworks=artworks)

    else:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM artworks WHERE status='Available'")
            columns = [desc[0] for desc in c.description]
            artworks = [dict(zip(columns, row)) for row in c.fetchall()]
        return render_template("buyer_dashboard.html", artworks=artworks)

# 🛒 Buy
@application.route('/buy/<art_id>')
def buy_art(art_id):
    if "user" not in session or session["role"] != "buyer":
        return redirect(url_for("login"))
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE artworks SET status='Booked' WHERE id=?", (art_id,))
        conn.commit()
    return redirect(url_for("dashboard"))

# 🗑️ Delete
@application.route('/delete/<art_id>')
def delete_art(art_id):
    if "user" not in session or session["role"] != "seller":
        return redirect(url_for("login"))

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Get image URL from DB
        c.execute("SELECT image_url FROM artworks WHERE id=?", (art_id,))
        row = c.fetchone()

        if row and row[0]:
            try:
                # Safely extract filename and build full path
                safe_filename = os.path.basename(row[0])
                file_path = os.path.join(application.root_path, 'static', 'uploads', safe_filename)

                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"✅ Deleted file: {file_path}")
                else:
                    print(f"⚠️ File not found: {file_path}")
            except Exception as e:
                print(f"❌ Error deleting image: {e}")

        # Delete artwork record from DB
        c.execute("DELETE FROM artworks WHERE id=?", (art_id,))
        conn.commit()

    return redirect(url_for("dashboard"))
# 🔓 Logout
@application.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("home"))

# 🔧 Run Flask App
if __name__ == "__main__":
    application.run(host="0.0.0.0", port=8080, debug=True)