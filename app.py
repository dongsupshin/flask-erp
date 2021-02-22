from flask import Flask, render_template, request, redirect, session, abort, url_for, send_from_directory, jsonify
from sqlalchemy import asc, desc, join
from sqlalchemy_filters import apply_pagination
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.sqltypes import String
from database_setup import Base, engine, User, Profile, FacilityMaster, ProductMaster, ProductStockMaster, ItemMaster, \
    ItemStockMaster, RecipeMaster, ProductStatusMaster, ActiveLoginSession, uuid_url64, LoginHistory, Board
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from lib.upload_file import uploadfile
from common import GetFileName, GetLineNumber, ALLOWED_EXTENSIONS, IGNORED_FILES, allowed_file, gen_file_name, create_thumbnail
import sys, os, PIL, simplejson, traceback, logging, datetime, json, datetime

# filename, file_extension = os.path.splitext(os.path.basename(__file__))
filename = './flask_erp_log.log'
# logging.basicConfig(handlers=[logging.FileHandler(filename=filename, 
#                                                  encoding='utf-8', mode='a+')],
#                     format="%(asctime)s %(name)s:%(levelname)s:%(message)s", 
#                     datefmt="%F %A %T", 
#                     level=logging.INFO)

logging.basicConfig(level=logging.INFO)

app = Flask('__name__')
app.config['SECRET_KEY'] = os.urandom(20)
app.config['UPLOAD_FOLDER'] = 'data/'
app.config['THUMBNAIL_FOLDER'] = 'data/thumbnail/'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
bootstrap = Bootstrap(app)

# Connect to Database and create database session
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
alchemy_session = DBSession()

@app.errorhandler(404)
def page_not_found(e):
    logging.error(str(e) + ' path : ' + request.path)
    alchemy_session.rollback()

    ######################################
    # [TBD]
    if str(request.path).split('/')[1] in ('static', 'upload', 'loginhistory'):
        return e
    ######################################

    alert = None
    if 'alerts' in session:
        alert = session['alerts']
    
    if alert:
        alert += ', ' + str(e)
    else:
        alert = str(e)

    return render_template('404.html', alert=alert), 404

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(str(e))
    alchemy_session.rollback()

    ######################################
    # [TBD]
    if str(request.path).split('/')[1] in ('static', 'upload'):
        return e
    ######################################

    alert = None
    if 'alerts' in session:
        alert = session['alerts']
    if alert:
        alert += ' ' + str(e)
    else:
        alert = str(e)
    del session
    return render_template("500.html", alert=alert), 500

@app.before_request
def before_request():
    ######################################
    # [TBD]
    if str(request.path).split('/')[1] in ('static', 'upload'):
        return
    ######################################

    username = None
    if ('username' in session) == True:
        username = session['username']
        CheckActiveSession()
        user = alchemy_session.query(User).filter_by(username=username).one()
        loginhistory = LoginHistory(id=str(uuid_url64()), user=user, request_url=request.url, remote_address=request.remote_addr)
        alchemy_session.add(loginhistory)
        alchemy_session.commit()
    if ('last_active' in session) == False:
        now = datetime.datetime.utcnow()
        session['last_active'] = now

    # update login active session
    now = datetime.datetime.utcnow()
    session['last_active'] = now
    if ('token' in session) == True:
        active_login_session = alchemy_session.query(ActiveLoginSession).filter_by(token=str(session['token'])).one()
        active_login_session.time_updated = session['last_active']
        alchemy_session.add(active_login_session)
        alchemy_session.commit()
    
    # check session expiration
    last_active = session['last_active']
    now = datetime.datetime.utcnow()
    delta = now - last_active
    if delta.seconds > 3600:
        session['last_active'] = now
        session['alerts'] = "Your session has expired after 30 minutes, you have been logged out"
        disconnect()

def CheckActiveSession():
    activesessions = alchemy_session.query(ActiveLoginSession).all()
    for row in activesessions:
        last_login = None
        if row.time_updated:
            last_login = row.time_updated
        else:
            last_login = row.time_created

        now = datetime.datetime.utcnow()
        delta = now - last_login
        if delta.total_seconds() > 3600:
            session_to_delete = alchemy_session.query(ActiveLoginSession).filter_by(id=row.id).one()
            alchemy_session.delete(session_to_delete)
            alchemy_session.commit()
            
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
   
# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    del session
    return redirect(url_for('index'))

@app.route('/')
def index():
    if 'username' in session:
        return redirect('/dashboard')
    
    alert = None
    if 'alerts' in session:
        alert = session['alerts']

    return render_template('index.html', alert=alert)

@app.route('/index_uploader')
def index_uploader():
    if 'username' in session:
        return redirect('/dashboard')
    return render_template('index_uploader.html')

def getuser():
    A, B = alchemy_session.query(User, Profile).filter(User.username == Profile.username, User.username == session['username']).one()
    user = {'username' : A.username, 'name' : B.name, 'dob' : B.dob, 'sex' : B.sex, 'email' : B.email, 'number' : B.number, 'address' : B.address}
    
    return user

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'username' in session:
        return redirect('/dashboard')
    if request.method == "GET":
        alert = None
        if 'alerts' in session:
            alert = session['alerts']
        else:
            alert = None
        
        sex_list = ['Male', 'Female']
        return render_template("signup.html", alert=alert, sex_list=sex_list)
    elif request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        sex = request.form.get('sex')
        dob = request.form.get('dob')
        dob = datetime.datetime.strptime(dob, '%Y-%m-%d')
        address = request.form.get('address')
        email = request.form.get('email')
        number = request.form.get('number')
        try:
            data = alchemy_session.query(User).filter_by(username=username).one()
            if data is not None:
                msg = "username already exists <br />"
        except Exception as e:
            alchemy_session.rollback()
            pass

        flag = 0
        try:
            newuser = User(uuid=str(uuid_url64()), username=username, password=password, type='user')
            alchemy_session.add(newuser)
            newuserprofile = Profile(user=newuser, name=name, dob=dob, sex=sex, email=email, address=address, number=number)
            alchemy_session.add(newuserprofile)
            alchemy_session.commit()
            flag = 1
        except Exception as e:
            alchemy_session.rollback()
            logging.error(str(e))
            flag = 0

        if flag == 0:
            msg = "wrong inputs, try again. <br />"
        else:
            msg = username + ' has been registered. please sign in.'
            session['alerts'] = msg
            return redirect("/")
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

        older_login_session = alchemy_session.query(ActiveLoginSession).filter_by(user=user).all()
        for old in older_login_session:
            alchemy_session.delete(old)
            alchemy_session.commit()

        token = str(uuid_url64())
        new_login_session = ActiveLoginSession(user=user, token=token)
        alchemy_session.add(new_login_session)
        alchemy_session.commit()
        session['token'] = token
        return redirect('/dashboard')
    except Exception as e:
        alchemy_session.rollback()
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
    users = alchemy_session.query(User).all()    
    return render_template("users.html", data=data, users=users)

@app.route('/admin/users/<username>/update')
def updateuser(username):
    if 'username' not in session:
        return redirect('/')
    data = alchemy_session.query(User).filter_by(username=session['username']).one()
    if "admin" not in data.type:
        session['alerts'] = "you don't have access to this cause you're not an admin."
        return redirect('/')
    user = alchemy_session.query(User).filter_by(username=username).one()
    return render_template("updateuser.html", data=data, user=user)

@app.route('/admin/users/delete/<username>/', methods=['GET'])
def deleteuser(username):
    if 'username' not in session:
        return redirect('/')
    
    if request.method == "GET":
        data = getuser()
        if data is None:
            return abort(404)
        
        user = alchemy_session.query(User).filter_by(username=username).one()
        alchemy_session.delete(user)
        alchemy_session.commit()
        session.pop('username')
        session.pop('token')
        return redirect('/')

@app.route('/products')
def products():
    if 'username' not in session:
        return redirect('/')

    data = getuser()
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

@app.route('/deleteproduct/<product_id>/', methods=['GET'])
def deleteproduct(product_id):
    if 'username' not in session:
        return redirect('/')
    
    if request.method == "GET":
        data = getuser()
        if data is None:
            return abort(404)
        
        product = alchemy_session.query(ProductMaster).filter_by(id=product_id).one()
        alchemy_session.delete(product)
        alchemy_session.commit()
        return redirect('/products')

@app.route('/recipes')
def recipes():
    if 'username' not in session:
        return redirect('/')

    data = getuser()
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    recipes = alchemy_session.query(RecipeMaster).all()
    return render_template("recipes.html", data=data, alert=alert, recipes=recipes)

@app.route('/getrecipes/product/<product_id>')
def getrecipes(product_id):
    if 'username' not in session:
        return redirect('/')
    
    recipes = alchemy_session.query(RecipeMaster).filter_by(product_id=product_id).all()
    return jsonify(recipes=[r.serialize for r in recipes])

@app.route('/deleterecipe/<int:recipe_id>/', methods=['GET'])
def deleterecipe(recipe_id):
    if 'username' not in session:
        return redirect('/')
    
    if request.method == "GET":
        
        data = getuser()
        if data is None:
            return abort(404)
        
        recipe = alchemy_session.query(RecipeMaster).filter_by(id=recipe_id).one()
        alchemy_session.delete(recipe)
        alchemy_session.commit()
        return redirect('/recipes')

@app.route('/items')
def items():
    if 'username' not in session:
        return redirect('/')

    data = getuser()
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

@app.route('/itemsstock')
def itemsstock():
    if 'username' not in session:
        return redirect('/')

    data = getuser()
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    stocks = alchemy_session.query(ItemStockMaster).all()
    return render_template("itemsstock.html", data=data, alert=alert, stocks=stocks)

@app.route('/filelist')
def filelist():
    if 'username' not in session:
        return redirect('/')

    data = getuser()
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    return render_template("filelist.html", data=data, alert=alert)

@app.route('/loginhistory/<int:page>')
def loginhistory(page):
    if 'username' not in session:
        return redirect('/')

    data = getuser()
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    loginhistories = alchemy_session.query(LoginHistory).order_by(desc(LoginHistory.login_time))

    query, pagination = apply_pagination(loginhistories, page_number=page, page_size=10)    
    page_size, page_number, num_pages, total_results = pagination
    loginhistories = alchemy_session.execute(query)
    num_pages = [page for page in range(1, num_pages+1)]
    return render_template("loginhistory.html", data=data, alert=alert, loginhistories=loginhistories, page_size=page_size, page_number=page_number, num_pages=num_pages, total_results=total_results)

@app.route('/activeloginsession')
def activeloginsession():
    if 'username' not in session:
        return redirect('/')
    
    data = getuser()
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
    user = data
    profiles = None
    if "admin" not in data.type:
        profiles = alchemy_session.query(Profile).filter_by(username=user.username).one()
    else:
        profiles = alchemy_session.query(Profile).all()

    return render_template("profiles.html", data=data, user=user, profiles=profiles)

@app.route('/profiles/update/<username>', methods=['GET', 'POST'])
def updateprofile(username):
    if 'username' not in session:
        return redirect('/')

    if request.method == "POST":
        selected_username = request.form.get('selected_username')
        name = request.form.get('name')
        sex = request.form.get('sex')
        dob = request.form.get('dob')
        dob = datetime.datetime.strptime(dob, '%Y-%m-%d')
        address = request.form.get('address')
        email = request.form.get('email')
        number = request.form.get('number')

        profile = alchemy_session.query(Profile).filter_by(username=selected_username).one()
        profile.name = name
        profile.sex = sex
        profile.dob = dob
        profile.address = address
        profile.email = email
        profile.number = number
        alchemy_session.add(profile)
        alchemy_session.commit()
        
        return redirect('/profiles')
    else:
        data = alchemy_session.query(User).filter_by(username=session['username']).one()
        profile = alchemy_session.query(Profile).filter_by(username=username).one()
        sex_list = ['Male', 'Female']
        return render_template("updateprofile.html", data=data, profile=profile, sex_list=sex_list)

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

    data = getuser()
    if data is None:
        return abort(404)
    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    user = alchemy_session.query(User).filter_by(username=data['username']).one()
    return render_template('settings.html', data=data, alert=alert, user=user)

@app.route('/newrecipe', methods=['GET', 'POST'])
def newrecipe():
    if 'username' not in session:
        return redirect('/')

    if request.method == "POST":
        recipename = request.form.get('recipename')
        detail = request.form.get('detail')
        product_id = request.form.get('product')

        try:
            product = alchemy_session.query(ProductMaster).filter_by(id=product_id).one()
            newrecipe = RecipeMaster(name=recipename, detail=detail, product=product)
            alchemy_session.add(newrecipe)
            alchemy_session.commit()
            return redirect('/updaterecipe/' + str(newrecipe.id))
        except Exception as e:
            alchemy_session.rollback()
            logging.error(str(e))
            session['alerts'] = 'you are not allowed to create new recipe.' + str(e)
            return redirect('/')
    else:
        data = getuser()
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
            recipe.item_list_in_json = json.dumps(request.json)
            alchemy_session.add(recipe)
            alchemy_session.commit()
            return 'success'
        except Exception as e:
            alchemy_session.rollback()
            logging.error(str(e))
            session['alerts'] = 'you are not allowed to update item_list_in_json.' + str(e)
            return str(e)
    else:
        data = getuser()
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
            alchemy_session.rollback()
            logging.error(str(e))
            session['alerts'] = 'you are not allowed to create new product.' + str(e)
            return redirect('/newproduct')

        return redirect('/products')
    else:
        data = getuser()
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
            newproductstats = ProductStatusMaster(product=product, product_name=product.name, status="Idle", created_date=date_time_obj, user=user,
                                                unit=in_unit, facility=facility, target_quantity=in_targetquantity,
                                                quantity=0, recipe=recipe)
            alchemy_session.add(newproductstats)
            alchemy_session.commit()
            return redirect('/showproductstatus')
        except Exception as e:
            alchemy_session.rollback()
            logging.error(str(e))
            session['alerts'] = 'you are not allowed to create new product status.' + str(e)
            return redirect('/showproductstatus')
    else:
        data = getuser()
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

    data = getuser()
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
            itemstock = ItemStockMaster(item=newitem, item_name=newitem.name, stock=int(in_quantity))
            alchemy_session.add(itemstock)
            alchemy_session.commit()
            return redirect('/items')
        except Exception as e:
            alchemy_session.rollback()
            logging.error(str(e))
            session['alerts'] = 'you are not allowed to create new item.' + str(e)
            return redirect('/items')
    else:
        users = alchemy_session.query(User).all()
        return render_template('newitem.html', data=data, alert=alert, users=users)

@app.route('/showproductstatus', methods=['GET'])
def showproductstatus():
    if 'username' not in session:
        return redirect('/')

    data = getuser()
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

    if request.method == "GET":
        data = getuser()
        if data is None:
            return abort(404)
        if 'alerts' in session:
            session.pop('alerts')
        else:
            boards = alchemy_session.query(Board).all()
            return render_template("board.html", data=data, boards=boards)

def updateproductstatusupdate(productstatus_id, quantity):
    productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()

    if productstatus.status == 'Finished':
        session['alerts'] = 'you are not allowed to upate the product status record ' + str(productstatus.id) + ' because is has been committed.'
        return redirect('/showproductstatus')
    else:            
        productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
        productstatus.quantity = quantity
        productstatus.status = 'OnGoing'
        alchemy_session.add(productstatus)
        alchemy_session.commit()
        return redirect('/showproductstatus')

def updateproductstatuscommit(productstatus_id, is_commit):
    try:
        productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
        productstock = alchemy_session.query(ProductStockMaster).filter_by(product_id=productstatus.product_id).one()
        recipe = alchemy_session.query(RecipeMaster).filter_by(id=productstatus.recipe_id).one()
    except Exception as e:
        logging.error(str(e))
        session['alerts'] = str(e)
        return abort(404, description=session['alerts'])

    if is_commit == 'True':
        if productstatus.status == 'Finished':
            session['alerts'] = 'productstatus ' + str(productstatus.id) + ' has been already commited.'
            return abort(404, description=session['alerts'])

        if recipe.item_list_in_json is None:
            session['alerts'] = 'recipe.item_list_in_json ' + str(recipe.id) + ' is empty.'
            return abort(404, description=session['alerts'])

        productstatus.status = 'Finished'
        alchemy_session.add(productstatus)

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
            # check items availability
            for row in item_list:
                item = alchemy_session.query(ItemMaster).filter_by(name=row['item']).one()
                item_stock_to_be_required = productstatus.quantity * int(row['quantity'])
                item_stock_in_db = alchemy_session.query(ItemStockMaster).filter_by(item_id=item.id).one()
                if item_stock_to_be_required > item_stock_in_db.stock:
                    session['alerts'] = 'item stock is not enough. ' + 'item_stock_to_be_required : ' + str(item_stock_to_be_required) + ', item_stock_in_db.stock : ' + str(item_stock_in_db.stock)
                    return abort(404, description=session['alerts'])

        alchemy_session.commit()
        
        stock = int(productstock.stock) + int(productstatus.quantity) 
        try:
            productstock = alchemy_session.query(ProductStockMaster).filter_by(id=productstock.id).one()
            productstock.stock = stock
            alchemy_session.add(productstock)
            alchemy_session.commit()
        except Exception as e:
            alchemy_session.rollback()
            logging.error(str(e))
            session['alerts'] = 'you are not allowed to update the record.' + str(e)
            return redirect('/showproductstatus')

        for row in item_list:
            try:
                item = alchemy_session.query(ItemMaster).filter_by(name=row['item']).one()
                item_stock_to_be_required = productstatus.quantity * int(row['quantity'])
                item_stock_in_db = alchemy_session.query(ItemStockMaster).filter_by(item_id=item.id).one()
                stock = int(item_stock_in_db.stock) - int(item_stock_to_be_required)
                item_stock_in_db.stock = stock
                alchemy_session.add(item_stock_in_db)
                alchemy_session.commit()
            except Exception as e:
                alchemy_session.rollback()
                logging.error(str(e))
                session['alerts'] = 'you are not allowed to update the record.' + str(e)
                return redirect('/showproductstatus')

        return redirect('/showproductstatus')
    else:
        session['alerts'] = 'invalid request. is_commit : ' + str(is_commit)
        return abort(404, description=session['alerts'])

def updateproductstatuscancelcommit(productstatus_id, is_cancel_commit):
    try:
        productstatus = alchemy_session.query(ProductStatusMaster).filter_by(id=productstatus_id).one()
        productstock = alchemy_session.query(ProductStockMaster).filter_by(product_id=productstatus.product_id).one()
        recipe = alchemy_session.query(RecipeMaster).filter_by(id=productstatus.recipe_id).one()
    except Exception as e:
        logging.error(str(e))
        session['alerts'] = str(e)
        return abort(404, description=session['alerts'])

    if is_cancel_commit == 'True':
        if productstatus.status in ('Idle', 'OnGoing'):
            productstatus.status = 'Idle'
            productstatus.quantity = 0
            alchemy_session.add(productstatus)
            alchemy_session.commit()
            return redirect('/showproductstatus')

        if recipe.item_list_in_json is None:
            session['alerts'] = 'recipe.item_list_in_json ' + str(recipe.id) + ' is empty.'
            return redirect('/showproductstatus')
        
        productstatus.status = 'Idle'
        
        # minus stock
        productstock = alchemy_session.query(ProductStockMaster).filter_by(product_id=productstatus.product_id).one()
        stock = int(productstock.stock) - int(productstatus.quantity)
        productstock.stock = stock
        alchemy_session.add(productstatus)
        alchemy_session.add(productstock)

        item_list = json.loads(recipe.item_list_in_json)
        for row in item_list:
            item = alchemy_session.query(ItemMaster).filter_by(name=row['item']).one()
            item_stock_to_be_required = productstatus.quantity * int(row['quantity'])
            item_stock_in_db = alchemy_session.query(ItemStockMaster).filter_by(item_id=item.id).one()
            stock = int(item_stock_in_db.stock) + int(item_stock_to_be_required)
            item_stock_in_db.stock = stock
            alchemy_session.add(item_stock_in_db)

        alchemy_session.commit()
        return redirect('/showproductstatus')
    else:
        session['alerts'] = 'invalid request. is_cancel_commit : ' + str(is_cancel_commit)
        return abort(404, description=session['alerts'])

@app.route('/updateproductstatus/<int:productstatus_id>/', methods=['GET', 'POST'])
def updateproductstatus(productstatus_id):
    if 'username' not in session:
        return redirect('/')

    if request.method == "GET":
        data = getuser()
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
        quantity = request.form.get('quantity') # update button clicked
        is_commit = request.form.get('IsCommit')
        is_cancel_commit = request.form.get('IsCancelCommit')

        if quantity:
            return updateproductstatusupdate(productstatus_id, quantity)
        elif is_commit:
            return updateproductstatuscommit(productstatus_id, is_commit)
        elif is_cancel_commit:
            return updateproductstatuscancelcommit(productstatus_id, is_cancel_commit)
        else:
            session['alerts'] = 'input params are empty.'
            return redirect('/showproductstatus')

@app.route('/updateitem/<int:item_id>/', methods=['GET', 'POST'])
def updateitem(item_id):
    if 'username' not in session:
        return redirect('/')
    
    if request.method == "GET":
        data = getuser()
        if data is None:
            return abort(404)
        if 'alerts' in session:
            alert = session['alerts']
            session.pop('alerts')
        else:
            alert = None

        itemstock = alchemy_session.query(ItemStockMaster).filter_by(item_id=item_id).one()
        return render_template('updateitem.html', data=data, alert=alert, itemstock=itemstock)
    else:
        previous_item_name = None
        quantity = request.form.get('quantity')
        itemstock = alchemy_session.query(ItemStockMaster).filter_by(item_id=item_id).one()
        previous_item_name = itemstock.item_name
        itemstock.stock = quantity
        itemstock.item_name = request.form.get('itemname')
        alchemy_session.add(itemstock)

        itemname = request.form.get('itemname')
        item = alchemy_session.query(ItemMaster).filter_by(id=item_id).one()
        item.name = itemname
        alchemy_session.add(item)

        # recipe item update
        recipes = alchemy_session.query(RecipeMaster).all()
        for row in recipes:
            if previous_item_name:
                row.item_list_in_json = row.item_list_in_json.replace(previous_item_name, itemname)
                alchemy_session.add(row)

        alchemy_session.commit()
        return redirect('/items')

@app.route('/deleteitem/<int:item_id>/', methods=['GET'])
def deleteitem(item_id):
    if 'username' not in session:
        return redirect('/')
    
    if request.method == "GET":
        
        data = getuser()
        if data is None:
            return abort(404)
        
        item = alchemy_session.query(ItemMaster).filter_by(id=item_id).one()
        alchemy_session.delete(item)
        alchemy_session.commit()
        return redirect('/items')

@app.route('/updateproduct/<product_id>/', methods=['GET', 'POST'])
def updateproduct(product_id):
    if 'username' not in session:
        return redirect('/')
    
    if request.method == "GET":
        data = getuser()
        if data is None:
            return abort(404)
        if 'alerts' in session:
            alert = session['alerts']
            session.pop('alerts')
        else:
            alert = None

        product = alchemy_session.query(ProductMaster).filter_by(id=product_id).one()
        return render_template('updateproduct.html', data=data, alert=alert, product=product)
    else:
        productname = request.form.get('productname')
        product = alchemy_session.query(ProductMaster).filter_by(id=product_id).one()
        product.name = productname
        alchemy_session.add(product)
        alchemy_session.commit()

        productstock = alchemy_session.query(ProductStockMaster).filter_by(product_id=product_id).one()
        productstock.product_name = productname
        alchemy_session.add(productstock)
        alchemy_session.commit()

        productstatuses = alchemy_session.query(ProductStatusMaster).filter_by(product_id=product_id).all()
        for row in productstatuses:
            row.product_name = productname
            alchemy_session.add(row)        
        alchemy_session.commit()

        return redirect('/products')

@app.route('/showproductstock', methods=['GET'])
def showproductstock():
    if 'username' not in session:
        return redirect('/')

    if request.method == "GET":
        data = getuser()
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

    users = alchemy_session.query(User).all()
    for user in users:
        username = user.username
        if session['username'] not in username:
            continue
        
        count = alchemy_session.query(Profile).filter_by(username=username).count()
        if count > 0:
            break
        count = alchemy_session.query(User).filter_by(username=username).count()
        if count > 0:
            break

        if count == 0:
            session.pop('username')
            session.pop('type')
            return "Your details are not filled. Please sign up again <a href=\"/signup\">here</a>. Account has been suspended."
    
    data = getuser()
    if data is None:
        return abort(404)

    if 'alerts' in session:
        alert = session['alerts']
        session.pop('alerts')
    else:
        alert = None

    return render_template("dashboard.html", data=data, alert=alert)

@app.route('/help')
def help():
    return render_template("help.html")

@app.route('/changesettings', methods=['GET', 'POST'])
def changesettings():
    if 'username' not in session:
        return redirect('/')
    
    if request.method == "POST":
        selected_username = request.form.get('selected_username')
        newusername = request.form.get('username')
        newpassword = request.form.get('password')
        newAdmin = request.form.get('newAdmin')
        
        msg = " "
        if newusername != "" and newusername is not None:
            if newusername == selected_username:
                msg = msg + ' username is same.'
                pass
            else:
                count = alchemy_session.query(User).filter_by(username=newusername).count()
                if count > 0:
                    msg = msg + " username already exists."
                else:
                    # this is not error, update user and profile
                    try:
                        ##############################################################################
                        # [TBD]
                        id, token, time_created, now, time_updated = None, None, None, None, None
                        try:
                            active_session = alchemy_session.query(ActiveLoginSession).filter_by(username=selected_username).one()
                            id = active_session.id
                            token = active_session.token
                            time_created = active_session.time_created
                            now = datetime.datetime.utcnow()
                            time_updated = now
                            alchemy_session.delete(active_session)
                            alchemy_session.commit()
                        except Exception as e:
                            pass

                        profile = alchemy_session.query(Profile).filter_by(username=selected_username).one()
                        dob = profile.dob
                        sex = profile.sex
                        email = profile.email
                        address = profile.address
                        number = profile.number
                        alchemy_session.delete(profile)
                        alchemy_session.commit()
                        
                        user_to_update = alchemy_session.query(User).filter_by(username=selected_username).one()
                        user_to_update.username = newusername
                        alchemy_session.add(user_to_update)
                        alchemy_session.commit()

                        user_to_update = alchemy_session.query(User).filter_by(username=newusername).one()
                        profile = Profile(user=user_to_update, name=user_to_update.username, dob=dob, sex=sex, email=email, address=address, number=number)
                        alchemy_session.add(profile)
                        alchemy_session.commit()

                        if id:
                            active_session = ActiveLoginSession(id=id, user=user_to_update, token=token,time_created=time_created, time_updated=time_updated)
                            alchemy_session.delete(active_session)
                            alchemy_session.commit()
                        ##############################################################################

                        msg = msg + " username changed to " + newusername + '.'
                        selected_username = newusername
                    except Exception as e:
                        alchemy_session.rollback()
                        logging.error(str(e))
                        session['alerts'] = str(e)
                        return redirect("/")
        else:
            msg = msg + " username is none."

        if newpassword != "" and newpassword is not None:
            try:
                data = alchemy_session.query(User).filter_by(username=selected_username).one()
                if newpassword == data.password:
                    msg = msg + " password is same."
                    pass
                else:
                    data.password = newpassword
                    alchemy_session.add(data)
                    alchemy_session.commit()
                    msg = msg + "Password changed."
            except Exception as e:
                alchemy_session.rollback()
                logging.error(str(e))
                session['alerts'] = str(e)
                return redirect("/")
            
        if newAdmin != "" and newAdmin is not None:
            try:
                data = alchemy_session.query(User).filter_by(username=str(newAdmin)).one()
                if data.type == "admin":
                    msg = msg + "Already admin "
                else:
                    data.type = 'admin'
                    alchemy_session.commit()
                    msg = msg + " " + newAdmin + " is now admin "
            except Exception as e:
                alchemy_session.rollback()
                logging.error(str(e))
                session['alerts'] = str(e)
                return redirect("/")

        session['alerts'] = msg
        return redirect("/")
    else:
        return redirect("/settings")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
