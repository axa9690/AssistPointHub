import atexit
import datetime
from flask import Flask, abort, current_app, render_template, redirect, send_from_directory, session, url_for, flash, request
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from forms import RecurringExpenseForm, RegistrationForm, LoginForm , ExpenseForm
from database import query_db, insert_db, get_user_by_id, init_db,get_db,delete_db
import sys
import os
from werkzeug.utils import secure_filename
import random
import smtplib
from datetime import datetime
from flask import jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from flask import Flask
from flask import render_template, session, redirect, url_for
from database import get_expenses_by_category, get_total_income, get_total_expenses, get_budget, get_recent_transactions, get_budgets_and_expenses
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER





# Define your function to add recurring expenses
def add_scheduled_recurring_expenses():
    with app.app_context():
        
        # Fetch recurring expenses where next_due_date is today or earlier and they haven't ended
        recurring_expenses = query_db('''
            SELECT * FROM recurring_expenses
            WHERE next_due_date <= DATE('now') AND end_date >= DATE('now')
        ''')

        for rec_exp in recurring_expenses:
            user_id = rec_exp[1]
            category_id = rec_exp[6]
            amount = rec_exp[3]
            description = rec_exp[2]
            period = rec_exp[5]
            next_due_date = datetime.strptime(rec_exp[7], '%Y-%m-%d')
            while next_due_date.date() <=  datetime.today().date():
            # Add the expense to the expenses table
             insert_db('''
                INSERT INTO expenses (user_id, category_id, amount, date, description)
                VALUES (?, ?, ?, ?, ?)
            ''', [user_id, category_id, amount, next_due_date.strftime('%Y-%m-%d'), description])

            # Calculate the next due date based on the period
             if period == 'daily' or period=='Daily':
                next_due_date += timedelta(days=1)
             elif period == 'weekly' or period == 'Weekly':
                next_due_date += timedelta(weeks=1)
             elif period == 'monthly' or period == 'Monthly':
                next_due_date = next_due_date.replace(day=1) + timedelta(days=32)
                next_due_date = next_due_date.replace(day=1)  # Move to next month
             elif period == 'yearly' or period == 'Yearly':
                next_due_date = next_due_date.replace(year=next_due_date.year + 1)

            # Update the recurring expense with the next due date
             print ('Iam here')
             
             insert_db('''
                UPDATE recurring_expenses
                SET next_due_date = ?
                WHERE id = ?
            ''', [next_due_date.strftime('%Y-%m-%d'), rec_exp[0]])
            

# Function to start the scheduler
def start_scheduler():
    scheduler = BackgroundScheduler()
    
    # Schedule the job to run once a day (at midnight, for example)
    scheduler.add_job(func=add_scheduled_recurring_expenses, trigger="interval", minutes =1)
    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())


start_scheduler()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)

class User(UserMixin):
    def __init__(self, id, username, email, password):
        self.id = id
        self.username = username
        self.email = email
        self.password = password
from flask import redirect, url_for, session, request



@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.route('/')
@app.route('/home')
@login_required
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        insert_db('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                  (form.username.data, form.email.data, hashed_password))
        flash('Your account has been created! You can now log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = query_db('SELECT * FROM users WHERE email = ?', [form.email.data], one=True)
        if user and bcrypt.check_password_hash(user[3], form.password.data):
            user_obj = User(id=user[0], username=user[1], email=user[2], password=user[3])
            login_user(user_obj, remember=form.remember.data)
            if user[1]=='Admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout',methods=['POST'])
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Logged out sucessfully','success')
    return redirect(url_for('login'))
# app.py



@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
  

    user_id = current_user.id
    user_name= query_db("SELECT username FROM USERS WHERE id=?",[current_user.id,])
    # Fetch data from the database or backend
   
    
    # Pass the data to the template
    categories= query_db("SELECT * FROM category ")


    query = '''
        SELECT 
            strftime('%m', e.date) AS month,
            IFNULL(SUM(CASE WHEN c.is_income = 1 THEN e.amount END), 0) AS total_income,
            IFNULL(SUM(CASE WHEN c.is_income = 0 THEN e.amount END), 0) AS total_expense
        FROM 
            expenses e
        JOIN 
            category c ON e.category_id = c.id
        WHERE 
            
            strftime('%Y', e.date) = strftime('%Y', 'now')
        GROUP BY 
            month
        HAVING 
            total_expense > 0;
    '''
    monthly_data = query_db(query, [])
    return render_template('admin_dashboard.html', 
                           user_name=user_name,
                            
                            budget=budget, 
                            
                            
                            monthly_data=monthly_data)
    
@app.route('/admin_request', methods=['GET', 'POST'])
@login_required  # Assuming only logged-in users can access this
def admin_request():
    search_query = request.args.get('search_query', '')  # Fetch search query
    sort_by_date = request.args.get('sort_by_date', 'desc')  # Sort by date (default descending)
    
    # Fetch unresolved requests first
    query = '''
        SELECT id, email, concern, timestamp, resolved, consern_id
        FROM concerns
        WHERE  (concern LIKE ? OR email LIKE ? OR consern_id LIKE ?)
        ORDER BY resolved asc, timestamp {}'''.format(sort_by_date) 
    
    search_query_param = f'%{search_query}%'  # Search pattern for query
    unresolved_requests = query_db(query, [search_query_param, search_query_param,search_query_param])
    
    return render_template('admin_request.html', requests=unresolved_requests)

# Mark request as resolved
@app.route('/resolve_request/<int:request_id>', methods=['POST'])
@login_required
def resolve_request(request_id):
    query = '''UPDATE concerns SET resolved = 1 WHERE id = ?'''
    insert_db(query, [request_id])
    flash('Request marked as resolved')
    return redirect(url_for('admin_request'))

# Delete a request
@app.route('/delete_request/<int:request_id>', methods=['POST'])
@login_required
def delete_request(request_id):
    query = '''DELETE FROM concerns WHERE id = ?'''
    insert_db(query, [request_id])
    flash('Request deleted successfully')
    return redirect(url_for('admin_request'))


@app.route('/dashboard')
@login_required
def dashboard():
  

    user_id = current_user.id
    user_name= query_db("SELECT username FROM USERS WHERE id=?",[current_user.id,])
    # Fetch data from the database or backend
    total_income = get_total_income(user_id)
    total_expenses = get_total_expenses(user_id)
    budget = get_budget(user_id)  # Fetch user's budget
    
    budgets_expenses = get_budgets_and_expenses(user_id)

    recent_transactions = get_recent_transactions(user_id)  # Fetch recent transactions
    expenses_by_category= get_expenses_by_category(user_id)
    # Pass the data to the template
    categories= query_db("SELECT * FROM category ")
    print(expenses_by_category)
    if not budget:
        budget=-1
    query = '''
        SELECT 
            strftime('%m', e.date) AS month,
            IFNULL(SUM(CASE WHEN c.is_income = 1 THEN e.amount END), 0) AS total_income,
            IFNULL(SUM(CASE WHEN c.is_income = 0 THEN e.amount END), 0) AS total_expense
        FROM 
            expenses e
        JOIN 
            category c ON e.category_id = c.id
        WHERE 
            e.user_id = ? 
            AND strftime('%Y', e.date) = strftime('%Y', 'now')
        GROUP BY 
            month
        HAVING 
            total_expense > 0;
    '''
    monthly_data = query_db(query, [user_id])
    return render_template('dashboard.html', 
                           user_name=user_name,
                            total_income=total_income, 
                            total_expenses=total_expenses, 
                            budget=budget, 
                            recent_transactions=recent_transactions,expenses_by_category=expenses_by_category,
                            categories=categories, budgets_expenses=budgets_expenses,
                            monthly_data=monthly_data)
    


@app.route('/submit_concern', methods=['POST'])
def submit_concern():
    data = request.get_json()
    print(data)
    email = data.get('email')
    concern = data.get('concern')
    concern_id=random.randint(1,1000000000)
    user_id=0
    if current_user.is_authenticated:
      user_id = current_user.id
    print(user_id)
    print(concern)
    print(email)
    if not email or not concern:
        print(user_id)
        return jsonify({'error': 'Email and concern are required.'}), 400
    print(user_id)
    insert_db('INSERT INTO concerns (user_id, email, concern,consern_id,resolved) VALUES (?, ?, ?,?,?)', 
             [user_id, email, concern,concern_id,0])
    msg=f'Your consern has been submitted successfully. If you want further assistance please use the consern ID {concern_id} when you reach out to us'
    
    send_msg(email,msg)
    return jsonify({'message': 'Concern submitted successfully!'}), 200


@app.route('/all_transactions',methods=['GET','POST'])
@login_required
def all_transactions():
    return render_template('all_transactions.html')



@app.route('/contact_us',methods=['GET','POST'])
@login_required
def contact_us():
    return render_template('contact_us.html')


@app.route('/add_expenses',methods=['GET','POST'])
@login_required
def add_expenses():
    if request.method == 'POST':
        # Extract form data
        date = request.form['date']
        description = request.form['description']
        amount = float(request.form['amount'])
        category_id = request.form['category']
        file = request.files['document']
        type = int(request.form['type'])
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            file_path = None
        # Insert the new expense into the database
        insert_db('INSERT INTO expenses (user_id, date, description, amount, category_id, document, is_income) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                  (current_user.id, date, description, amount, category_id, file_path, type))
        
        current_month = datetime.now().month
        current_year = datetime.now().year

        # Get total expenses for this category in the current month and year
        total_expenses = query_db('''
            SELECT SUM(amount) 
            FROM expenses 
            WHERE category_id = ? AND user_id = ? AND strftime('%m', date) = ? AND strftime('%Y', date) = ?''', 
            [category_id, current_user.id, f'{current_month:02d}', str(current_year)])[0][0]

        # Get the budget for this category
        result = query_db('SELECT monthly_budget FROM budgets WHERE user_id = ? AND category_id = ?', [current_user.id , category_id])
        if result:
          category_budget = result[0][0]
        else:
    # Handle the case when there is no budget
          category_budget = 0   
        catego = query_db('SELECT name From category WHERE id = ?', [category_id])
        print (total_expenses)
        print(category_budget)
        if total_expenses > category_budget:
            # Create a notification for the user
            message = f'You have exceeded the budget for the {catego[0][0]} by {total_expenses - category_budget}!'
            insert_db('INSERT INTO notifications (user_id, message) VALUES (?, ?)', [current_user.id, message])
            email = query_db('SELECT email FROM users WHERE id=?', [current_user.id], one=True)[0]
            send_msg(email ,message)
        

        flash('Record added successfully!', 'success')
        return redirect(url_for('view_expenses'))

    # Fetch categories for the form dropdown
    categories = query_db('SELECT id, name, is_income FROM category')
    print(categories)
    return render_template('add_expenses.html', categories=categories)

@app.route('/view_expenses', methods=['GET', 'POST'])
@login_required
def view_expenses():
    # Get filter and search parameters from the request
    search_description = request.args.get('search', '')
    category_v = request.args.get('category', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    amount_comparison = request.args.get('amount_comparison', '')
    amount_value = request.args.get('amount_value', '')
    sort_by=request.args.get('sort_by')
    # Base query to fetch expenses
    query = '''
        SELECT e.id, e.date, e.description, e.amount, e.document, c.name AS category_name 
        FROM expenses e 
        JOIN category c ON e.category_id = c.id 
        WHERE e.user_id = ?
    '''
    params = [current_user.id]
    categories = query_db('SELECT id, name, is_income FROM category')
    # Apply search filter if provided
    if search_description:
        query += ' AND e.description LIKE ?'
        params.append(f'%{search_description}%')
   
    # Apply category filter if provided
    if category_v:
        category_v =int(category_v)
        query += ' AND c.id = ?'
        params.append(int(category_v))

    # Apply date filters if provided
    if start_date:
        query += ' AND e.date >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND e.date <= ?'
        params.append(end_date)

    # Apply amount filters if provided
    if amount_comparison and amount_value:
        if amount_comparison == 'equal':
            query += ' AND e.amount = ?'
        elif amount_comparison == 'greater':
            query += ' AND e.amount > ?'
        elif amount_comparison == 'less':
            query += ' AND e.amount < ?'
        params.append(amount_value)
    if sort_by:
        if sort_by == "date_asc":
            query += " ORDER BY e.date ASC"
        elif sort_by == "date_desc":
            query += " ORDER BY e.date DESC"
        elif sort_by == "amount_asc":
            query += " ORDER BY e.amount ASC"
        elif sort_by == "amount_desc":
            query += " ORDER BY e.amount DESC"

    expenses = query_db(query, params)
    
    return render_template(
        'view_expenses.html',
        expenses=expenses,
        search=search_description,
        category_v=category_v,
        start_date=start_date,
        end_date=end_date,
        amount_comparison=amount_comparison,
        amount_value=amount_value,
        categories =categories,
        sort_by=sort_by
    )

    

@app.route('/manage_expenses')
@login_required
def manage_expenses():
   return render_template('manage_expenses.html')

@app.route('/edit_expense/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    # Fetch the expense from the database
    expense = query_db('SELECT * FROM expenses WHERE id = ? AND user_id = ?', [expense_id, current_user.id], one=True)
    
    if not expense:
        flash('Expense not found or unauthorized access.', 'danger')
        return redirect(url_for('view_expenses'))
    
    if request.method == 'POST':
        description = request.form['description']
        amount = request.form['amount']
        date = request.form['date']
        category_id = request.form['category']

        # Handle file upload if a new document is provided
        file = request.files['document']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            file_path = expense[6]  # Keep the old document if no new one is uploaded

        # Update the database with the new values
        insert_db(
            'UPDATE expenses SET description = ?, amount = ?, date = ?, category_id = ?, document = ? WHERE id = ? AND user_id = ?',
            (description, amount, date, category_id, file_path, expense_id, current_user.id)
        )

        flash('Expense updated successfully!', 'success')
        return redirect(url_for('view_expenses'))

    # Fetch categories for the form
    categories = query_db('SELECT * FROM category')
    
    return render_template('edit_expense.html', expense=expense, categories=categories)

@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    # Delete the expense from the database
    delete_db('DELETE FROM expenses WHERE id = ? AND user_id = ?', [expense_id, current_user.id])
    
    flash( 'Expense deleted successfully!' , 'success')
    return redirect(url_for('view_expenses'))

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    upload_folder = app.config['UPLOAD_FOLDER']
    try:
        return send_from_directory(upload_folder, filename[8:], as_attachment=True)
    except FileNotFoundError:
        abort(404)
@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    print("file name is:"+filename[8:])
    upload_folder = app.config['UPLOAD_FOLDER']
    print(f"Upload folder path: {upload_folder}")

    return send_from_directory(app.config['UPLOAD_FOLDER'], filename[8:])

@app.route('/add_recurring_expense', methods=['GET', 'POST'])
@login_required
def add_recurring_expense():
    form = RecurringExpenseForm()
    if form.validate_on_submit():
        start_date = form.start_date.data
        description = form.description.data
        amount = float(form.amount.data)
        period = form.period.data
        category_id = int(form.category.data)
        end_date = form.end_date.data or None
        
        # Calculate the next due date (initially, it's the start date)
        next_due_date = start_date
        
        file = request.files['document']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            file_path =""
          
        insert_db('INSERT INTO recurring_expenses (user_id, description, amount, start_date, period, next_due_date, end_date, category_id,document) VALUES (?, ?, ?, ?, ?, ?, ?, ?,?)',
                  (current_user.id, description, amount, start_date, period, next_due_date, end_date, category_id,file_path))

        flash('Recurring expense added successfully!', 'success')
        return redirect(url_for('view_recurring_expenses'))
   
    categories = query_db('SELECT * FROM category')
    choices = query_db('SELECT * FROM choices')
    return render_template('add_recurring_expense.html', form=form, categories=categories, choices=choices)

@app.route('/view_recurring_expenses', methods=['GET', 'POST'])
@login_required
def view_recurring_expenses():
    # Get query parameters for filtering
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    amount_comparison = request.args.get('amount_comparison', '')
    amount_value = request.args.get('amount_value', '')
    period = request.args.get('period', '')
    sort_by = request.args.get('sort_by', '')

    # Base query
    query = '''
        SELECT r.*, c.name AS category_name 
        FROM recurring_expenses r 
        JOIN category c ON r.category_id = c.id 
        WHERE r.user_id = ?
    '''
    params = [current_user.id]

    # Apply filters
    if search:
        query += " AND r.description LIKE ?"
        params.append(f'%{search}%')

    if category:
        category=int(category)
        
        query += " AND c.id = ?"
        params.append(category)

    if start_date:
        query += " AND r.start_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND r.start_date <= ?"
        params.append(end_date)

    if amount_comparison and amount_value:
        if amount_comparison == "equal":
            query += " AND r.amount = ?"
        elif amount_comparison == "greater":
            query += " AND r.amount > ?"
        elif amount_comparison == "less":
            query += " AND r.amount < ?"
        params.append(amount_value)

    if period:
        print("Period:")
        print(period)
        query += " AND r.period = ?"
        params.append(period)

    # Apply sorting
    if sort_by:
        if sort_by == "start_date_asc":
            query += " ORDER BY r.start_date ASC"
        elif sort_by == "start_date_desc":
            query += " ORDER BY r.start_date DESC"
        elif sort_by == "end_date_asc":
            query += " ORDER BY r.end_date ASC"
        elif sort_by == "end_date_desc":
            query += " ORDER BY r.end_date DESC"
        elif sort_by == "amount_asc":
            query += " ORDER BY r.amount ASC"
        elif sort_by == "amount_desc":
            query += " ORDER BY r.amount DESC"

    # Fetch existing recurring expenses for the user
    expenses = query_db(query, params)
    categories = query_db('SELECT id, name, is_income FROM category')
    print(period)
    return render_template('view_recurring_expenses.html', 
                           expenses=expenses,
                           search=search,
                           category_v=category,
                           start_date=start_date,
                           end_date=end_date,
                           amount_comparison=amount_comparison,
                           amount_value=amount_value,
                           period=period,
                           sort_by=sort_by
                           ,
                           categories=categories)

@app.route('/delete_recurring_expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_recurring_expense(expense_id):
    # Delete the expense from the database
    delete_db('DELETE FROM recurring_expenses WHERE id = ? AND user_id = ?', [expense_id, current_user.id])
    
    flash( 'Expense deleted successfully!' , 'success')
    return redirect(url_for('view_recurring_expenses'))

@app.route('/edit_recurring_expense/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_recurring_expense(expense_id):
    # Fetch the expense from the database
    expense = query_db('SELECT * FROM recurring_expenses WHERE id = ? AND user_id = ?', [expense_id, current_user.id], one=True)
    
    if not expense:
        flash('Expense not found or unauthorized access.', 'danger')
        return redirect(url_for('view_recurring_expenses'))
    
    if request.method == 'POST':
        description = request.form['description']
        amount = request.form['amount']
        Startdate = request.form['Startdate']
        Enddate =request.form['Enddate']
        category_id = request.form['category']
        period=request.form['period']

        # Handle file upload if a new document is provided
        file = request.files['document']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            file_path = expense[9]  # Keep the old document if no new one is uploaded

        # Update the database with the new values
        insert_db(
            'UPDATE recurring_expenses SET description = ?, amount = ?, start_date=?,end_date = ?, period=?,category_id = ?, document = ? WHERE id = ? AND user_id = ?',
            (description, amount, Startdate, Enddate, period,category_id, file_path, expense_id, current_user.id)
        )

        flash('Expense updated successfully!', 'success')
        return redirect(url_for('view_recurring_expenses'))

    # Fetch categories for the form
    categories = query_db('SELECT * FROM category')
    period = query_db('SELECT * FROM choices')
    
    return render_template('edit_recurring_expenses.html', expense=expense, categories=categories,period=period)


@app.route('/admin_profile', methods=['GET', 'POST'])
@login_required
def admin_profile():
    # Fetch current user's profile
    user = query_db('SELECT * FROM users WHERE id=?', [current_user.id], one=True)
    if request.method == 'POST':
        # Get form data
        full_name = request.form['full_name']
        email = request.form['email']
        phone_number = request.form['phone_number']
        address = request.form['address']
        file = request.files['profile']
        
        # Handle file upload
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            file_path = user[7]  # No file uploaded

        # Update the user's profile in the database (assuming you have a current_user object)
        insert_db('UPDATE users SET Fullname=?, email=?, Phonenumber=?, address=?, document=? WHERE id=?',
         (full_name, email, phone_number, address, file_path, current_user.id))

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('admin_profile'))
    return render_template('admin_profile.html', user=user)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    # Fetch current user's profile
    user = query_db('SELECT * FROM users WHERE id=?', [current_user.id], one=True)
    if request.method == 'POST':
        # Get form data
        full_name = request.form['full_name']
        email = request.form['email']
        phone_number = request.form['phone_number']
        address = request.form['address']
        file = request.files['profile']
        
        # Handle file upload
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            file_path = user[7]  # No file uploaded

        # Update the user's profile in the database (assuming you have a current_user object)
        insert_db('UPDATE users SET Fullname=?, email=?, Phonenumber=?, address=?, document=? WHERE id=?',
         (full_name, email, phone_number, address, file_path, current_user.id))

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    

    return render_template('profile.html', user=user)


@app.route('/admin/category_manage', methods=['GET','POST'])
def admin_category_manage():

    if request.method=='POST':
        action_type = request.form.get('action_type')
        
        if action_type == 'add_category':
            category_name = request.form.get('category_name')
            if category_name:
                insert_db("INSERT INTO category (name) VALUES (?)", [category_name])
                flash('Category added!', 'success')
            return redirect(url_for('admin_category_manage'))
        elif action_type =="edit_category":
             category_id = request.form.get('category_id')
             category_name= request.form.get('category_name')
             insert_db("UPDATE category SET name=? WHERE id =?", [category_name, category_id])
        elif action_type == 'delete_category':
            category_id = request.form.get('category_id')
            in_expense=query_db("SELECT category_id FROM expenses WHERE category_id=?",[category_id])
            in_budget=query_db("SELECT category_id FROM budgets WHERE category_id=?",[category_id])
            in_recurrin= query_db("SELECT category_id FROM recurring_expenses WHERE category_id=?",[category_id])
            

            if in_expense or in_budget or in_recurrin:
                    
                flash('Cannot delete category, it is in use!', 'danger')
                    
            else:
                insert_db('DELETE FROM category WHERE id = ?',[category_id])
                flash('Category deleted!', 'success')
                    
            return redirect(url_for('admin_category_manage'))

    # Fetching categories for the category management section
    categories = query_db("SELECT * FROM category ")
    return render_template ('admin_category_manage.html', categories=categories)

 
@app.route('/admin/actions', methods=['GET', 'POST'])
def admin_actions():
    if request.method == 'POST':
        # Handling various form submissions here
        action_type = request.form.get('action_type')

        if action_type == 'reset_password':
            email = request.form.get('email')
            if email:
                user = query_db("SELECT id FROM USERS where email=?",[email])
                print(user)
                if user:
                    print("yes")
                    url= url_for('forgot_password')
                    msg= f" Please use the below url to reset the password:  http://127.0.0.1:5000/{url_for('forgot_password')}"
                    send_msg(email,msg)
                    flash('Password reset email sent!', 'success')
                else:
                    print("no")
                    flash('User not found!', 'danger')
            return redirect(url_for('admin_actions'))


       
        elif action_type == 'delete_user':
            email = request.form.get('email')
            if email:
                user = query_db("SELECT id FROM USERS where email=?",[email])
                if user:
                    #Anand do the dlete user query here
                    flash('User deleted!', 'success')
                else:
                    flash('Error deleting user!', 'danger')
            return redirect(url_for('admin_actions'))

        elif action_type == 'send_custom_email':
            email = request.form.get('email')
            message = request.form.get('message')
            if email and message:
                send_msg(email, message)
                flash('Email sent!', 'success')
            else:
                flash('Error sending email!', 'danger')
            return redirect(url_for('admin_actions'))

        
            


    return render_template('admin_actions.html')



def generate_otp():
    """Generate a 6-digit OTP"""
    return random.randint(100000, 999999)



def send_otp(email, otp):
    """Send the OTP to the user's email"""
    # Configure your email server (e.g., Gmail)
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "finanaceadse@gmail.com"
    sender_password = "yofzsxztafrgiqtd"
    
    subject = "Your OTP for Password Reset"
    body = f"Your OTP is {otp}. Please enter this to reset your password."

    message = f"Subject: {subject}\n\n{body}"

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, message)
        server.quit()
        print("OTP sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")

@app.route('/forgot_password', methods=['GET','POST'])
def forgot_password():
   if request.method=='POST': 
    email = request.form['email']
    
    # Check if email exists in the database
    user = query_db('SELECT * FROM users WHERE email = ?', (email,),one=True)
    
    if user:
        otp = generate_otp()
        session['otp'] = otp
        session['email'] = email
        send_otp(email, otp)
        
        flash('OTP has been sent to your email.', 'success')
        return redirect(url_for('verify_otp'))
    else:
        flash('Email does not exist in our records.', 'danger')
        print('error')
        
   
   return render_template('forgot_password.html')

@app.context_processor
def inject_unread_notifications():
    if current_user.is_authenticated:
        # Count unread notifications for the logged-in user
        unread_count = query_db('''
            SELECT COUNT(*)
            FROM notifications
            WHERE user_id = ? AND is_read = 0
        ''', [current_user.id], one=True)

        return dict(unread_count=unread_count[0] if unread_count else 0)
    return dict(unread_count=0)



def send_msg(email, msg):
    """Send the OTP to the user's email"""
    # Configure your email server (e.g., Gmail)
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "finanaceadse@gmail.com"
    sender_password = "yofzsxztafrgiqtd"
    
    subject = "Track It Hack It"
    body = msg

    message = f"Subject: {subject}\n\n{body}"

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, message)
        server.quit()
        print("OTP sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")


@app.route('/notifications')
@login_required
def notifications():
    # Fetch all notifications for the user
    notifications = query_db('''
        SELECT id, message, is_read, created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY is_read asc, created_at DESC 
    ''', [current_user.id])
  
    return render_template('notifications.html', notifications=notifications)

@app.route('/mark_notification_as_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_as_read(notification_id):
    insert_db('UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?', [notification_id, current_user.id])
    return jsonify({'status': 'success'})

@app.route('/delete_notification/<int:notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    insert_db('DELETE FROM notifications WHERE id = ? AND user_id = ?', [notification_id, current_user.id])
    return jsonify({'status': 'success'})

@app.route('/clear_all_notifications', methods=['POST'])
@login_required
def clear_all_notifications():
    insert_db('DELETE FROM notifications WHERE user_id = ?', [current_user.id])
    return jsonify({'status': 'success'})


@app.route('/change_password', methods=['GET','POST'])
def change_password():
    email = query_db('SELECT email FROM users WHERE id=?', [current_user.id], one=True)
    email=email[0]
    otp = generate_otp()
    session['otp'] = otp
    session['email'] = email
    print(email)
    send_otp(email, otp)

    flash('OTP has been sent to your email.', 'success')
    return redirect(url_for('verify_otp'))

@app.route('/verify_otp', methods=['GET','POST'])
def verify_otp():
   if request.method == 'POST':
    otp = request.form['otp']
    
    if 'otp' in session and session['otp'] == int(otp):
        flash('OTP verified. You can now reset your password.', 'success')
        return redirect(url_for('reset_password'))
    else:
        flash('Invalid OTP. Please try again.', 'danger')
        return redirect(url_for('verify_otp'))
   return render_template('verify_otp.html')


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password == confirm_password:
            # Update the password in the database
            email = session.get('email')
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            insert_db('UPDATE users SET password = ? WHERE email = ?', (hashed_password, email))
            
            flash('Password reset successfully!', 'success')
            logout_user()
            return redirect(url_for('login'))
        else:
            flash('Passwords do not match. Please try again.', 'danger')
           
    return render_template('reset_password.html')

@app.route('/budget', methods=['GET','POST'])
@login_required
def budget():
    categories = query_db('SELECT * FROM category WHERE is_income = 0')  # Fetch all categories
    budgets = query_db('SELECT * FROM budgets WHERE user_id = ?', (current_user.id,))
    budget_dict= dict()
    for budget in budgets:
        budget_dict[budget[2]]= budget[3]
    return render_template('budget.html', categories=categories, budgets=budgets,budget_dict=budget_dict)


@app.route('/add_edit_budget', methods=['POST','GET'])
@login_required
def add_edit_budget():
  if request.method =='POST':  
    category_id = request.form['category_id']
    monthly_budget = request.form['monthly_budget']

    # Check if budget already exists for this category
    existing_budget = query_db('SELECT * FROM budgets WHERE user_id = ? AND category_id = ?', 
                               (current_user.id, category_id))
    
    if existing_budget:
        # Update existing budget
        insert_db('UPDATE budgets SET monthly_budget = ? WHERE user_id = ? AND category_id = ?', 
                 (monthly_budget, current_user.id, category_id))
        flash('Budget updated successfully!', 'success')
    else:
        # Insert new budget
        insert_db('INSERT INTO budgets (user_id, category_id, monthly_budget) VALUES (?, ?, ?)', 
                 (current_user.id, category_id, monthly_budget))
        flash('Budget added successfully!', 'success')
        print(monthly_budget)
    
    return redirect(url_for('budget'))
  else:
      return render_template('add_edit_budget.html')

@app.route('/view_report_income', methods=['GET', 'POST'])
@login_required
def view_report_income():
    
        # Get the report type and filter type from the form
         # Set to either 'income' or 'expense'
        filter_type = request.form.get('income-date-filter')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date') 
        
        # Default to 'income' if report_type is not provided
    
        report_type = 'income'

        # Validate filter type and set default
        if not filter_type:
            filter_type = 'this_month'

        user_id = current_user.id  # Get the user ID from the logged-in user

        # Initialize the base query based on the report_type
        if report_type == 'income':
            base_query = '''
                SELECT c.name, SUM(e.amount) 
                FROM category c 
                LEFT JOIN expenses e ON c.id = e.category_id 
                WHERE c.is_income = 1 AND e.user_id = ? '''
        

        # Modify query based on the filter type
        if filter_type == 'this_month':
            query = base_query + ''' AND strftime('%Y-%m', e.date) = strftime('%Y-%m', 'now') GROUP BY c.id, c.name '''
            result = query_db(query, [user_id])

        elif filter_type == 'this_year':
            query = base_query + ''' AND strftime('%Y', e.date) = strftime('%Y', 'now') GROUP BY c.id, c.name '''
            result = query_db(query, [user_id])

        elif filter_type == 'date_range' and start_date and end_date:
            query = base_query + ''' AND e.date BETWEEN ? AND ? GROUP BY c.id, c.name '''
            result = query_db(query, [user_id, start_date, end_date])

        else:
            result = []

        # Format the result into categories and values
        categories = [row[0] for row in result]  # Category names
        values = [row[1] for row in result]  # Summed amounts for each category
        backgroundColors = [
            'rgba(255, 99, 132, 0.2)',  # Color for category 1
            'rgba(54, 162, 235, 0.2)',   # Color for category 2
            'rgba(255, 206, 86, 0.2)',    # Color for category 3
            'rgba(75, 192, 192, 0.2)',   # Color for category 4
            'rgba(153, 102, 255, 0.2)',  # Color for category 5
            'rgba(255, 159, 64, 0.2)',   # Color for category 6
            'rgba(199, 199, 199, 0.2)',   # Color for category 7
            'rgba(83, 102, 255, 0.2)'     # Color for category 8
        ];

        borderColors = [
            'rgba(255, 99, 132, 1)',      # Border color for category 1
            'rgba(54, 162, 235, 1)',       # Border color for category 2
            'rgba(255, 206, 86, 1)',       # Border color for category 3
            'rgba(75, 192, 192, 1)',       # Border color for category 4
            'rgba(153, 102, 255, 1)',      # Border color for category 5
            'rgba(255, 159, 64, 1)',       # Border color for category 6
            'rgba(199, 199, 199, 1)',       # Border color for category 7
            'rgba(83, 102, 255, 1)'         # Border color for category 8
        ];
        return render_template("view_report_income.html",backgroundColors=backgroundColors, categories=categories, values=values,report_type=report_type, filter_type=filter_type,start_date=start_date,end_date=end_date)
   
@app.route('/view_report_expense', methods=['GET', 'POST'])
@login_required
def view_report_expense():
    
        # Get the report type and filter type from the form
         # Set to either 'income' or 'expense'
        filter_type = request.form.get('expense-date-filter')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date') 
        
        # Default to 'income' if report_type is not provided
        
        report_type = 'expense'

        # Validate filter type and set default
        if not filter_type:
            filter_type = 'this_month'

        user_id = current_user.id  # Get the user ID from the logged-in user

        # Initialize the base query based on the report_type
        
        if report_type == 'expense':
            base_query = '''
                SELECT c.name, SUM(e.amount) 
                FROM category c 
                LEFT JOIN expenses e ON c.id = e.category_id 
                WHERE c.is_income = 0 AND e.user_id = ? '''
        else:
            # Handle cases where report_type is invalid
            return "Invalid report type", 400

        # Modify query based on the filter type
        if filter_type == 'this_month':
            query = base_query + ''' AND strftime('%Y-%m', e.date) = strftime('%Y-%m', 'now') GROUP BY c.id, c.name '''
            result = query_db(query, [user_id])

        elif filter_type == 'this_year':
            query = base_query + ''' AND strftime('%Y', e.date) = strftime('%Y', 'now') GROUP BY c.id, c.name '''
            result = query_db(query, [user_id])

        elif filter_type == 'date_range' and start_date and end_date:
            query = base_query + ''' AND e.date BETWEEN ? AND ? GROUP BY c.id, c.name '''
            result = query_db(query, [user_id, start_date, end_date])

        else:
            result = []

        # Format the result into categories and values
        categories = [row[0] for row in result]  # Category names
        values = [row[1] for row in result]  # Summed amounts for each category
        print(report_type)
        print(filter_type)
        backgroundColors = [
            'rgba(255, 99, 132, 0.2)',  
            'rgba(54, 162, 235, 0.2)',   #Color for category 2
            'rgba(255, 206, 86, 0.2)',    # Color for category 3
            'rgba(75, 192, 192, 0.2)',  # Color for category 4
            'rgba(153, 102, 255, 0.2)', # Color for category 5
            'rgba(255, 159, 64, 0.2)',   # Color for category 6
            'rgba(199, 199, 199, 0.2)',   # Color for category 7
            'rgba(83, 102, 255, 0.2)'     # Color for category 8
        ];

        borderColors = [
            'rgba(255, 99, 132, 1)',      # Border color for category 1
            'rgba(54, 162, 235, 1)',       # Border color for category 2
            'rgba(255, 206, 86, 1)',       # Border color for category 3
            'rgba(75, 192, 192, 1)',       # Border color for category 4
            'rgba(153, 102, 255, 1)',      # Border color for category 5
            'rgba(255, 159, 64, 1)',       # Border color for category 6
            'rgba(199, 199, 199, 1)',       # Border color for category 7
            'rgba(83, 102, 255, 1)'         # Border color for category 8
        ];
        return render_template("view_report_expense.html",backgroundColors=backgroundColors, categories=categories, values=values,report_type=report_type, filter_type=filter_type,start_date=start_date,end_date=end_date)
    



@app.route('/admin_view_report_income', methods=['GET', 'POST'])
@login_required
def admin_view_report_income():
    
        # Get the report type and filter type from the form
         # Set to either 'income' or 'expense'
        filter_type = request.form.get('income-date-filter')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date') 
        
        # Default to 'income' if report_type is not provided
    
        report_type = 'income'

        # Validate filter type and set default
        if not filter_type:
            filter_type = 'this_month'

        user_id = current_user.id  # Get the user ID from the logged-in user

        # Initialize the base query based on the report_type
        if report_type == 'income':
            base_query = '''
                SELECT c.name, SUM(e.amount) 
                FROM category c 
                LEFT JOIN expenses e ON c.id = e.category_id 
                WHERE c.is_income = 1  '''
        

        # Modify query based on the filter type
        if filter_type == 'this_month':
            query = base_query + ''' AND strftime('%Y-%m', e.date) = strftime('%Y-%m', 'now') GROUP BY c.id, c.name '''
            result = query_db(query, [])

        elif filter_type == 'this_year':
            query = base_query + ''' AND strftime('%Y', e.date) = strftime('%Y', 'now') GROUP BY c.id, c.name '''
            result = query_db(query, [])

        elif filter_type == 'date_range' and start_date and end_date:
            query = base_query + ''' AND e.date BETWEEN ? AND ? GROUP BY c.id, c.name '''
            result = query_db(query, [ start_date, end_date])

        else:
            result = []

        # Format the result into categories and values
        categories = [row[0] for row in result]  # Category names
        values = [row[1] for row in result]  # Summed amounts for each category
        backgroundColors = [
            'rgba(255, 99, 132, 0.2)',  # Color for category 1
            'rgba(54, 162, 235, 0.2)',   # Color for category 2
            'rgba(255, 206, 86, 0.2)',    # Color for category 3
            'rgba(75, 192, 192, 0.2)',   # Color for category 4
            'rgba(153, 102, 255, 0.2)',  # Color for category 5
            'rgba(255, 159, 64, 0.2)',   # Color for category 6
            'rgba(199, 199, 199, 0.2)',   # Color for category 7
            'rgba(83, 102, 255, 0.2)'     # Color for category 8
        ];

        borderColors = [
            'rgba(255, 99, 132, 1)',      # Border color for category 1
            'rgba(54, 162, 235, 1)',       # Border color for category 2
            'rgba(255, 206, 86, 1)',       # Border color for category 3
            'rgba(75, 192, 192, 1)',       # Border color for category 4
            'rgba(153, 102, 255, 1)',      # Border color for category 5
            'rgba(255, 159, 64, 1)',       # Border color for category 6
            'rgba(199, 199, 199, 1)',       # Border color for category 7
            'rgba(83, 102, 255, 1)'         # Border color for category 8
        ];
        return render_template("admin_view_report_income.html",backgroundColors=backgroundColors, categories=categories, values=values,report_type=report_type, filter_type=filter_type,start_date=start_date,end_date=end_date)
   
@app.route('/admin_view_report_expense', methods=['GET', 'POST'])
@login_required
def admin_view_report_expense():
    
        # Get the report type and filter type from the form
         # Set to either 'income' or 'expense'
        filter_type = request.form.get('expense-date-filter')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date') 
        
        # Default to 'income' if report_type is not provided
        
        report_type = 'expense'

        # Validate filter type and set default
        if not filter_type:
            filter_type = 'this_month'

        user_id = current_user.id  # Get the user ID from the logged-in user

        # Initialize the base query based on the report_type
        
        if report_type == 'expense':
            base_query = '''
                SELECT c.name, SUM(e.amount) 
                FROM category c 
                LEFT JOIN expenses e ON c.id = e.category_id 
                WHERE c.is_income = 0  '''
        else:
            # Handle cases where report_type is invalid
            return "Invalid report type", 400

        # Modify query based on the filter type
        if filter_type == 'this_month':
            query = base_query + ''' AND strftime('%Y-%m', e.date) = strftime('%Y-%m', 'now') GROUP BY c.id, c.name '''
            result = query_db(query, [])

        elif filter_type == 'this_year':
            query = base_query + ''' AND strftime('%Y', e.date) = strftime('%Y', 'now') GROUP BY c.id, c.name '''
            result = query_db(query, [])

        elif filter_type == 'date_range' and start_date and end_date:
            query = base_query + ''' AND e.date BETWEEN ? AND ? GROUP BY c.id, c.name '''
            result = query_db(query, [ start_date, end_date])

        else:
            result = []

        # Format the result into categories and values
        categories = [row[0] for row in result]  # Category names
        values = [row[1] for row in result]  # Summed amounts for each category
        print(report_type)
        print(filter_type)
        backgroundColors = [
            'rgba(255, 99, 132, 0.2)',  
            'rgba(54, 162, 235, 0.2)',   #Color for category 2
            'rgba(255, 206, 86, 0.2)',    # Color for category 3
            'rgba(75, 192, 192, 0.2)',  # Color for category 4
            'rgba(153, 102, 255, 0.2)', # Color for category 5
            'rgba(255, 159, 64, 0.2)',   # Color for category 6
            'rgba(199, 199, 199, 0.2)',   # Color for category 7
            'rgba(83, 102, 255, 0.2)'     # Color for category 8
        ];

        borderColors = [
            'rgba(255, 99, 132, 1)',      # Border color for category 1
            'rgba(54, 162, 235, 1)',       # Border color for category 2
            'rgba(255, 206, 86, 1)',       # Border color for category 3
            'rgba(75, 192, 192, 1)',       # Border color for category 4
            'rgba(153, 102, 255, 1)',      # Border color for category 5
            'rgba(255, 159, 64, 1)',       # Border color for category 6
            'rgba(199, 199, 199, 1)',       # Border color for category 7
            'rgba(83, 102, 255, 1)'         # Border color for category 8
        ];
        return render_template("admin_view_report_expense.html",backgroundColors=backgroundColors, categories=categories, values=values,report_type=report_type, filter_type=filter_type,start_date=start_date,end_date=end_date)
    
@app.route('/tax_calculator', methods=['GET', 'POST'])
def tax_calculator():
    tax_result = None
    federal_tax = None
    state_tax = None
    if request.method == 'POST':
        try:
            income = float(request.form['income'])
            tax_deductions = float(request.form.get('deductions', 0))
            taxable_income = max(0, income - tax_deductions)  # Ensure taxable income is not negative
            federal_rate = float(request.form['federal_tax_rate'])
            state_rate = float(request.form['state_tax_rate'])

            # Basic progressive tax rates for federal (example)
            federal_tax = calculate_progressive_tax(taxable_income, federal_rate)

            # State tax (flat percentage)
            state_tax = taxable_income * (state_rate / 100)

            # Total tax calculation
            tax_result = federal_tax + state_tax
        except ValueError:
            tax_result = "Invalid input. Please enter numeric values."

    return render_template('tax_calculator.html', tax_result=tax_result, federal_tax=federal_tax, state_tax=state_tax)

def calculate_progressive_tax(income, base_rate):
    # Example of a simple progressive tax calculation
    tax = 0
    brackets = [
        (10000, 0.1),  # 10% for income up to 10,000
        (30000, 0.2),  # 20% for the next 30,000
        (float('inf'), 0.3)  # 30% for the remaining income
    ]

    for limit, rate in brackets:
        if income > limit:
            tax += limit * rate
            income -= limit
        else:
            tax += income * rate
            break

    return tax



if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'init_db':
        init_db(app)  # Pass the `app` object here
        print("Database initialized successfully.")
    else:
        app.run(debug=True)
