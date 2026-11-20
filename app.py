import os, sqlite3, secrets
from datetime import date
from functools import wraps
from decimal import Decimal, InvalidOperation
from flask import Flask, request, redirect, session, render_template, abort, flash
from werkzeug.security import generate_password_hash, check_password_hash
app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('HTTPS_ONLY')=='1', MAX_CONTENT_LENGTH=1024*1024)
DB=os.environ.get('DATABASE_PATH','garage.sqlite3')
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
with db() as c:
 c.executescript('''
 CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('owner','staff')),active INTEGER DEFAULT 1);
 CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,address TEXT DEFAULT '');
 CREATE TABLE IF NOT EXISTS vehicles(id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES customers(id),registration TEXT UNIQUE NOT NULL,model TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),mechanic_id INTEGER REFERENCES users(id),problem TEXT NOT NULL,status TEXT DEFAULT 'Naya',created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS stock(id INTEGER PRIMARY KEY,name TEXT NOT NULL,code TEXT UNIQUE NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>=0),price INTEGER NOT NULL CHECK(price>=0));
 CREATE TABLE IF NOT EXISTS bills(id INTEGER PRIMARY KEY,job_id INTEGER UNIQUE REFERENCES jobs(id),customer_id INTEGER NOT NULL REFERENCES customers(id),description TEXT NOT NULL,total INTEGER NOT NULL CHECK(total>0),created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY,bill_id INTEGER NOT NULL REFERENCES bills(id),amount INTEGER NOT NULL CHECK(amount>0),method TEXT NOT NULL,reference TEXT,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY,description TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),day TEXT NOT NULL,status TEXT NOT NULL,UNIQUE(user_id,day));
 CREATE TABLE IF NOT EXISTS salary_entries(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),kind TEXT NOT NULL CHECK(kind IN ('Earned','Payment','Advance')),amount INTEGER NOT NULL CHECK(amount>0),note TEXT NOT NULL,created TEXT NOT NULL);
 ''')
 if not c.execute('SELECT 1 FROM users').fetchone():
  password=os.environ.get('OWNER_PASSWORD','')
  if len(password)<12: raise RuntimeError('Set OWNER_PASSWORD to at least 12 characters for first startup.')
  c.execute('INSERT INTO users(name,username,password,role) VALUES(?,?,?,?)',('Owner','owner',generate_password_hash(password),'owner'))
def money(v):
 try:
  x=Decimal(v)
  if not x.is_finite() or x<=0 or x>Decimal('100000000'): raise ValueError('Invalid amount')
  if x != x.quantize(Decimal('.01')): raise ValueError('Use maximum two decimal places')
  return int(x*100)
 except (InvalidOperation,TypeError): raise ValueError('Invalid amount')
def auth(owner=False):
 def deco(f):
  @wraps(f)
  def run(*a,**kw):
   with db() as c: u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(session.get('uid'),)).fetchone()
   if not u:return redirect('/login')
   if owner and u['role']!='owner':abort(403)
   return f(*a,**kw)
  return run
 return deco
@app.before_request
def csrf():
 session.setdefault('csrf',secrets.token_hex(32))
 if request.method=='POST' and not secrets.compare_digest(session['csrf'],request.form.get('csrf','')):abort(403)
@app.template_filter('inr')
def inr(v):return f'{(v or 0)/100:,.2f}'
@app.template_filter('day')
def day(v):return date.fromisoformat(v).strftime('%d/%m/%Y')
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  with db() as c:u=c.execute('SELECT * FROM users WHERE username=? AND active=1',(request.form.get('username'),)).fetchone()
  if u and check_password_hash(u['password'],request.form.get('password','')):
   session.clear();session['uid']=u['id'];return redirect('/')
  flash('Login galat hai')
 return render_template('login.html')
@app.post('/logout')
def logout():session.clear();return redirect('/login')
@app.get('/')
@auth()
def home():
 with db() as c:
  u=c.execute('SELECT * FROM users WHERE id=?',(session['uid'],)).fetchone();owner=u['role']=='owner'
  jobs=c.execute('SELECT j.*,v.registration,u.name mechanic FROM jobs j JOIN vehicles v ON v.id=j.vehicle_id LEFT JOIN users u ON u.id=j.mechanic_id '+('' if owner else 'WHERE j.mechanic_id=? ')+'ORDER BY j.id DESC',() if owner else (u['id'],)).fetchall()
  data={}
  if owner:
   for table in ['customers','vehicles','stock','users','expenses','attendance','salary_entries']:data[table]=c.execute('SELECT * FROM '+table+' ORDER BY id DESC').fetchall()
   data['bills']=c.execute('SELECT b.*,c.name,COALESCE((SELECT SUM(amount) FROM payments p WHERE p.bill_id=b.id),0) paid FROM bills b JOIN customers c ON c.id=b.customer_id ORDER BY b.id DESC').fetchall()
   today=date.today().isoformat()
   data['billing']=c.execute('SELECT COALESCE(SUM(total),0) FROM bills WHERE created=?',(today,)).fetchone()[0]
   data['collected']=c.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE created=?',(today,)).fetchone()[0]
   data['spent']=c.execute('SELECT COALESCE(SUM(amount),0) FROM expenses WHERE created=?',(today,)).fetchone()[0]
   data['due']=sum(b['total']-b['paid'] for b in data['bills'])
  else:
   data['attendance']=c.execute('SELECT * FROM attendance WHERE user_id=? ORDER BY day DESC',(u['id'],)).fetchall()
   data['salary_entries']=c.execute('SELECT * FROM salary_entries WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()
  data['salary_balance']=sum(r['amount'] if r['kind']=='Earned' else -r['amount'] for r in data['salary_entries']) if not owner else None
 return render_template('home.html',u=u,owner=owner,jobs=jobs,d=data)
@app.post('/add/<kind>')
@auth(owner=True)
def add(kind):
 f=request.form;today=date.today().isoformat()
 try:
  with db() as c:
   if kind=='customer': c.execute('INSERT INTO customers(name,phone,address) VALUES(?,?,?)',(f['name'].strip(),f['phone'].strip(),f.get('address','')))
   elif kind=='vehicle': c.execute('INSERT INTO vehicles(customer_id,registration,model) VALUES(?,?,?)',(int(f['customer_id']),f['registration'].upper().replace(' ',''),f['model']))
   elif kind=='job':
    mid=int(f['mechanic_id']) if f.get('mechanic_id') else None
    if mid and not c.execute("SELECT 1 FROM users WHERE id=? AND role='staff' AND active=1",(mid,)).fetchone():raise ValueError('Active mechanic chuno')
    c.execute('INSERT INTO jobs(vehicle_id,mechanic_id,problem,created) VALUES(?,?,?,?)',(int(f['vehicle_id']),mid,f['problem'],today))
   elif kind=='stock': c.execute('INSERT INTO stock(name,code,quantity,price) VALUES(?,?,?,?)',(f['name'],f['code'],int(f['quantity']),money(f['price'])))
   elif kind=='bill':
    jid=int(f['job_id']) if f.get('job_id') else None;cid=int(f['customer_id'])
    if jid:
     row=c.execute('SELECT v.customer_id FROM jobs j JOIN vehicles v ON v.id=j.vehicle_id WHERE j.id=?',(jid,)).fetchone()
     if not row or row[0]!=cid:raise ValueError('Job aur customer match nahi karte')
    c.execute('INSERT INTO bills(job_id,customer_id,description,total,created) VALUES(?,?,?,?,?)',(jid,cid,f['description'],money(f['total']),today))
   elif kind=='payment':
    c.execute('BEGIN IMMEDIATE');bid=int(f['bill_id']);amount=money(f['amount'])
    row=c.execute('SELECT total-COALESCE((SELECT SUM(amount) FROM payments WHERE bill_id=b.id),0) due FROM bills b WHERE id=?',(bid,)).fetchone()
    if not row or amount>row['due']:raise ValueError('Payment baaki amount se zyada hai')
    if f['method'] not in ['Cash','UPI','Bank transfer']:raise ValueError('Invalid payment method')
    c.execute('INSERT INTO payments(bill_id,amount,method,reference,created) VALUES(?,?,?,?,?)',(bid,amount,f['method'],f.get('reference',''),today))
   elif kind=='expense':c.execute('INSERT INTO expenses(description,amount,created) VALUES(?,?,?)',(f['description'],money(f['amount']),today))
   elif kind=='staff':
    if len(f['password'])<12:raise ValueError('Password minimum 12 characters')
    c.execute("INSERT INTO users(name,username,password,role) VALUES(?,?,?,'staff')",(f['name'],f['username'],generate_password_hash(f['password'])))
   elif kind in ['attendance','salary']:
    uid=int(f['user_id'])
    if not c.execute("SELECT 1 FROM users WHERE id=? AND role='staff'",(uid,)).fetchone():raise ValueError('Staff chuno')
    if kind=='attendance':
     date.fromisoformat(f['day'])
     if f['status'] not in ['Present','Absent','Half-day','Leave']:raise ValueError('Invalid status')
     c.execute('INSERT INTO attendance(user_id,day,status) VALUES(?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET status=excluded.status',(uid,f['day'],f['status']))
    else:c.execute('INSERT INTO salary_entries(user_id,kind,amount,note,created) VALUES(?,?,?,?,?)',(uid,f['kind'],money(f['amount']),f['note'],today))
   elif kind=='deactivate':
    c.execute("UPDATE users SET active=0 WHERE id=? AND role='staff'",(int(f['user_id']),))
   elif kind=='status':
    if f['status'] not in ['Naya','Checking','Kaam Chal Raha Hai','Parts Ka Intezaar','Ready','Delivered','Cancelled']:raise ValueError('Invalid status')
    c.execute('UPDATE jobs SET status=? WHERE id=?',(f['status'],int(f['job_id'])))
   else:abort(404)
  flash('Save ho gaya')
 except (ValueError,KeyError,sqlite3.IntegrityError):flash('Save nahi hua: fields check karo. Duplicate record, galat reference ya invalid amount ho sakta hai.')
 return redirect('/')
@app.get('/bill/<int:bid>')
@auth(owner=True)
def bill(bid):
 with db() as c:
  b=c.execute('SELECT b.*,c.name,c.phone FROM bills b JOIN customers c ON c.id=b.customer_id WHERE b.id=?',(bid,)).fetchone()
  if not b:abort(404)
  p=c.execute('SELECT * FROM payments WHERE bill_id=? ORDER BY id',(bid,)).fetchall()
 return render_template('bill.html',b=b,p=p,paid=sum(x['amount'] for x in p))
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
