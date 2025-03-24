from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev')

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEBUG'] = True
app.config['MAIL_SUPPRESS_SEND'] = False
app.config['MAIL_TIMEOUT'] = 30

mail = Mail(app)
print("app is running")

# MongoDB configuration
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client.user_database 

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = db.users.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            session['user_email'] = email
            session['role'] = user.get('role', 'staff')
            # Removed welcome email here. Task assignment email is sent when a task is assigned.
            return redirect(url_for('dashboard'))
        
        return 'Invalid credentials'
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            role = request.form.get('role', 'staff')
            hashed_password = generate_password_hash(request.form['password'])
            
            db.users.insert_one({
                'name': name,
                'email': email,
                'password': hashed_password,
                'role': role
            })
            return redirect(url_for('login'))
        except Exception as e:
            print("Error during registration:", e)
            return "An error occurred during registration", 500
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    role = session.get('role')
    return render_template('dashboard.html', role=role)

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    # Only allow access if the logged-in user is an admin
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Admin assigns a task to a staff member
        staff_email = request.form['staff_email']
        task_name = request.form['task_name']
        description = request.form['description']
        
        db.tasks.insert_one({
            'staff_email': staff_email,
            'task_name': task_name,
            'description': description,
            'status': 'pending'
        })
        
        # Send task assignment email to the staff member
        send_task_email(staff_email, task_name, description)
        return redirect(url_for('admin_panel'))
    
    tasks = list(db.tasks.find())
    return render_template('admin.html', tasks=tasks)

@app.route('/staff', methods=['GET', 'POST'])
def staff_panel():
    # Only allow access if the logged-in user is a staff member
    if session.get('role') != 'staff':
        return redirect(url_for('dashboard'))
    
    user_email = session.get('user_email')
    
    if request.method == 'POST':
        # Update task status for the given task
        task_id = request.form['task_id']
        new_status = request.form['status']
        db.tasks.update_one({'_id': ObjectId(task_id)}, {'$set': {'status': new_status}})
        return redirect(url_for('staff_panel'))
    
    tasks = list(db.tasks.find({'staff_email': user_email}))
    return render_template('staff.html', tasks=tasks)

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('role', None)
    return redirect(url_for('login'))

def send_task_email(email, task_name, description):
    msg = Message("New Task Assignment",
                  sender=os.environ.get('MAIL_USERNAME'),
                  recipients=[email])
    msg.body = (
        f"You have been assigned a new task:\n\n"
        f"Task: {task_name}\n\n"
        f"Description:\n{description}\n\n"
        f"Please log in to update the status."
    )
    mail.send(msg)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
