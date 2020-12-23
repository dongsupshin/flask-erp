from flask import Flask, render_template, request, redirect, session, abort, url_for, send_from_directory
from flaskext.mysql import MySQL
from sqlalchemy.orm import sessionmaker
from database_setup import Base, engine, User, Profile, FacilityMaster, ProductMaster, ProductStockMaster, ItemMaster, ItemStockMaster, RecipeMaster, ProductStatusMaster
from flask_bootstrap import Bootstrap
from werkzeug import secure_filename
from lib.upload_file import uploadfile
import os
import PIL
from PIL import Image
import simplejson
import traceback

mysql = MySQL()
app = Flask('__name__')
app.config['SECRET_KEY']=os.urandom(20)
app.config['MYSQL_DATABASE_USER'] = 'dbms'
app.config['MYSQL_DATABASE_PASSWORD'] = 'justanothersecret'
app.config['MYSQL_DATABASE_DB'] = 'erp'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['UPLOAD_FOLDER'] = 'data/'
app.config['THUMBNAIL_FOLDER'] = 'data/thumbnail/'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
mysql.init_app(app)

# Connect to Database and create database session
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
alchemy_session = DBSession()

# add flask file uploader
ALLOWED_EXTENSIONS = set(['txt', 'gif', 'png', 'jpg', 'jpeg', 'bmp', 'rar', 'zip', '7zip', 'doc', 'docx', 'csv', 'xlsx'])
IGNORED_FILES = set(['.gitignore'])

bootstrap = Bootstrap(app)

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def gen_file_name(filename):
    """
    If file was exist already, rename it and return a new name
    """

    i = 1
    while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        name, extension = os.path.splitext(filename)
        filename = '%s_%s%s' % (name, str(i), extension)
        i += 1

    return filename


def create_thumbnail(image):
    try:
        base_width = 80
        img = Image.open(os.path.join(app.config['UPLOAD_FOLDER'], image))
        w_percent = (base_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        img = img.resize((base_width, h_size), PIL.Image.ANTIALIAS)
        img.save(os.path.join(app.config['THUMBNAIL_FOLDER'], image))

        return True

    except:
        print (traceback.format_exc())
        return False


@app.route("/upload", methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        files = request.files['file']

        if files:
            filename = secure_filename(files.filename)
            filename = gen_file_name(filename)
            mime_type = files.content_type

            if not allowed_file(files.filename):
                result = uploadfile(name=filename, type=mime_type, size=0, not_allowed_msg="File type not allowed")

            else:
                # save file to disk
                uploaded_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                files.save(uploaded_file_path)

                # create thumbnail after saving
                if mime_type.startswith('image'):
                    create_thumbnail(filename)
                
                # get file size after saving
                size = os.path.getsize(uploaded_file_path)

                # return json for js call back
                result = uploadfile(name=filename, type=mime_type, size=size)
            
            return simplejson.dumps({"files": [result.get_file()]})

    if request.method == 'GET':
        # get all file in ./data directory
        files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'],f)) and f not in IGNORED_FILES ]
        
        file_display = []

        for f in files:
            size = os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], f))
            file_saved = uploadfile(name=f, size=size)
            file_display.append(file_saved.get_file())

        return simplejson.dumps({"files": file_display})

    return redirect(url_for('fileuploader'))


@app.route("/delete/<string:filename>", methods=['DELETE'])
def delete(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file_thumb_path = os.path.join(app.config['THUMBNAIL_FOLDER'], filename)

    if os.path.exists(file_path):
        try:
            os.remove(file_path)

            if os.path.exists(file_thumb_path):
                os.remove(file_thumb_path)
            
            return simplejson.dumps({filename: 'True'})
        except:
            return simplejson.dumps({filename: 'False'})


# serve static files
@app.route("/thumbnail/<string:filename>", methods=['GET'])
def get_thumbnail(filename):
    return send_from_directory(app.config['THUMBNAIL_FOLDER'], filename=filename)


@app.route("/data/<string:filename>", methods=['GET'])
def get_file(filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER']), filename=filename)

@app.route('/fileuploader', methods=['GET', 'POST'])
def fileuploader():
    return render_template('index_uploader.html')

@app.route('/')
def index():
	if 'username' in session:
		return redirect('/dashboard')
	return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
	if 'username' in session:
		return redirect('/dashboard')
	if request.method == "GET":
		if 'alerts' in session:
			alert = session['alerts']
		else:
			alert = None
		return render_template("signup.html", alert=alert)
	elif request.method == "POST":
		username = request.form.get('username')
		password = request.form.get('password')
		name = request.form.get('name')
		sex = request.form.get('sex')
		dob = "2017-04-18"
		address = request.form.get('address')
		email = request.form.get('email')
		number = request.form.get('number')
		conn = mysql.connect()
		cursor = conn.cursor()
		cursor.execute("SELECT * FROM user where username ='" + username + "'")
		data = cursor.fetchone()
		if data is not None:
			msg = "username already exists <br />"
		flag = 0
		flag = cursor.execute("INSERT INTO user (username,password,type) VALUES('"+username+"','"+password+"','user')")
		flag = cursor.execute("INSERT INTO profile (username,name,dob,sex,email,address,number) VALUES('"+username+"','"+name+"','"+dob+"','"+sex+"','"+email+"','"+address+"','"+number+"')")
		conn.commit()
		if flag == 0:
			msg = "wrong inputs, try again. <br />"
		else: 
			msg = "you were successful, please login from index."
		session['alerts'] = msg
		return redirect("/signup")

@app.route('/login', methods=['GET','POST'])
def login():
	if 'username' in session:
		return redirect('/dashboard')	
	username = request.form.get('username')
	password = request.form.get('password')
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT * FROM user where username='" + username + "' and password='" + password + "'")
	data = cursor.fetchone()
	if data is None:
		return render_template('wrong-login.html')
	else:
		session['username'] = username
		session['type'] = data[2] 
		print(session['username'],session['type'])
		return redirect('/dashboard')

@app.route('/admin/users')
def users():
	if 'username' not in session:
		return redirect('/')
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT type FROM user where username='" + session['username'] + "'")
	data = cursor.fetchone()
	if "admin" not in data:
		return "you don't have access to this cause you're not an admin."
	conn = mysql.connect()
	cursor = conn.cursor()
	cursor.execute("SELECT username, type FROM user WHERE EXISTS(SELECT * FROM user WHERE type = \"admin\")")
	data = cursor.fetchall()
	return render_template("users.html",data=data)

@app.route('/products')
def products():
	if 'username' not in session:
		return redirect('/')
	
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session['username'] + "\" and user.username = profile.username")
	data = cursor.fetchone()
	if data is None:
		return abort(404)
	if 'alerts' in session:
		alert = session['alerts']
		session.pop('alerts')
	else:
		alert = None

	products = alchemy_session.query(ProductMaster).all()
	return render_template("products.html",data=data,alert=alert,products=products)

@app.route('/items')
def items():
	if 'username' not in session:
		return redirect('/')
	
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session['username'] + "\" and user.username = profile.username")
	data = cursor.fetchone()
	if data is None:
		return abort(404)
	if 'alerts' in session:
		alert = session['alerts']
		session.pop('alerts')
	else:
		alert = None
	
	items = alchemy_session.query(ItemMaster).all()
	return render_template("items.html",data=data, items=items, alert=alert)

@app.route('/profiles')
def profiles():
	if 'username' not in session:
		return redirect('/')
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT type FROM user where username='" + session['username'] + "'")
	data = cursor.fetchone()
	if "admin" not in data:
		return "you don't have access to this cause you're not an admin."
	conn = mysql.connect()
	cursor = conn.cursor()
	# cursor.execute("SELECT username FROM user WHERE EXISTS(SELECT * FROM user WHERE type = \"admin\")")
	cursor.execute("SELECT * FROM erp.profile")
	data = cursor.fetchall()
	return render_template("profiles.html",data=data)

@app.route('/logout')
def logout():
	if 'username' not in session:
		return redirect('/')
	session.pop('username')
	session.pop('type') 
	return redirect('/')

@app.route('/settings')
def settings():
	if 'username' not in session:
		return redirect('/')
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session['username'] + "\" and user.username = profile.username")
	data = cursor.fetchone()
	if data is None:
		return abort(404)
	if 'alerts' in session:
		alert = session['alerts']
		session.pop('alerts')
	else:
		alert = None
	return render_template('settings.html', data=data, alert=alert)

@app.route('/addproduct', methods=['GET','POST'])
def addproduct():
	if 'username' not in session:
		return redirect('/')
	
	if request.method == "POST":
		# for key in request.form:
		# 	print(key)
		
		in_product = request.form.get('products')
		in_user = request.form.get('users')
		in_recipes = request.form.get('recipes')
		in_targetquantity = request.form.get('targetquantity')
		in_unit = request.form.get('unit')
		in_facilities = request.form.get('facilities')
		in_createddatetime = request.form.get('in_createddatetime')
		print(in_createddatetime)

		import datetime
		date_time_obj = datetime.datetime.strptime(in_createddatetime, '%Y-%m-%dT%H:%M')
		print('Date-time:', date_time_obj)

		product = alchemy_session.query(ProductMaster).filter_by(id=in_product).one()
		user = alchemy_session.query(User).filter_by(username=in_user).one()
		facility = alchemy_session.query(FacilityMaster).filter_by(id=in_facilities).one()
		newproductstats = ProductStatusMaster(product=product, status="OnGoing", created_date=date_time_obj, user=user, unit=in_unit, facility=facility, target_quantity=in_targetquantity, quantity=0)
		alchemy_session.add(newproductstats)
		alchemy_session.commit()
		print(newproductstats)

		return redirect('/showproductstatus')
	else:
		cursor = mysql.connect().cursor()
		cursor.execute("SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session['username'] + "\" and user.username = profile.username")
		data = cursor.fetchone()
		if data is None:
			return abort(404)
		if 'alerts' in session:
			alert = session['alerts']
			session.pop('alerts')
		else:
			alert = None
		
		products = alchemy_session.query(ProductMaster).all()
		users = alchemy_session.query(User).all()
		recipes = alchemy_session.query(RecipeMaster).all()
		facilities = alchemy_session.query(FacilityMaster).all()
		return render_template('addproduct.html', data=data, alert=alert, products=products, users=users, recipes=recipes, facilities=facilities)

@app.route('/showproductstatus', methods=['GET','POST'])
def showproductstatus():
	if 'username' not in session:
		return redirect('/')

	cursor = mysql.connect().cursor()
	cursor.execute("SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session['username'] + "\" and user.username = profile.username")
	data = cursor.fetchone()
	
	if request.method == "GET":
		if data is None:
			return abort(404)
		if 'alerts' in session:
			alert = session['alerts']
			session.pop('alerts')
		else:
			alert = None
		
		productstatuses = alchemy_session.query(ProductStatusMaster).all()
		return render_template('showproductstatus.html', data=data, alert=alert, productstatuses=productstatuses)
	else:

		return 'hello world'

@app.route('/updateproductstatus/<int:productstatus_id>/', methods=['GET','POST'])
def updateproductstatus(productstatus_id):
	if 'username' not in session:
		return redirect('/')

	cursor = mysql.connect().cursor()
	cursor.execute("SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session['username'] + "\" and user.username = profile.username")
	data = cursor.fetchone()
	
	if request.method == "GET":
		if data is None:
			return abort(404)
		if 'alerts' in session:
			alert = session['alerts']
			session.pop('alerts')
		else:
			alert = None
		
		productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
		return render_template('updateproductstatus.html', data=data, alert=alert, productstatus=productstatus)
	else:
		return 'hello world'


@app.route('/showproductstock', methods=['GET','POST'])
def showproductstock():
	if 'username' not in session:
		return redirect('/')

	cursor = mysql.connect().cursor()
	cursor.execute("SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session['username'] + "\" and user.username = profile.username")
	data = cursor.fetchone()
	
	if request.method == "GET":
		if data is None:
			return abort(404)
		if 'alerts' in session:
			alert = session['alerts']
			session.pop('alerts')
		else:
			alert = None
		
		productstocks = alchemy_session.query(ProductStockMaster).all()
		return render_template('showproductstock.html', data=data, alert=alert, productstocks=productstocks)
	else:

		return 'hello world'

@app.route('/dashboard')
def dashboard():
	if 'username' not in session:
		return redirect('/')
	conn = mysql.connect()
	cursor = conn.cursor()
	cursor.execute("SELECT username FROM user WHERE NOT EXISTS (SELECT * FROM profile WHERE user.username = profile.username)")
	data = cursor.fetchone()
	if data is not None:
		if session['username'] in data:
			cursor.execute("DELETE FROM user WHERE username = '"+session['username']+"'")
			conn.commit()
			session.pop('username')
			session.pop('type')
			return "Your details are not filled. Please sign up again <a href=\"/signup\">here</a>. Account has been suspended."
	cursor.execute("SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session['username'] + "\" and user.username = profile.username")
	data = cursor.fetchone()
	if data is None:
		return abort(404)
	return render_template("dashboard.html",data=data)

@app.route('/help')
def help():
	return render_template("help.html")

@app.route('/changesettings', methods=['GET','POST'])
def changesettings():
	if 'username' not in session:
		return redirect('/')
	username = request.form.get('username')
	password = request.form.get('password')
	newAdmin = request.form.get('newAdmin')
	conn = mysql.connect()
	cursor = conn.cursor()
	msg = " "
	if username != "" and username is not None:
		if username == session['username']:
			msg = msg + "<br /> Same Username "
		else:
			cursor.execute("SELECT username FROM user WHERE username = \"" + username + "\"")
			data = cursor.fetchone()
			if data is None:
				msg = msg + "<br /> Username Available"
				cursor.execute("UPDATE user SET username = \"" + username + "\" WHERE username = \"" + session['username'] + "\"" )
				cursor.execute("UPDATE profile SET username = \"" + username + "\" WHERE username = \"" + session['username'] + "\"" )
				conn.commit()
				session['username'] = username
				msg = msg + "<br />username changed to " + username
			else:
				msg = msg + "<br />username already exists"
	else:
		msg = msg + "<br /> username is none"
	if password != "" and password is not None:
		cursor.execute("SELECT password FROM user WHERE username = \"" + username + "\"")
		data = cursor.fetchone()
		if password == data:
			msg = msg + "<br /> Same Password."
		else:
			cursor.execute("UPDATE user SET password = \"" + password + "\" WHERE username = \"" + session['username'] + "\"" )
			conn.commit()
	msg = msg + "<br /> Password changed."
	if newAdmin != "" and newAdmin is not None:
		cursor.execute("SELECT type FROM user WHERE username = \"" + str(newAdmin) + "\"")
		data = cursor.fetchone()
		if data[0] == "admin":
			msg = msg + "<br /> Already admin "
		else:
			cursor.execute("UPDATE user SET type = \"admin\" WHERE username = \"" + str(newAdmin) + "\"" )
			conn.commit()
			msg = msg + "<br />" + newAdmin + " is now admin "
	session['alerts'] = msg		
	return redirect("/settings")

if __name__ == '__main__':
	app.run(host='0.0.0.0',port=8000,debug=True)