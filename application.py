#!/usr/bin/env python
import string
import random
# New imports from the flask library
from database_setup import Base, Category, CategoryItem
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from flask import Flask,
from flask render_template, request, redirect,
from flask import url_for, jsonify, flash,
from flask import make_response, session as login_session
# IMPORTS FOR THIS STEP
# from oauth2client.client import flow_from_clientsecrets
# from oauth2client.client import FlowExchangeError
from oauth2client import client
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Items and categories"

engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Create anti-forgery state token


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)

# Connect to the Google Sign-in oAuth method.


@app.route('/gconnect', methods=['POST'])
def gconnect():
    '''route to connect google sign-in oauth authorization, in this function
    it will validate the token and obtain authorization code then it
    upgrades the code into a credentials object'''

    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps
                                 ('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius:' \
              ' 150px;-webkit-border-radius: 150px;' \
              '-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# User Helper Functions

''' Helper functions is used to  make your programs easier to read by giving
 descriptive names to computations. It also let us reuse of computations,
 just as with functions in general.'''


def createUser(login_session):
    newUser = User(name=login_session['username'],
                   email=login_session['email'],
                   picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except BaseException:
        return None


@app.route('/gdisconnect')
def gdisconnect():
    '''It will validate the acces token in login session if both
    will match then it allow us to log out and the details of
    users will be also delted from the databse'''
    access_token = login_session.get('access_token')
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps('Current'
                                            ' user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    url = 'https://accounts.google.com/o/oauth2/revoke?token=' \
        '%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect('/')
    else:
        response = make_response(json.dumps(
            'Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        return redirect('/')


# show category
@app.route('/')
@app.route('/category/')
def categories():
    ''' this route will show the categories list '''
    cat = session.query(Category).all()
    return render_template("category.html", cat=cat)

# Show Category JSON


@app.route('/category/JSON')
def categoryJSON():
    cat = session.query(Category).all()
    return jsonify(Category=[i.serialize for i in cat])

# show category items by category id


@app.route('/category/<int:category_id>')
@app.route('/category/<int:category_id>/items/')
def showCategoryItems(category_id):
    cat = session.query(Category).filter_by(id=category_id).first()
    items = session.query(CategoryItem).filter_by(
        category_id=category_id).all()
    return render_template("CategoryItem.html", items=items, cat=cat)

# JSON api endpoints to showcategories


@app.route('/category/<int:category_id>/JSON')
@app.route('/category/<int:category_id>/items/JSON')
def showCategoryItemsJSON(category_id):
    cat = session.query(Category).filter_by(id=category_id).first()
    items = session.query(CategoryItem).filter_by(
        category_id=category_id).all()
    return jsonify(Category=[i.serialize for i in items])

# show categoryitems by item id


@app.route('/category/<int:category_id>/items/<int:item_id>')
def ShowItemDescription(category_id, item_id):
    cat = session.query(Category).filter_by(id=category_id).one()
    des = session.query(CategoryItem).filter_by(id=item_id).first()
    return render_template("itemdescription.html", des=des)

# JSON endpoints api for items


@app.route('/category/<int:category_id>/items/<int:item_id>/JSON')
def ShowItemDescriptionJSON(category_id, item_id):
    des = session.query(CategoryItem).filter_by(id=item_id).one()
    return jsonify(itemDescription=[des.serialize])

# add new category item


@app.route('/category/add/', methods=['GET', 'POST'])
def addItem():
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newCategoryItem = CategoryItem(
            name=request.form['name'],
            description=request.form['description'],
            category_id=request.form['category'],
            user_id=login_session['email'])
        user_id = login_session['email']
        session.add(newCategoryItem)
        session.commit()
        flash("New Items Created")
        return redirect(url_for('categories'))
    else:
        categories = session.query(Category).all()
        return render_template("additem.html", categories=categories)

# edit category items


@app.route('/category/<int:category_id>/items/<int:item_id>/edit',
           methods=['GET', 'POST'])
def editItem(category_id, item_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    if 'username' not in login_session:
        return redirect('/login')
    editedItem = session.query(CategoryItem).filter_by(id=item_id).one()

# Check if logged in user is creator of category item
    if editedItem.user_id != login_session['email']:
        print login_session['email']
        print editedItem.user_id
        return 'Not authorized'
    category = session.query(Category).filter_by(id=category_id).one()
    categories = session.query(Category).all()

    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        session.add(editedItem)
        session.commit()
        flash('Item is edited successfully')
        return redirect(url_for('showCategoryItems', category_id=category_id))
    else:
        return render_template("edititem.html")

# delete category items


@app.route('/category/<int:category_id>/items/<int:item_id>/delete',
           methods=['GET', 'POST'])
def deleteItem(category_id, item_id):
    DBSession = sessionmaker(bind=engine)
    session = DBSession()

    if 'username' not in login_session:
        return redirect('/login')
    deleteItem = session.query(CategoryItem).filter_by(id=item_id).one()

    if deleteItem.user_id != login_session['email']:
        return "Not authorized"

    else:
        if request.method == 'POST':
            session.delete(deleteItem)
            session.commit()
            flash('Item is deleted')
            return redirect(
                url_for(
                    'showCategoryItems',
                    category_id=category_id))
        else:
            return render_template("deletingitem.html")

if __name__ == "__main__":
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
