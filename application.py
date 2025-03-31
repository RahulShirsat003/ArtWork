from flask import Flask, render_template, request, redirect, url_for, session
import boto3, uuid, base64, requests, io, os
from PIL import Image
from decimal import Decimal

application = Flask(__name__)
application.secret_key = 'supersecretkey'

# AWS Resources
region = "eu-west-1"
dynamodb = boto3.resource("dynamodb", region_name=region)
s3 = boto3.client("s3", region_name=region)

users_table = dynamodb.Table("UserArt")
artworks_table = dynamodb.Table("Artworks")
S3_BUCKET = "bucketart325"

# External APIs
PRICE_API = "https://gi96frqbc5.execute-api.eu-west-1.amazonaws.com"
AUTH_API = "https://rf83t8chb1.execute-api.eu-west-1.amazonaws.com"
GEO_API = "https://ipapi.co/json/"
CURRENCY_API = "https://api.exchangerate-api.com/v4/latest/USD"

# 🔼 Upload to S3
def upload_to_s3(file_bytes, filename):
    s3.put_object(Bucket=S3_BUCKET, Key=filename, Body=file_bytes, ContentType="image/jpeg", ACL='public-read')
    return f"https://{S3_BUCKET}.s3.{region}.amazonaws.com/{filename}"

# 🧠 HuggingFace Caption
def huggingface_caption(image_bytes):
    try:
        HF_TOKEN = os.environ.get("HF_API_KEY", "")
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "applicationlication/octet-stream"
        }
        response = requests.post(
            "https://api-inference.huggingface.co/models/nlpconnect/vit-gpt2-image-captioning",
            headers=headers,
            data=image_bytes
        )
        result = response.json()
        print("🧠 Caption API response:", result)
        if isinstance(result, list) and "generated_text" in result[0]:
            return result[0]["generated_text"]
        return "Could not generate description"
    except Exception as e:
        print("🧠 Caption ERROR:", e)
        return "Could not generate description"

# 🌍 Currency Conversion
def get_currency_conversion(price_usd):
    try:
        geo = requests.get(GEO_API).json()
        currency = geo.get("currency", "INR")
        rates = requests.get(CURRENCY_API).json().get("rates", {})
        converted = round(float(price_usd) * rates.get(currency, 1), 2)
        return f"{converted} {currency}"
    except Exception as e:
        print("🌍 Conversion error:", e)
        return f"{price_usd} USD"

# 🏠 Home Page
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
        try:
            users_table.put_item(Item={
                'username': username,
                'password': password,
                'role': role
            })
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
        response = users_table.get_item(Key={'username': username})
        user = response.get("Item")

        if user and user["password"] == password and user["role"] == role:
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
            title = request.form["title"]
            image = request.files["image"]
            image_bytes = image.read()
            b64img = base64.b64encode(image_bytes).decode()

            # Predict Price
            price_resp = requests.post(PRICE_API, json={"file": b64img}).json()
            print("💰 Price API:", price_resp)
            price = Decimal(str(price_resp.get("predicted_price", "0")))

            # Auth Check
            auth_resp = requests.post(AUTH_API, json={"file": b64img}).json()
            print("🔐 Auth API:", auth_resp)
            auth = auth_resp.get("status", "Unknown")

            # Caption
            vision = huggingface_caption(image_bytes)

            # Color Info
            avg = Image.open(io.BytesIO(image_bytes)).resize((1,1)).getpixel((0,0))
            hex_color = '%02x%02x%02x' % avg
            caption = f"Dominant color: RGB({avg[0]}, {avg[1]}, {avg[2]})"
            color_url = f"https://www.thecolorapi.com/id?hex={hex_color}"

            # Currency
            currency_price = get_currency_conversion(price)

            # Upload
            s3_name = f"{uuid.uuid4()}.jpg"
            image_url = upload_to_s3(image_bytes, s3_name)

            # Store
            artworks_table.put_item(Item={
                "id": str(uuid.uuid4()),
                "title": title,
                "uploader": username,
                "price": price,
                "authenticity": auth,
                "caption": caption,
                "color_url": color_url,
                "vision_desc": vision,
                "status": "Available",
                "currency_price": str(currency_price),
                "image_url": image_url
            })

        items = artworks_table.scan()["Items"]
        artworks = [item for item in items if item["uploader"] == username]
        return render_template("seller_dashboard.html", artworks=artworks)

    else:  # Buyer
        items = artworks_table.scan()["Items"]
        return render_template("buyer_dashboard.html", artworks=items)

# 🛒 Buy
@application.route('/buy/<art_id>')
def buy_art(art_id):
    if "user" not in session or session["role"] != "buyer":
        return redirect(url_for("login"))
    artworks_table.update_item(
        Key={"id": art_id},
        UpdateExpression="set #s = :val",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":val": "Booked"}
    )
    return redirect(url_for("dashboard"))

# 🗑️ Delete
@application.route('/delete/<art_id>')
def delete_art(art_id):
    if "user" not in session or session["role"] != "seller":
        return redirect(url_for("login"))
    artworks_table.delete_item(Key={"id": art_id})
    return redirect(url_for("dashboard"))

# 🔓 Logout
@application.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=8080, debug=True)