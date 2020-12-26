from flask import Flask, render_template, request, redirect, session, abort, url_for, send_from_directory, flash
from flaskext.mysql import MySQL
from sqlalchemy import asc, desc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, engine, User, Profile, FacilityMaster, ProductMaster, ProductStockMaster, ItemMaster, \
    ItemStockMaster, RecipeMaster, ProductStatusMaster, ActiveLoginSession, uuid_url64, LoginHistory
from flask_bootstrap import Bootstrap
# deprecated
# from werkzeug import secure_filename
from werkzeug.utils import secure_filename
from lib.upload_file import uploadfile
from PIL import Image
from inspect import currentframe, getframeinfo
# print(frameinfo.filename, frameinfo.lineno)
import sys, os, PIL, simplejson, traceback, logging

from datetime import datetime
today = datetime.now()
filename = "log_" + today.strftime('%Y%m%d') + ".log"
filename = "flask_erp_log.log"
logging.basicConfig(filename=filename, level=logging.DEBUG)

def getFileName():
    frameinfo = getframeinfo(currentframe())
    return frameinfo.filename

def GetLineNumber():
    cf = currentframe()
    return cf.f_back.f_lineno

app = Flask('__name__')
app.config['SECRET_KEY'] = os.urandom(20)
app.config['MYSQL_DATABASE_USER'] = 'dbms'
app.config['MYSQL_DATABASE_PASSWORD'] = 'justanothersecret'
app.config['MYSQL_DATABASE_DB'] = 'erp'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['UPLOAD_FOLDER'] = 'data/'
app.config['THUMBNAIL_FOLDER'] = 'data/thumbnail/'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

mysql = MySQL()
mysql.init_app(app)
mysqlconn = mysql.connect()
mysqlcursor = mysqlconn.cursor()

# Connect to Database and create database session
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
alchemy_session = DBSession()

# add flask file uploader
ALLOWED_EXTENSIONS = set(
    ['txt', 'gif', 'png', 'jpg', 'jpeg', 'bmp', 'rar', 'zip', '7zip', 'doc', 'docx', 'csv', 'xlsx'])
IGNORED_FILES = set(['.gitignore'])

bootstrap = Bootstrap(app)

@app.before_request
def before_request():
    ######################################
    # [TBD]
    if str(request.path).split('/')[1] in ('static', 'upload'):
        return
    ######################################

    import datetime
    now = datetime.datetime.now()

    key_list = []
    for key in session:
        key_list.append(key)
    
    username = ''
    type = ''
    if ('username' in key_list) == True:
        username = session['username']
    if ('type' in key_list) == True:
        type = session['type']
    if ('last_active' in key_list) == False:
        session['last_active'] = now

    try:
        user = alchemy_session.query(User).filter_by(username=username).one()
        loginhistory = LoginHistory(id=str(uuid_url64()), user=user, request_url=request.url, remote_address=request.remote_addr)
        alchemy_session.add(loginhistory)
        alchemy_session.commit()
        # create login active session
        activeloginsession = ActiveLoginSession(user=user, token=str(uuid_url64()))
        alchemy_session.add(activeloginsession)
        alchemy_session.commit()
        session['token'] = activeloginsession.token
    except Exception as e:
        msg = str(e)
        logging.error(msg)
        return

    
    if ('token' in key_list) == True:
        try:
            active_session_object = alchemy_session.query(ActiveLoginSession).filter_by(token=session['token']).one()
            active_session_object.updated_date = session['last_active']
            alchemy_session.add(active_session_object)
            alchemy_session.commit()
        except Exception as e:
            msg = str(e)
            logging.error(msg)
            return redirect('/login')
    else:
        return

    # check session expiration
    try:
        last_active = session['last_active']
        delta = now - last_active
        if delta.seconds > 3600:
            session['last_active'] = now
            flash("Your session has expired after 30 minutes, you have been logged out")
            disconnect()
    except Exception as e:
        pass

# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    print('disconnect!!!')
    print(session)
    del session
    return redirect(url_for('index'))


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
        print(traceback.format_exc())
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
        files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if
                 os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], f)) and f not in IGNORED_FILES]

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


@app.route('/index_uploader')
def index_uploader():
    if 'username' in session:
        return redirect('/dashboard')
    return render_template('index_uploader.html')


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
        mysqlcursor.execute("SELECT * FROM user where username ='" + username + "'")
        data = mysqlcursor.fetchone()
        if data is not None:
            msg = "username already exists <br />"

        flag = 0
        try:
            flag = mysqlcursor.execute(
                "INSERT INTO user (username,password,type) VALUES('" + username + "','" + password + "','user')")
            flag = mysqlcursor.execute(
                "INSERT INTO profile (username,name,dob,sex,email,address,number) VALUES('" + username + "','" + name + "','" + dob + "','" + sex + "','" + email + "','" + address + "','" + number + "')")
            mysqlconn.commit()
        except Exception as e:
            mysqlconn.rollback()
            logging.error(str(e))
            flag = 0

        if flag == 0:
            msg = "wrong inputs, try again. <br />"
        else:
            msg = "you were successful, please login from index."
        session['alerts'] = msg
        return redirect("/signup")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect('/dashboard')
    username = request.form.get('username')
    password = request.form.get('password')
    mysqlcursor.execute("SELECT * FROM user where username='" + username + "' and password='" + password + "'")
    data = mysqlcursor.fetchone()
    if data is None:
        return render_template('wrong-login.html')
    else:
        session['username'] = username
        session['type'] = data[2]
        print(session['username'], session['type'])
        return redirect('/dashboard')


@app.route('/admin/users')
def users():
    if 'username' not in session:
        return redirect('/')
    mysqlcursor.execute("SELECT type FROM user where username='" + session['username'] + "'")
    data = mysqlcursor.fetchone()
    if "admin" not in data:
        return "you don't have access to this cause you're not an admin."
    mysqlcursor.execute("SELECT username, type FROM user WHERE EXISTS(SELECT * FROM user WHERE type = \"admin\")")
    data = mysqlcursor.fetchall()
    return render_template("users.html", data=data)

@app.route('/products')
def products():
    if 'username' not in session:
        return redirect('/')

    mysqlcursor.execute(
        "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
            'username'] + "\" and user.username = profile.username")
    data = mysqlcursor.fetchone()
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    products = alchemy_session.query(ProductMaster).all()
    return render_template("products.html", data=data, alert=alert, products=products)


@app.route('/items')
def items():
    if 'username' not in session:
        return redirect('/')

    mysqlcursor.execute(
        "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
            'username'] + "\" and user.username = profile.username")
    data = mysqlcursor.fetchone()
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    items = alchemy_session.query(ItemMaster).all()
    return render_template("items.html", data=data, items=items, alert=alert)


@app.route('/filelist')
def filelist():
    if 'username' not in session:
        return redirect('/')

    mysqlcursor.execute(
        "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
            'username'] + "\" and user.username = profile.username")
    data = mysqlcursor.fetchone()
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    return render_template("filelist.html", data=data, alert=alert)

@app.route('/loginhistory')
def loginhistory():
    if 'username' not in session:
        return redirect('/')

    mysqlcursor.execute(
        "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
            'username'] + "\" and user.username = profile.username")
    data = mysqlcursor.fetchone()
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    loginhistories = alchemy_session.query(LoginHistory).order_by(desc(LoginHistory.login_time))
    return render_template("loginhistory.html", data=data, alert=alert, loginhistories=loginhistories)

@app.route('/profiles')
def profiles():
    if 'username' not in session:
        return redirect('/')
    mysqlcursor.execute("SELECT type FROM user where username='" + session['username'] + "'")
    data = mysqlcursor.fetchone()
    if "admin" not in data:
        return "you don't have access to this cause you're not an admin."
    mysqlcursor.execute("SELECT * FROM erp.profile")
    data = mysqlcursor.fetchall()
    return render_template("profiles.html", data=data)


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
    mysqlcursor.execute(
        "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
            'username'] + "\" and user.username = profile.username")
    data = mysqlcursor.fetchone()
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None
    return render_template('settings.html', data=data, alert=alert)


@app.route('/addproduct', methods=['GET', 'POST'])
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
        newproductstats = ProductStatusMaster(product=product, status="OnGoing", created_date=date_time_obj, user=user,
                                              unit=in_unit, facility=facility, target_quantity=in_targetquantity,
                                              quantity=0)
        alchemy_session.add(newproductstats)
        alchemy_session.commit()
        print(newproductstats)

        return redirect('/showproductstatus')
    else:
        mysqlcursor.execute(
            "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
                'username'] + "\" and user.username = profile.username")
        data = mysqlcursor.fetchone()
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
        return render_template('addproduct.html', data=data, alert=alert, products=products, users=users,
                               recipes=recipes, facilities=facilities)

@app.route('/additem', methods=['GET', 'POST'])
def additem():
    if 'username' not in session:
        return redirect('/')

    if request.method == "POST":
        in_item = request.form.get('itemname')
        in_user = request.form.get('users')

        user = alchemy_session.query(User).filter_by(username=in_user).one()
        newitem = ItemMaster(name=in_item,user=user)
        alchemy_session.add(newitem)
        alchemy_session.commit()
        itemstock = ItemStockMaster(item=newitem, stock=100)
        alchemy_session.add(itemstock)
        alchemy_session.commit()
        return redirect('/items')
    else:
        mysqlcursor.execute(
            "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
                'username'] + "\" and user.username = profile.username")
        data = mysqlcursor.fetchone()
        if data is None:
            return abort(404)
        if 'alerts' in session:
            alert = session['alerts']
            session.pop('alerts')
        else:
            alert = None

        users = alchemy_session.query(User).all()
        return render_template('additem.html', data=data, alert=alert, users=users)

@app.route('/showproductstatus', methods=['GET', 'POST'])
def showproductstatus():
    if 'username' not in session:
        return redirect('/')

    mysqlcursor.execute(
        "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
            'username'] + "\" and user.username = profile.username")
    data = mysqlcursor.fetchone()

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


@app.route('/updateproductstatus/<int:productstatus_id>/', methods=['GET', 'POST'])
def updateproductstatus(productstatus_id):
    if 'username' not in session:
        return redirect('/')

    mysqlcursor.execute(
        "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
            'username'] + "\" and user.username = profile.username")
    data = mysqlcursor.fetchone()

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
        if data is None:
            return abort(404)
        if 'alerts' in session:
            alert = session['alerts']
            session.pop('alerts')
        else:
            alert = None
        # POST
        # for key in request.form:
        # 	print(key)
        quantity = request.form.get('quantity')
        is_commit = request.form.get('IsCommit')
        is_cancel_commit = request.form.get('IsCancelCommit')

        # print('is_commit : ', is_commit)
        # print('is_cancel_commit : ', is_cancel_commit)

        if is_commit == 'True':
            str_query = 'update ' + str(ProductStatusMaster.__tablename__)
            str_query += ' set status = \'Finished\''
            str_query += ' where id = ' + str(productstatus_id)
            mysqlcursor.execute(str_query)
            mysqlconn.commit()

            # plus stock
            productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
            productstock = alchemy_session.query(ProductStockMaster).filter_by(product_id=productstatus.product_id).one()
            print('stock : ', productstock.stock)
            stock = int(productstock.stock) + int(productstatus.quantity)
            print('new stock : ', stock)

            str_query = 'update ' + str(ProductStockMaster.__tablename__)
            str_query += ' set stock = ' + str(stock)
            str_query += ' where id = ' + str(productstock.id)
            mysqlcursor.execute(str_query)
            mysqlconn.commit()

            return redirect('/showproductstatus')

        if is_cancel_commit == 'True':
            str_query = 'update ' + str(ProductStatusMaster.__tablename__)
            str_query += ' set status = \'OnGoing\''
            str_query += ' where id = ' + str(productstatus_id)
            mysqlcursor.execute(str_query)
            mysqlconn.commit()

            # minus stock
            productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
            productstock = alchemy_session.query(ProductStockMaster).filter_by(product_id=productstatus.product_id).one()
            print('stock : ', productstock.stock)
            stock = int(productstock.stock) - int(productstatus.quantity)
            print('new stock : ', stock)

            str_query = 'update ' + str(ProductStockMaster.__tablename__)
            str_query += ' set stock = ' + str(stock)
            str_query += ' where id = ' + str(productstock.id)
            mysqlcursor.execute(str_query)
            mysqlconn.commit()

            return redirect('/showproductstatus')

        productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
        if productstatus.status == 'Finished':
            productstatuses = alchemy_session.query(ProductStatusMaster).all()
            alert = 'you are not allowed to upate the product status record ' + str(productstatus.id) + ' because is has been committed.'
            return render_template('showproductstatus.html', data=data, alert=alert, productstatuses=productstatuses)
        else:    
            str_query = 'update ' + str(ProductStatusMaster.__tablename__)
            str_query += ' set quantity = ' + str(quantity)
            str_query += ' where id = ' + str(productstatus.id)
            print(str_query)
            mysqlcursor.execute(str_query)
            mysqlconn.commit()
            return redirect('/showproductstatus')

@app.route('/updateitemstock/<int:item_id>/', methods=['GET', 'POST'])
def updateitemstock(item_id):
    if 'username' not in session:
        return redirect('/')

    mysqlcursor.execute(
        "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
            'username'] + "\" and user.username = profile.username")
    data = mysqlcursor.fetchone()

    if request.method == "GET":
        if data is None:
            return abort(404)
        if 'alerts' in session:
            alert = session['alerts']
            session.pop('alerts')
        else:
            alert = None

        itemstock = alchemy_session.query(ItemStockMaster).filter_by(item_id=item_id).one()
        return render_template('updateitemstock.html', data=data, alert=alert, itemstock=itemstock)
    else:
        # POST
        # for key in request.form:
        # 	print(key)
        quantity = request.form.get('quantity')

        str_query = 'update ' + str(ItemStockMaster.__tablename__)
        str_query += ' set stock = ' + str(quantity)
        str_query += ' where item_id = ' + str(item_id)
        print(str_query)
        mysqlcursor.execute(str_query)
        mysqlconn.commit()
        return redirect('/items')

@app.route('/showproductstock', methods=['GET', 'POST'])
def showproductstock():
    if 'username' not in session:
        return redirect('/')

    mysqlcursor.execute(
        "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
            'username'] + "\" and user.username = profile.username")
    data = mysqlcursor.fetchone()

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
    mysqlcursor.execute(
        "SELECT username FROM user WHERE NOT EXISTS (SELECT * FROM profile WHERE user.username = profile.username)")
    data = mysqlcursor.fetchone()
    if data is not None:
        if session['username'] in data:
            mysqlcursor.execute("DELETE FROM user WHERE username = '" + session['username'] + "'")
            mysqlcursor.commit()
            session.pop('username')
            session.pop('type')
            return "Your details are not filled. Please sign up again <a href=\"/signup\">here</a>. Account has been suspended."
    mysqlcursor.execute(
        "SELECT name, dob, sex, email, number, address FROM user, profile where user.username = \"" + session[
            'username'] + "\" and user.username = profile.username")
    data = mysqlcursor.fetchone()
    if data is None:
        return abort(404)
    return render_template("dashboard.html", data=data)


@app.route('/help')
def help():
    return render_template("help.html")


@app.route('/changesettings', methods=['GET', 'POST'])
def changesettings():
    if 'username' not in session:
        return redirect('/')
    username = request.form.get('username')
    password = request.form.get('password')
    newAdmin = request.form.get('newAdmin')
    msg = " "
    if username != "" and username is not None:
        if username == session['username']:
            msg = msg + "<br /> Same Username "
        else:
            mysqlcursor.execute("SELECT username FROM user WHERE username = \"" + username + "\"")
            data = mysqlcursor.fetchone()
            if data is None:
                msg = msg + "<br /> Username Available"
                mysqlcursor.execute(
                    "UPDATE user SET username = \"" + username + "\" WHERE username = \"" + session['username'] + "\"")
                mysqlcursor.execute("UPDATE profile SET username = \"" + username + "\" WHERE username = \"" + session[
                    'username'] + "\"")
                mysqlcursor.commit()
                session['username'] = username
                msg = msg + "<br />username changed to " + username
            else:
                msg = msg + "<br />username already exists"
    else:
        msg = msg + "<br /> username is none"
    if password != "" and password is not None:
        mysqlcursor.execute("SELECT password FROM user WHERE username = \"" + username + "\"")
        data = mysqlcursor.fetchone()
        if password == data:
            msg = msg + "<br /> Same Password."
        else:
            mysqlcursor.execute(
                "UPDATE user SET password = \"" + password + "\" WHERE username = \"" + session['username'] + "\"")
            mysqlcursor.commit()
    msg = msg + "<br /> Password changed."
    if newAdmin != "" and newAdmin is not None:
        mysqlcursor.execute("SELECT type FROM user WHERE username = \"" + str(newAdmin) + "\"")
        data = mysqlcursor.fetchone()
        if data[0] == "admin":
            msg = msg + "<br /> Already admin "
        else:
            mysqlcursor.execute("UPDATE user SET type = \"admin\" WHERE username = \"" + str(newAdmin) + "\"")
            mysqlcursor.commit()
            msg = msg + "<br />" + newAdmin + " is now admin "
    session['alerts'] = msg
    return redirect("/settings")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
