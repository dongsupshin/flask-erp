from flask import Flask, render_template, request, redirect, session, abort, url_for, send_from_directory, jsonify
from flaskext.mysql import MySQL
from sqlalchemy import asc, desc, join
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.sqltypes import String
from database_setup import Base, engine, User, Profile, FacilityMaster, ProductMaster, ProductStockMaster, ItemMaster, \
    ItemStockMaster, RecipeMaster, ProductStatusMaster, ActiveLoginSession, uuid_url64, LoginHistory, Board
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
from lib.upload_file import uploadfile
from PIL import Image
from inspect import currentframe, getframeinfo
import sys, os, PIL, simplejson, traceback, logging, datetime, json, datetime

now = datetime.datetime.now()
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

def CheckActiveSession():
    try:
        activesessions = alchemy_session.query(ActiveLoginSession).all()
        for row in activesessions:
            last_login = None
            if row.time_updated:
                last_login = row.time_updated
            else:
                last_login = row.time_created

            now = datetime.datetime.now()
            delta = now - last_login
            print(row.username, delta.total_seconds(), now, last_login)
            if delta.total_seconds() > 3600 and now > last_login:
                session_to_delete = alchemy_session.query(ActiveLoginSession).filter_by(id=row.id).one()
                alchemy_session.delete(session_to_delete)
                alchemy_session.commit()
    except Exception as e:
        alchemy_session.rollback()
        logging.error(str(e))
        print(str(e))

@app.before_request
def before_request():
    CheckActiveSession()

    ######################################
    # [TBD]
    if str(request.path).split('/')[1] in ('static', 'upload'):
        return
    ######################################

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
        now = datetime.datetime.now()
        session['last_active'] = now

    try:
        user = alchemy_session.query(User).filter_by(username=username).one()
        loginhistory = LoginHistory(id=str(uuid_url64()), user=user, request_url=request.url, remote_address=request.remote_addr)
        alchemy_session.add(loginhistory)
        alchemy_session.commit()
        # update login active session
        now = datetime.datetime.now()
        session['last_active'] = now
        if ('token' in key_list) == True:
            active_login_session = alchemy_session.query(ActiveLoginSession).filter_by(token=str(session['token'])).one()
            active_login_session.time_updated = session['last_active']
            alchemy_session.add(active_login_session)
            alchemy_session.commit()
    except Exception as e:
        logging.error(str(e))
        alchemy_session.rollback()
        return
    
    # check session expiration
    try:
        last_active = session['last_active']
        now = datetime.datetime.now()
        delta = now - last_active
        if delta.seconds > 3600:
            session['last_active'] = now
            session['alerts'] = "Your session has expired after 30 minutes, you have been logged out"
            disconnect()
    except Exception as e:
        pass

# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
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
        logging.error(str(traceback.format_exc()))
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
        try:
            data = alchemy_session.query(User).filter_by(username=username).one()
            if data is not None:
                msg = "username already exists <br />"
        except Exception as e:
            pass

        flag = 0
        try:
            newuser = User(username=username, password=password, type='user')
            alchemy_session.add(newuser)
            newuserprofile = Profile(user=newuser, name=name, dob=dob, sex=sex, email=email, address=address, number=number)
            alchemy_session.add(newuserprofile)
            alchemy_session.commit()
            flag = 1
        except Exception as e:
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

    if username is None or password is None:
        return render_template('wrong-login.html')

    try:
        data = alchemy_session.query(User).filter_by(username=username).filter_by(password=password).one()
        session['username'] = username
        session['type'] = data.type
        
        user = alchemy_session.query(User).filter_by(username=username).one()

        try:
            older_login_session = alchemy_session.query(ActiveLoginSession).filter_by(user=user).all()
            for old in older_login_session:
                alchemy_session.delete(old)
                alchemy_session.commit()
        except Exception as e:
            logging.error(str(e))

        new_login_session = ActiveLoginSession(user=user, token=str(uuid_url64()))
        alchemy_session.add(new_login_session)
        alchemy_session.commit()
        session['token'] = new_login_session.token
        return redirect('/dashboard')
    except Exception as e:
        logging.error(str(e))
        session['alerts'] = str(e)
        return render_template('wrong-login.html')

@app.route('/admin/users')
def users():
    if 'username' not in session:
        return redirect('/')
    data = alchemy_session.query(User).filter_by(username=session['username']).one()
    if "admin" not in data.type:
        session['alerts'] = "you don't have access to this cause you're not an admin."
        return redirect('/')
    users = alchemy_session.query(User).filter_by(type='admin').all()
    return render_template("users.html", data=data, users=users)

@app.route('/products')
def products():
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    
    data = items[0]

    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    items = []
    for A, B in alchemy_session.query(ProductMaster, ProductStockMaster).filter(ProductMaster.id==ProductStockMaster.product_id).all():
        item = {'id' : A.id, 'name' : A.name, 'time_created' : A.time_created, 'stock' : B.stock}
        items.append(item)
    products=items

    return render_template("products.html", data=data, alert=alert, products=products)

@app.route('/recipes')
def recipes():
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]
    
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    recipes = alchemy_session.query(RecipeMaster).all()
    return render_template("recipes.html", data=data, alert=alert, recipes=recipes)

@app.route('/items')
def items():
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    items = []
    for A, B in alchemy_session.query(ItemMaster, ItemStockMaster).filter(ItemMaster.id == ItemStockMaster.item_id).all():
        item = {'id' : A.id, 'name' : A.name, 'time_created' : A.time_created, 'time_updated' : B.time_updated, 'stock' : B.stock}
        items.append(item)
    
    return render_template("items.html", data=data, items=items, alert=alert)


@app.route('/filelist')
def filelist():
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]
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

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    loginhistories = alchemy_session.query(LoginHistory).order_by(desc(LoginHistory.login_time))
    return render_template("loginhistory.html", data=data, alert=alert, loginhistories=loginhistories)

@app.route('/activeloginsession')
def activeloginsession():
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    activesessions = alchemy_session.query(ActiveLoginSession).all()
    return render_template("activeloginsession.html", data=data, alert=alert, activesessions=activesessions)

@app.route('/profiles')
def profiles():
    if 'username' not in session:
        return redirect('/')
    data = alchemy_session.query(User).filter_by(username=session['username']).one()
    if "admin" not in data.type:
        session['alerts'] = "you don't have access to this cause you're not an admin."
        return redirect('/')
    profiles = alchemy_session.query(Profile).all()
    return render_template("profiles.html", data=data, profiles=profiles)


@app.route('/logout')
def logout():
    if 'username' not in session:
        return redirect('/')

    session_to_delete = alchemy_session.query(ActiveLoginSession).filter_by(token=session['token']).one()
    alchemy_session.delete(session_to_delete)
    alchemy_session.commit()

    session.pop('username')
    session.pop('type')
    session.pop('token')
    return redirect('/')


@app.route('/settings')
def settings():
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]

    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None
    return render_template('settings.html', data=data, alert=alert)

@app.route('/newrecipe', methods=['GET', 'POST'])
def newrecipe():
    if 'username' not in session:
        return redirect('/')

    if request.method == "POST":
        recipename = request.form.get('recipename')
        user = request.form.get('user')
        detail = request.form.get('detail')
        product_id = request.form.get('product')

        try:
            product = alchemy_session.query(ProductMaster).filter_by(id=product_id).one()
            newrecipe = RecipeMaster(name=recipename, detail=detail, product=product)
            alchemy_session.add(newrecipe)
            alchemy_session.commit()
            return redirect('/updaterecipe/' + str(newrecipe.id))
        except Exception as e:
            logging.error(str(e))
            alchemy_session.rollback()
            session['alerts'] = 'you are not allowed to create new recipe.' + str(e)
            return redirect('/')
    else:
        items = []
        for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
            item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
            items.append(item)
        data = items[0]
        if data is None:
            return abort(404)
        if 'alerts' in session:
            alert = session['alerts']
            session.pop('alerts')
        else:
            alert = None
        
        users = alchemy_session.query(User).all()
        items = alchemy_session.query(ItemMaster).all()
        products = alchemy_session.query(ProductMaster).all()
        return render_template('newrecipe.html', data=data, alert=alert, users=users, products=products, items=items)

@app.route('/updaterecipe/<int:recipe_id>', methods=['GET', 'POST'])
def updaterecipe(recipe_id):
    if 'username' not in session:
        return redirect('/')

    if request.method == "POST":
        try:
            recipe = alchemy_session.query(RecipeMaster).filter_by(id=recipe_id).one()
            now = datetime.datetime.now()
            recipe.time_updated = now
            recipe.item_list_in_json = json.dumps(request.json)
            alchemy_session.add(recipe)
            alchemy_session.commit()
            return 'success'
        except Exception as e:
            logging.error(str(e))
            alchemy_session.rollback()
            session['alerts'] = 'you are not allowed to update item_list_in_json.' + str(e)
            return str(e)
    else:
        items = []
        for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
            item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
            items.append(item)
        data = items[0]
        if data is None:
            return abort(404)
        if 'alerts' in session:
            alert = session['alerts']
            session.pop('alerts')
        else:
            alert = None
        
        recipe = alchemy_session.query(RecipeMaster).filter_by(id=recipe_id).one()
        items = alchemy_session.query(ItemMaster).all()
        return render_template('updaterecipe.html', data=data, alert=alert, recipe=recipe, items=items)

@app.route('/newproduct', methods=['GET', 'POST'])
def newproduct():
    if 'username' not in session:
        return redirect('/')

    if request.method == "POST":
        productname = request.form.get('productname')
        stock = request.form.get('InputStock')

        try:
            newproduct = ProductMaster(id=str(uuid_url64()), name=productname)
            alchemy_session.add(newproduct)
            alchemy_session.commit()

            newproductstock = ProductStockMaster(product=newproduct, product_name=newproduct.name, stock=stock)
            alchemy_session.add(newproductstock)
            alchemy_session.commit()
        except Exception as e:
            logging.error(str(e))
            alchemy_session.rollback()
            session['alerts'] = 'you are not allowed to create new product.' + str(e)
            return redirect('/newproduct')

        return redirect('/products')
    else:
        items = []
        for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
            item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
            items.append(item)
        data = items[0]
        if data is None:
            return abort(404)
        if 'alerts' in session:
            alert = session['alerts']
            session.pop('alerts')
        else:
            alert = None

        return render_template('newproduct.html', data=data, alert=alert)

@app.route('/addproduct', methods=['GET', 'POST'])
def addproduct():
    if 'username' not in session:
        return redirect('/')

    if request.method == "POST":
        in_product = request.form.get('products')
        in_user = request.form.get('users')
        in_recipes = request.form.get('recipes')
        in_targetquantity = request.form.get('targetquantity')
        in_unit = request.form.get('unit')
        in_facilities = request.form.get('facilities')
        in_createddatetime = request.form.get('createddatetime')
        in_recipe = request.form.get('recipe')

        date_time_obj = datetime.datetime.strptime(in_createddatetime, '%Y-%m-%dT%H:%M')

        try:
            recipe = alchemy_session.query(RecipeMaster).filter_by(id=in_recipe).one()
            product = alchemy_session.query(ProductMaster).filter_by(id=in_product).one()
            user = alchemy_session.query(User).filter_by(username=in_user).one()
            facility = alchemy_session.query(FacilityMaster).filter_by(id=in_facilities).one()
            newproductstats = ProductStatusMaster(product=product, product_name=product.name, status="OnGoing", created_date=date_time_obj, user=user,
                                                unit=in_unit, facility=facility, target_quantity=in_targetquantity,
                                                quantity=0, recipe=recipe)
            alchemy_session.add(newproductstats)
            alchemy_session.commit()
            return redirect('/showproductstatus')
        except Exception as e:
            logging.error(str(e))
            alchemy_session.rollback()
            session['alerts'] = 'you are not allowed to create new product status.' + str(e)
            return redirect('/showproductstatus')
    else:
        items = []
        for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
            item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
            items.append(item)
        data = items[0]
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

@app.route('/newitem', methods=['GET', 'POST'])
def newitem():
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None
    
    if request.method == "POST":
        in_item = request.form.get('itemname')
        in_user = request.form.get('users')
        in_quantity = request.form.get('quantity')

        try:
            user = alchemy_session.query(User).filter_by(username=in_user).one()
            newitem = ItemMaster(name=in_item,user=user)
            alchemy_session.add(newitem)
            alchemy_session.commit()
            itemstock = ItemStockMaster(item=newitem, stock=int(in_quantity))
            alchemy_session.add(itemstock)
            alchemy_session.commit()
            return redirect('/items')
        except Exception as e:
            logging.error(str(e))
            alchemy_session.rollback()
            session['alerts'] = 'you are not allowed to create new item.' + str(e)
            return redirect('/items')
    else:
        users = alchemy_session.query(User).all()
        return render_template('newitem.html', data=data, alert=alert, users=users)

@app.route('/showproductstatus', methods=['GET'])
def showproductstatus():
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)

    data = items[0]
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    productstatuses = alchemy_session.query(ProductStatusMaster).order_by(ProductStatusMaster.created_date.desc()).all()
    return render_template('showproductstatus.html', data=data, alert=alert, productstatuses=productstatuses)

@app.route('/showboard', methods=['GET'])
def showboard():
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]
    if request.method == "GET":
        if data is None:
            return abort(404)
        if 'alerts' in session:
            alert = session['alerts']
            session.pop('alerts')
        else:
            alert = None
            boards = alchemy_session.query(Board).all()
            return render_template("board.html", data=data, boards=boards)

@app.route('/updateproductstatus/<int:productstatus_id>/', methods=['GET', 'POST'])
def updateproductstatus(productstatus_id):
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    if request.method == "GET":
        productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
        return render_template('updateproductstatus.html', data=data, alert=alert, productstatus=productstatus)
    else:
        quantity = request.form.get('quantity') # update button clicked
        is_commit = request.form.get('IsCommit')
        is_cancel_commit = request.form.get('IsCancelCommit')
        
        productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
        productstock = alchemy_session.query(ProductStockMaster).filter_by(product_id=productstatus.product_id).one()
        recipe = alchemy_session.query(RecipeMaster).filter_by(id=productstatus.recipe_id).one()

        if is_commit == 'True':
            if productstatus.status == 'Finished':
                session['alerts'] = 'productstatus ' + str(productstatus.id) + ' has been already commited.'
                return abort(404, description=session['alerts'])

            if recipe.item_list_in_json is None:
                session['alerts'] = 'recipe.item_list_in_json ' + str(recipe.id) + ' is empty.'
                return abort(404, description=session['alerts'])

            productstatus.status = 'Finished'
            now = datetime.datetime.now()
            productstatus.time_updated = now
            alchemy_session.add(productstatus)
            alchemy_session.commit()

            # plus stock
            item_list = []
            if recipe.item_list_in_json is None:
                session['alerts'] = 'recipe_id ' + str(productstatus.recipe_id) + ' : productstatus.item_list_in_json is None.'
                return redirect('/showproductstatus')
            if len(recipe.item_list_in_json) == 0:
                session['alerts'] = 'recipe_id ' + str(productstatus.recipe_id) + ' : productstatus.item_list_in_json is empty.'
                return redirect('/showproductstatus')
            else:
                item_list = json.loads(recipe.item_list_in_json)
                for row in item_list:
                    item = alchemy_session.query(ItemMaster).filter_by(name=row['item']).one()
                    item_stock_to_be_required = productstatus.quantity * int(row['quantity'])
                    item_stock_in_db = alchemy_session.query(ItemStockMaster).filter_by(item_id=item.id).one()
                    if item_stock_to_be_required > item_stock_in_db.stock:
                        session['alerts'] = 'item stock is not enough. ' + 'item_stock_to_be_required : ' + str(item_stock_to_be_required) + ', item_stock_in_db.stock : ' + str(item_stock_in_db.stock)
                        return redirect('/showproductstatus')
            
            stock = int(productstock.stock) + int(productstatus.quantity)
 
            try:
                productstock = alchemy_session.query(ProductStockMaster).filter_by(id=productstock.id).one()
                productstock.stock = stock
                now = datetime.datetime.now()
                productstock.time_updated = now
                alchemy_session.add(productstock)
                alchemy_session.commit()
            except Exception as e:
                logging.error(str(e))
                alchemy_session.rollback()
                session['alerts'] = 'you are not allowed to update the record.' + str(e)
                return redirect('/showproductstatus')

            for row in item_list:
                try:
                    item = alchemy_session.query(ItemMaster).filter_by(name=row['item']).one()
                    item_stock_to_be_required = productstatus.quantity * int(row['quantity'])
                    item_stock_in_db = alchemy_session.query(ItemStockMaster).filter_by(item_id=item.id).one()
                    stock = int(item_stock_in_db.stock) - int(item_stock_to_be_required)
                    item_stock_in_db.stock = stock
                    now = datetime.datetime.now()
                    item_stock_in_db.time_updated = now
                    alchemy_session.add(item_stock_in_db)
                    alchemy_session.commit()
                except Exception as e:
                    logging.error(str(e))
                    alchemy_session.rollback()
                    session['alerts'] = 'you are not allowed to update the record.' + str(e)
                    return redirect('/showproductstatus')

            return redirect('/showproductstatus')

        if is_cancel_commit == 'True':
            if productstatus.status in ('OnGoing'):
                session['alerts'] = 'productstatus ' + str(productstatus.id) + ' has been already canceled.'
                return abort(404, description=session['alerts'])

            if recipe.item_list_in_json is None:
                session['alerts'] = 'recipe.item_list_in_json ' + str(recipe.id) + ' is empty.'
                return abort(404, description=session['alerts'])
            

            productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
            productstatus.status = 'OnGoing'
            now = datetime.datetime.now()
            productstatus.time_updated = now
            alchemy_session.add(productstatus)
            alchemy_session.commit()
            
            # minus stock
            productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
            productstock = alchemy_session.query(ProductStockMaster).filter_by(product_id=productstatus.product_id).one()
            stock = int(productstock.stock) - int(productstatus.quantity)
            
            productstock = alchemy_session.query(ProductStockMaster).filter_by(id=productstock.id).one()
            productstock.stock = stock
            now = datetime.datetime.now()
            productstock.time_updated = now
            alchemy_session.add(productstock)
            alchemy_session.commit()

            item_list = json.loads(recipe.item_list_in_json)

            for row in item_list:
                item = alchemy_session.query(ItemMaster).filter_by(name=row['item']).one()
                item_stock_to_be_required = productstatus.quantity * int(row['quantity'])
                item_stock_in_db = alchemy_session.query(ItemStockMaster).filter_by(item_id=item.id).one()
                stock = int(item_stock_in_db.stock) + int(item_stock_to_be_required)
                
                item_stock_in_db.stock = stock
                now = datetime.datetime.now()
                item_stock_in_db.time_updated = now
                alchemy_session.add(item_stock_in_db)
                alchemy_session.commit()

            return redirect('/showproductstatus')

        productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
        if productstatus.status == 'Finished':
            session['alerts'] = 'you are not allowed to upate the product status record ' + str(productstatus.id) + ' because is has been committed.'
            return redirect('/showproductstatus')
        else:            
            productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
            productstatus.quantity = quantity
            now = datetime.datetime.now()
            productstatus.time_updated = now
            alchemy_session.add(productstatus)
            alchemy_session.commit()
            return redirect('/showproductstatus')

@app.route('/updateitemstock/<int:item_id>/', methods=['GET', 'POST'])
def updateitemstock(item_id):
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]

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
        quantity = request.form.get('quantity')
        itemstock = alchemy_session.query(ItemStockMaster).filter_by(id=item_id).one()
        itemstock.stock = quantity
        now = datetime.datetime.now()
        itemstock.time_updated = now
        alchemy_session.add(itemstock)
        alchemy_session.commit()
        return redirect('/items')

@app.route('/showproductstock', methods=['GET'])
def showproductstock():
    if 'username' not in session:
        return redirect('/')

    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]
    if request.method == "GET":
        if data is None:
            return abort(404)
        if 'alerts' in session:
            alert = session['alerts']
            session.pop('alerts')
        else:
            alert = None

        productstocks = alchemy_session.query(ProductStockMaster).order_by(ProductStockMaster.time_created.desc()).all()
        return render_template('showproductstock.html', data=data, alert=alert, productstocks=productstocks)


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
    items = []
    for A, B in alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).all():
        item = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
        items.append(item)
    data = items[0]
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
            try:
                data = alchemy_session.query(User).filter_by(username=username).one()
                msg = msg + "<br />username already exists"
            except Exception as e:
                # this is not error
                msg = msg + "<br /> Username Available"

                user_to_update = alchemy_session.query(User).filter_by(username=session['username']).one()
                user_to_update.username = username
                profile_to_update = alchemy_session.query(Profile).filter_by(username=session['username']).one()
                profile_to_update.username = username
                alchemy_session.commit()
                session['username'] = username
                msg = msg + "<br />username changed to " + username
    else:
        msg = msg + "<br /> username is none"
    if password != "" and password is not None:
        data = alchemy_session.query(User).filter_by(username=username).one()
        if password == data.password:
            msg = msg + "<br /> Same Password."
        else:
            data.password = password
            alchemy_session.commit()
    msg = msg + "<br /> Password changed."
    if newAdmin != "" and newAdmin is not None:
        try:
            data = alchemy_session.query(User).filter_by(username=str(newAdmin)).one()
            if data.type == "admin":
                msg = msg + "<br /> Already admin "
            else:
                data.type = 'admin'
                alchemy_session.commit()
                msg = msg + "<br />" + newAdmin + " is now admin "
        except Exception as e:
            logging.error(str(e))
            session['alerts'] = str(e)
            return redirect("/settings")

    session['alerts'] = msg
    return redirect("/settings")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
