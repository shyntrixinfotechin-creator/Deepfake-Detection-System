# pip install -r requirements.txt
# python app.py

from flask import Flask, request, render_template, send_from_directory, redirect, url_for, session
import os, uuid
import mysql.connector
import tensorflow as tf
import torch
from torchvision import models, transforms
from mtcnn import MTCNN
import cv2
from PIL import Image

# --- FLASK INIT -----------------------------------------------------
app = Flask(__name__)
app.secret_key = "deepfake_secret_key"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------------------------------------------------------
# MySQL DB Connection
# -------------------------------------------------------------------
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root2",
        database="deepfake_db"
    )

# -------------------------------------------------------------------
# Serve uploaded files
# -------------------------------------------------------------------
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# -------------------------------------------------------------------
# MODELS (same as yours)
# -------------------------------------------------------------------
image_model_path = r"model/final_model.keras"
image_model = tf.keras.models.load_model(image_model_path)
labels = ["Fake", "Real"]

video_model_path = r"model/best_resnet.pth"
device = "cuda" if torch.cuda.is_available() else "cpu"

video_model = models.resnet18(weights=None)
video_model.fc = torch.nn.Linear(video_model.fc.in_features, 2)
video_model.load_state_dict(torch.load(video_model_path, map_location=device))
video_model.eval()
video_model.to(device)

transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224,224)),
    transforms.ToTensor(),
    transforms.Normalize([0.5,0.5,0.5], [0.5,0.5,0.5])
])

mtcnn = MTCNN()

# -------------------------------------------------------------------
@app.route('/')
def home():
    return render_template('index.html')

# -------------------------------------------------------------------
# IMAGE PREDICTION
# -------------------------------------------------------------------
@app.route('/predict_image', methods=['POST'])
def predict_image():
    try:
        if 'file' not in request.files:
            return render_template('index.html', error="No file submitted")

        file = request.files['file']
        if file.filename == "":
            return render_template('index.html', error="Empty filename")

        filename = f"{uuid.uuid4()}_{file.filename}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)

        img = tf.keras.utils.load_img(save_path, target_size=(256, 256))
        img = tf.keras.utils.img_to_array(img)
        img = tf.expand_dims(img, axis=0)

        yhat = image_model.predict(img)
        pred = labels[int(yhat[0] > 0.5)]

        return render_template(
            "index.html",
            prediction=f"Image Result: {pred}",
            preview=f"/uploads/{filename}"
        )
    except Exception as e:
        return render_template("index.html", error=str(e))

# -------------------------------------------------------------------
# VIDEO PREDICTION
# -------------------------------------------------------------------
@app.route('/predict_video', methods=['POST'])
def predict_video():
    try:
        if 'file' not in request.files:
            return render_template('index.html', error="No video submitted")

        file = request.files['file']
        filename = f"{uuid.uuid4()}.mp4"
        video_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(video_path)

        fake = real = frame_i = 0
        cap = cv2.VideoCapture(video_path)

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_i += 1
            if frame_i % 3 != 0:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = mtcnn.detect_faces(rgb)
            if not faces:
                continue

            x1, y1, w, h = faces[0]['box']
            pad = int(min(w, h) * 0.25)
            x1 = max(0, x1 - pad); y1 = max(0, y1 - pad)
            x2 = min(frame.shape[1], x1 + w + pad * 2)
            y2 = min(frame.shape[0], y1 + h + pad * 2)

            face_img = rgb[y1:y2, x1:x2]
            if face_img.size == 0:
                continue

            face_tensor = transform(face_img).unsqueeze(0).to(device)
            with torch.no_grad():
                pred = torch.argmax(video_model(face_tensor)).item()

            if pred == 0: real += 1
            else: fake += 1

        cap.release()
        total = fake + real
        if total == 0:
            return render_template("index.html", error="No detectable face found!")

        fake_ratio = fake / total
        result = f"Deepfake Likely ({fake_ratio*100:.1f}% fake)" if fake_ratio > 0.15 else f"Likely Real ({fake_ratio*100:.1f}% fake)"

        return render_template("index.html", prediction=result, preview=f"/uploads/{filename}")

    except Exception as e:
        return render_template("index.html", error=str(e))

# -------------------------------------------------------------------
# COMPLAINT FORM
# -------------------------------------------------------------------
@app.route('/complaint')
def complaint():
    return render_template("complaint.html")

@app.route('/submit_complaint', methods=['POST'])
def submit_complaint():
    try:
        name = request.form.get("name")
        age = request.form.get("age")
        gender = request.form.get("gender")
        mobile = request.form.get("mobile")
        desc = request.form.get("desc")

        img_name = None
        file = request.files.get("file")
        if file and file.filename != "":
            img_name = f"complaint_{uuid.uuid4()}_{file.filename}"
            file.save(os.path.join(UPLOAD_FOLDER, img_name))

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO complaints (name, age, gender, mobile, description, image) VALUES (%s,%s,%s,%s,%s,%s)",
            (name, age, gender, mobile, desc, img_name)
        )
        db.commit()
        cursor.close()
        db.close()

        return render_template("complaint.html", message="Complaint filed successfully!")
    except Exception as e:
        return render_template("complaint.html", error=str(e))

# -------------------------------------------------------------------
# ADMIN LOGIN + PANEL
# -------------------------------------------------------------------
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == "POST":
        user = request.form.get("username")
        pw = request.form.get("password")

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM admin_users WHERE username=%s AND password=%s",
            (user, pw)
        )
        admin = cursor.fetchone()

        if admin:
            session['admin'] = True
            return redirect(url_for('admin_panel'))

        return render_template("admin_login.html", error="Invalid credentials")

    # GET request:
    return render_template("admin_login.html")

@app.route('/login', methods=['POST'])
def login():
    user = request.form.get("username")
    pw = request.form.get("password")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admin_users WHERE username=%s AND password=%s", (user, pw))
    admin = cursor.fetchone()

    if admin:
        session['admin'] = True
        return redirect(url_for('admin_panel'))

    return render_template("admin_login.html", error="Invalid credentials")

@app.route('/panel')
def admin_panel():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM complaints ORDER BY id DESC")
    complaints = cursor.fetchall()
    return render_template("admin_panel.html", complaints=complaints)

# -------------------------------------------------------------------
# DELETE COMPLAINT
# -------------------------------------------------------------------
@app.route('/delete/<int:id>')
def delete(id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM complaints WHERE id=%s", (id,))
    db.commit()
    cursor.close()
    db.close()
    return redirect(url_for('admin_panel'))

# -------------------------------------------------------------------
# MARK RESOLVED
# -------------------------------------------------------------------
@app.route('/resolve/<int:id>')
def resolve(id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE complaints SET status='Resolved' WHERE id=%s", (id,))
    db.commit()
    cursor.close()
    db.close()
    return redirect(url_for('admin_panel'))

# -------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)