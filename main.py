from flask import Flask, render_template, request, flash, redirect, abort
import pymysql
import pymysql.cursors 
from dynaconf import Dynaconf
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

app = Flask(__name__)
config = Dynaconf(settings_file=["settings.toml"])
app.secret_key = config.secret_key
login_manager = LoginManager( app )

login_manager.login_view = "/login"

class User:
    is_authenticated = True
    is_active = True
    is_anonymous = False
    
    def __init__(self, result):
        self.name = result['Name']
        self.email = result["Email"]
        self.address = result["Address"]
        self.id = result["ID"]

    def get_id(self):
        return str(self.id)
@login_manager.user_loader
def load_user(user_id):
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(" SELECT * FROM `User` WHERE `ID` = %s ", (user_id))
    result = cursor.fetchone()
    connection.close()

    if result is None:
        return None 
    return User(result)

def connect_db():
    conn = pymysql.connect(
        host="db.steamcenter.tech", 
        user="jprity",
        password= config.password,
        database="jprity_henna_by_heart",
        autocommit= True,
        cursorclass= pymysql.cursors.DictCursor
    )
    return conn


@app.route("/")
def index():
    return render_template("homepage.html.jinja")

@app.route("/browse")
def browse():
    connection = connect_db()

    cursor = connection.cursor()
    cursor.execute("SELECT * FROM `Product` ")
    result = cursor.fetchall()
    connection.close()
    return render_template("browse.html.jinja", products=result)

@app.route("/product/<product_id>")
def product_page(product_id):
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM `Product` WHERE `ID` = %s", (product_id))
    result = cursor.fetchone()

    cursor = connection.cursor()
    cursor.execute(
    "SELECT * FROM `Review` "
    "JOIN `User` ON `User`.ID = `Review`.`UserID` "
    "WHERE `ProductID` = %s",
    (product_id,))
    result2 = cursor.fetchall()
    connection.close()


    if result is None:
        abort(404)

    return render_template("product.html.jinja", product=result, reviews=result2)

@app.route("/product/<product_id>/add_to_cart", methods=["POST"])
@login_required
def add_to_cart(product_id):

    quantity = request.form["QTY"]

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO `Cart` (`Quantity`, `ProductID`, `UserID`)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
        `Quantity` = `Quantity` + %s 
    """, (quantity, product_id, current_user.id, quantity))
        
    connection.close()
    return redirect('/cart')

@app.route("/product/<product_id>/review", methods=["POST"])
@login_required
def add_review(product_id):
    #get imput values from the form
    rating = request.form["rating"]
    comments = request.form["comments"]
    #connect to the database
    connection = connect_db()
    cursor = connection.cursor()

    #Write our SQl add the review 
    cursor.execute("""
    INSERT INTO `Review`
        (`Rating`, `Comments`, `UserID`, `ProductID`)
    VALUES
        (%s, %s, %s, %s)
""", (rating, comments, current_user.id, product_id))

    connection.close()
    #return user back to product page 
    return redirect(f"/product/{product_id}")

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html", error=error), 404


@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
       name = request.form["name"]
       email = request.form["email"]
       password = request.form["password"]
       confirm_password = request.form["confirm_password"]
       address = request.form["address"]
       if password != confirm_password:
           flash("Passwords do not match!")
       elif len(password) < 10:
           flash("Password Is Too Short!")
       else:
           connection = connect_db()
           cursor = connection.cursor()
       try:
           cursor.execute("""
           INSERT INTO `User` (`Name`, `Email`, `Address`, `Password`)
           VALUES (%s, %s, %s, %s)               
                          """, (name, email, address, password))
           connection.close()
       except pymysql.err.IntegrityError:
           flash("User with that email already exists")
           connection.close()
       else:
           return redirect('/login')
       
    return render_template("register.html.jinja")
@app.route("/login", methods= [ "POST" , "GET" ] )
def login():
    if request.method == 'POST':
         email = request.form['email']
         password = request.form['password']

         connection = connect_db()
         cursor = connection.cursor()
         cursor.execute(" SELECT * FROM `User` WHERE `Email` = %s " , (email))
         result = cursor.fetchone()

         connection.close()

         if result is None:
             flash("No user found")
         elif password != result["Password"]:
             flash("Incorrect password!")
         else:
             login_user(User( result ))
             return redirect ('/browse')
    

    return render_template("login.html.jinja")
      
@app.route("/logout", methods=['GET', 'POST'] )
@login_required
def logout():
    logout_user()
    flash("You have been logged out.") 
    return redirect("/")

@app.route("/cart")
@login_required
def cart():

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM `Cart`
        JOIN `Product` ON `Product`.`ID` = `Cart`.`ProductID`
        WHERE `UserID` = %s 
    """, (current_user.id))  

    results = cursor.fetchall() 
    connection.close()

    total = 0
    for item in results:
        total = total + item["Price"] * item["Quantity"]
    
    return render_template("cart.html.jinja", cart=results, total=total)

@app.route('/cart/<product_id>/update_qty', methods=["POST"])
@login_required
def update_cart(product_id):
    new_qty = request.form['qty']
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("""
         UPDATE `Cart`
         SET `Quantity` = %s
         WHERE `ProductID` = %s AND `UserID` = %s
                             
     """, (new_qty, product_id, current_user.id ))
    connection.close()
    return redirect('/cart')


@app.route('/cart/<product_id>/delete', methods=["POST"])
@login_required
def delete_cart_item(product_id):
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("""
        DELETE FROM Cart
        WHERE ProductID = %s AND UserID = %s
    """, (product_id, current_user.id))
    connection.close()
    flash("Item removed from cart")
    return redirect('/cart')

@app.route("/checkout", methods=['GET', 'POST'])
@login_required
def check():

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM `Cart`
        JOIN `Product` ON `Product`.`ID` = `Cart`.`ProductID`
        WHERE `UserID` = %s 
    """, (current_user.id))  

    results = cursor.fetchall() 

    if request.method == 'POST':
        #create the sle in the database 
        cursor.execute("INSERT INTO `Sale` (`UserID`) VALUES (%s)", (current_user.id, ))
        #store products bought
        sale = cursor.lastrowid 
        for item in results:
            cursor.execute("INSERT INTO `SaleCart`(`SaleID`, `ProductID`, `Quantity`) VALUES (%s, %s, %s)", (sale,item['ProductID'], item['Quantity']))
        #empty cart
        cursor.execute("DELETE FROM `Cart` WHERE `UserID` = %s", (current_user.id))
        #thank you screen
        return redirect('/thank-you')

    connection.close()

    total = 0
    for item in results:
        total = total + item["Price"] * item["Quantity"]
    
    return render_template("checkout.html.jinja", cart=results, total=total)

@app.route("/thank-you")
def thank():
    return render_template("thank-you.html.jinja")

@app.route("/order")
@login_required
def order():
    connection = connect_db()

    cursor = connection.cursor()
    cursor.execute("""
                   
        SELECT
              `Sale`.`ID`,
              `Sale`.`Timestamp`,
               SUM(`SaleCart`.`Quantity`) AS "Quantity",
               SUM(`SaleCart`.`Quantity` * `Product`.`Price`) AS "Total"
        FROM `Sale`
        JOIN `SaleCart` ON `SaleCart`.`SaleID` = `Sale`.`ID`
        JOIN `Product` ON `Product`.`ID` = `SaleCart`.`ProductID`
        WHERE `UserID` = %s    
        GROUP BY `Sale`.`ID`; 
                   """, (current_user.id))
    result = cursor.fetchall()
    connection.close()
    
    return render_template("order.html.jinja", orders=result)


    