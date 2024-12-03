from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import random
import time

app = Flask(__name__)
app.secret_key = "supersecretkey"
socketio = SocketIO(app)

from flask_mail import Mail, Message

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'tvarshitha.123@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'yxfc jgns euww yzup'  # Replace with your email's app password
app.config['MAIL_DEFAULT_SENDER'] = 'tvarshitha.123@gmail.com'  # Replace with your email
mail = Mail(app)

# Initialize the user and collection databases
def init_db():
    # Database setup for MySQL
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="wms"
    )
    cursor = conn.cursor()

    # User table setup
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL
    )
    """)

    # Collection request table setup
    cursor.execute('''CREATE TABLE IF NOT EXISTS request_collection (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        collector_name VARCHAR(255),
                        collector_email VARCHAR(255),
                        waste_type VARCHAR(255),
                        quantity INT,
                        collection_date DATE,
                        collection_time TIME,
                        address TEXT
                    )''')
    
    
    conn.commit()
    conn.close()

# Call the function to set up the database
init_db()

# Home route
@app.route("/")
def home():
    if "user_id" in session:
        return render_template("home.html")
    else:
        return redirect(url_for("login"))

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="wms"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect(url_for("home"))
        else:
            flash("Invalid email or password", "danger")

    return render_template("login.html")

# Register route
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password, method="sha256")

        try:
            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="root",
                database="wms"
            )
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_password))
            conn.commit()
            conn.close()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except mysql.connector.IntegrityError:
            flash("Email already registered", "danger")

    return render_template("register.html")

# Logout route
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# admin login route
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="wms"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE email = %s", (email,))
        admin = cursor.fetchone()
        conn.close()

        if admin and check_password_hash(admin[2], password):
            session["admin_id"] = admin[0]
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin credentials", "danger")

    return render_template("admin_login.html", registering=False)

# admin dashboard route
@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="wms"
    )
    cursor = conn.cursor()
    cursor.execute("SELECT id, collector_name, collector_email, waste_type, quantity, collection_date, collection_time, address, status FROM request_collection")
    collection_requests = cursor.fetchall()
    conn.close()

    
    return render_template("admin_dashboard.html",collection_requests=collection_requests)


# admin register route
@app.route("/admin_register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password, method="sha256")

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="wms"
        )
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO admins (email, password) VALUES (%s, %s)", (email, hashed_password))
            conn.commit()
            flash("Admin registration successful!", "success")
            return redirect(url_for("admin_login"))
        except mysql.connector.IntegrityError:
            flash("Email already registered", "danger")
        finally:
            conn.close()

    return render_template("admin_login.html", registering=True)

@app.route('/update_request_status/<int:request_id>', methods=["POST"])
def update_request_status(request_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    status = request.form["status"]

    # Update the status in the database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="wms"
    )
    cursor = conn.cursor()
    
    # Fetch user email to send the update
    cursor.execute("SELECT collector_email FROM request_collection WHERE id = %s", (request_id,))
    collector_email = cursor.fetchone()
    if not collector_email:
        flash("Request not found!", "danger")
        return redirect(url_for("admin_dashboard"))

    # Update the status
    cursor.execute("UPDATE request_collection SET status = %s WHERE id = %s", (status, request_id))
    conn.commit()
    conn.close()

    # Send email to user
    try:
        msg = Message("Waste Collection Status Update",
                      recipients=[collector_email[0]])
        msg.body = f"Hello,\n\nYour waste collection request (ID: {request_id}) has been updated to '{status}'.\n\nThank you for using our service!\n\nBest regards,\nWaste Management System"
        mail.send(msg)
        flash("Status updated and email sent to the user successfully!", "success")
    except Exception as e:
        flash(f"Failed to send email: {e}", "danger")

    return redirect(url_for("admin_dashboard"))


    

# Request Collection route
@app.route("/request-collection", methods=["GET", "POST"])
def request_collection():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        collector_name = request.form["collector_name"]
        collector_email = request.form["collector_email"]
        waste_type = request.form["waste_type"]
        quantity = request.form["quantity"]
        collection_date = request.form["collection_date"]
        collection_time = request.form["collection_time"]
        address = request.form["address"]

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="wms"
        )
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO request_collection
                          (collector_name, collector_email, waste_type, quantity, collection_date, collection_time, address)
                          VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                       (collector_name, collector_email, waste_type, quantity, collection_date, collection_time, address))
        conn.commit()
        conn.close()
        # Example validation or processing
        if not collector_name or not collector_email:
            flash('Collector name and email are required!', 'danger')
        else:
            # Process the form data, e.g., store in database or do something else
            flash('Collection request submitted successfully!', 'success')
            #return redirect(url_for('home'))  # Redirect to prevent form resubmission
            

    return render_template("request_collection.html")

# Delete request route
@app.route('/delete_request/<int:request_id>', methods=["POST"])
def delete_request(request_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="wms"
    )
    cursor = conn.cursor()
    cursor.execute("DELETE FROM request_collection WHERE id = %s", (request_id,))
    conn.commit()
    conn.close()
    
    flash("Request deleted successfully!", "success")
    return redirect(url_for("waste_collections"))

# Ensure the waste collections function selects the 'id' as well
@app.route('/waste_collections')
def waste_collections():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="wms"
    )
    cursor = conn.cursor()
    cursor.execute("SELECT id, collector_name, collector_email, waste_type, quantity, collection_date, collection_time, address FROM request_collection")
    collection_requests = cursor.fetchall()
    conn.close()
    return render_template('waste_collections.html', collection_requests=collection_requests)




# Simulated vehicle positions (to mimic GPS data)
vehicles = {
    "Hyderabad": {
        "Banjara Hills": {"lat": 17.4128, "lng": 78.4316},
        "Madhapur": {"lat": 17.4483, "lng": 78.3915},
    },
    "Lucknow": {
        "Hazratganj": {"lat": 26.8500, "lng": 80.9462},
        "Indira Nagar": {"lat": 26.8779, "lng": 80.9853},
    },
    "Bangalore": {
        "Koramangala": {"lat": 12.9345, "lng": 77.6266},
        "Whitefield": {"lat": 12.9698, "lng": 77.7499},
    },
}

@socketio.on("request_vehicle_update")
def send_vehicle_update(data):
    """Emit simulated vehicle positions."""
    city = data.get("city")
    area = data.get("area")
    if city in vehicles and area in vehicles[city]:
        position = vehicles[city][area]
        
        # Simulate movement by adding randomness
        position["lat"] += random.uniform(-0.0001, 0.0001)
        position["lng"] += random.uniform(-0.0001, 0.0001)
        
        emit("vehicle_update", {"city": city, "area": area, "position": position}, broadcast=True)

@app.route("/real_time_tracking")
def real_time_tracking():
    return render_template("track.html")



# City and Area data
city_areas = {
    "Hyderabad": ["Banjara Hills", "Madhapur"],
    "Lucknow":["Hazratganj", "Indira Nagar"],
    "Bangalore": ["Koramangala", "Whitefield"],
    # Add more cities and areas as needed
}

route_info = {
    "Hyderabad": {
        "Banjara Hills": [
            {"route_name": "Route 1", "route_places": ["Necklace Road", "Banjara Lake", "Road No. 10", "Jubilee Hills"], "collection_time": "08:00:00"},
            {"route_name": "Route 2", "route_places": ["Banjara Lake", "Ameerpet", "Madhapur", "Gachibowli"], "collection_time": "09:00:00"}
        ],
        "Madhapur": [
            {"route_name": "Route 1", "route_places": ["HITEC City", "Cyber Towers", "Raidurg", "Banjara Hills"], "collection_time": "09:00:00"},
            {"route_name": "Route 2", "route_places": ["Cyber Towers", "Madhapur Main Road", "Gachibowli", "Kondapur"], "collection_time": "10:00:00"}
        ],
        # Add other areas and routes
    },
    "Lucknow": {
        "Hazratganj": [
            {"route_name": "Route 1", "route_places": ["Rumi Darwaza", "Imambara", "Bada Chauraha", "Nawab Wajid Ali Shah Zoological Garden"], "collection_time": "08:00:00"},
            {"route_name": "Route 2", "route_places": ["Vidhan Sabha", "Hazratganj Market", "Mahavir Mandir", "Charbagh"], "collection_time": "09:00:00"}
        ],
        "Indira Nagar": [
            {"route_name": "Route 1", "route_places": ["Indira Nagar Market", "Vikramshila Park", "Jankipuram", "Alambagh"], "collection_time": "08:30:00"},
            {"route_name": "Route 2", "route_places": ["BBD University", "Indira Nagar Police Station", "Bans Mandi", "Shahid Smarak"], "collection_time": "10:00:00"}
        ],
    },
    "Bangalore": {
        "Koramangala": [
            {"route_name": "Route 1", "route_places": ["Koramangala 5th Block", "Madiwala", "Silk Board", "HSR Layout"], "collection_time": "07:00:00"},
            {"route_name": "Route 2", "route_places": ["Forum Mall", "Ejipura", "Bellandur", "Marathahalli"], "collection_time": "08:30:00"}
        ],
        "Whitefield": [
            {"route_name": "Route 1", "route_places": ["Whitefield Main Road", "ITPL", "Varthur", "Kadugodi"], "collection_time": "08:00:00"},
            {"route_name": "Route 2", "route_places": ["ITPL", "Graphite India", "Kundalahalli", "Brookefield"], "collection_time": "09:30:00"}
        ],
        # Add other areas and routes
    }
    # Add more cities and areas if necessary
}


@app.route("/route_info", methods=["GET", "POST"])
def route_info_page():
    city = request.args.get("city")  # To get the city from the selection
    areas = city_areas.get(city, []) if city else []
    return render_template("route_info.html", city=city, areas=areas, route_info=route_info)
@app.route("/select_area", methods=["GET"])
def select_area():
    city = request.args.get("city")
    areas = city_areas.get(city, [])
    return render_template("route_info.html", city=city, areas=areas, route_info=route_info)

if __name__ == "__main__":
    socketio.run(app, debug=True)
