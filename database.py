from datetime import datetime
import datetime
import sqlite3
from flask import g
from flask_login import UserMixin
DATABASE = 'finance_tracker.db'

class User(UserMixin):
    def __init__(self, id, username, email, password):
        self.id = id
        self.username = username
        self.email = email
        self.password = password

    def __repr__(self):
        return f'<User {self.username}>'

  
def get_db():
    #if '_database' not in g:
     #   g._database = sqlite3.connect(DATABASE)
    return sqlite3.connect(DATABASE)

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def delete_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    cur.close()
    
def insert_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    cur.close()

def get_user_by_id(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return User(id=user[0], username=user[1], email=user[2], password=user[3])
    return None

def init_db(app):
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
# Assuming you are using SQLAlchemy or some other ORM

def get_total_income(user_id):
    # Query to calculate total income for the user
    query = 'SELECT SUM(amount) FROM expenses WHERE user_id = ? AND is_income = 1'
    db=get_db()
    result = db.execute(query, (user_id,)).fetchone()
    return result[0] if result[0] is not None else 0


def get_total_expenses(user_id):
    # Query to calculate total expenses for the user
    query = 'SELECT SUM(amount) FROM expenses WHERE user_id = ? AND is_income = 0'
    db=get_db()
    result = db.execute(query, (user_id,)).fetchone()
    return result[0] if result[0] is not None else 0


def get_budget(user_id):
    # Query to fetch user's current budget
    query = 'SELECT monthly_budget FROM  budgets WHERE id = ?'
    db=get_db()
    result = db.execute(query, (user_id,)).fetchone()
    return result[0] if result[0] is not None else 0

def get_budgets_and_expenses(user_id):
    query = '''
        SELECT 
            c.name, 
            IFNULL(b.monthly_budget, 0) AS monthly_budget, 
            IFNULL(SUM(e.amount), 0) AS total_expense
        FROM 
            category c 
        LEFT JOIN 
            budgets b ON c.id = b.category_id AND b.user_id = ?
        LEFT JOIN 
            expenses e ON c.id = e.category_id AND e.user_id = ? AND strftime('%Y-%m', e.date) = strftime('%Y-%m', 'now')
        WHERE c.is_income=0
         GROUP BY 
            c.id, c.name, b.monthly_budget
    '''
    return query_db(query, [user_id, user_id])

def get_expenses_by_category(user_id):
    db = get_db()
     
    current_date = datetime.date.today()
    first_day_of_month = current_date.replace(day=1)
    query = '''
        SELECT e.category_id, SUM(e.amount) as total_expense, c.name AS category_name 
        FROM expenses e 
        JOIN category c ON e.category_id = c.id 
        WHERE user_id = ?  AND date >= ? AND date < ?
        GROUP BY c.name
    '''
    result = db.execute(query,(user_id, first_day_of_month, first_day_of_month.replace(month=current_date.month % 12 + 1))).fetchall()
    return result


def get_recent_transactions(user_id):
    # Query to fetch the most recent transactions
    query = '''
        SELECT description, category_id, amount, date
        FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC
        LIMIT 7
    '''
    db=get_db()
    result = db.execute(query, (user_id,)).fetchall()
    return result
