import json
import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

app = Flask(__name__)

#Secret key
app.secret_key = "eco-deckmasters-decktrack-2026"


#Load stock
def load_stock():
    path = os.path.join("data", "stock.json")
    f = open(path, "r", encoding="utf-8")
    items = json.load(f)
    f.close()
    return items


#Save stock
def save_stock(items):
    path = os.path.join("data", "stock.json")
    f = open(path, "w", encoding="utf-8")
    json.dump(items, f, indent=2)
    f.close()


#Load the recorded sales
def load_sales():
    path = os.path.join("data", "sales.json")
    if not os.path.exists(path):
        return []
    f = open(path, "r", encoding="utf-8")
    text = f.read().strip()
    f.close()
    if text == "":
        return []
    return json.loads(text)


#Save the recorded sales
def save_sales(sales):
    path = os.path.join("data", "sales.json")
    f = open(path, "w", encoding="utf-8")
    json.dump(sales, f, indent=2)
    f.close()


#Works out the next id number for a new stock item
def next_id(items):
    biggest = 0
    for item in items:
        if item["id"] > biggest:
            biggest = item["id"]
    return biggest + 1


#Returns a list of the categories already used in the stock list
def get_categories(items):
    categories = []
    for item in items:
        if item["category"] not in categories:
            categories.append(item["category"])
    return categories


#Loads the user accounts from the JSON database
def load_users():
    path = os.path.join("data", "users.json")
    f = open(path, "r", encoding="utf-8")
    users = json.load(f)
    f.close()
    return users


#Finds a single user by their username (returns None if not found)
def find_user(username):
    for user in load_users():
        if user["username"] == username:
            return user
    return None


#True if someone is currently logged in
def is_logged_in():
    return "username" in session


#True if the logged in user is an Admin
def is_admin():
    return session.get("role") == "admin"


#Login page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        #Look the user up and check their password against the stored hash
        user = find_user(username)
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html",
                                   error="Incorrect username or password.")

        #Remember who is logged in for the rest of the session
        session["username"] = user["username"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        return redirect(url_for("index"))

    return render_template("login.html", error=None)


#Log out
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


#Home page / dashboard
@app.route("/")
def index():
    if not is_logged_in():
        return redirect(url_for("login"))
    items = load_stock()
    low_items = [it for it in items if it["quantity"] <= it["min_level"]]
    today = datetime.now().strftime("%A %d %B %Y")

    #Work out today's sales and the most recent sales for the dashboard
    sales = load_sales()
    today_str = datetime.now().strftime("%Y-%m-%d")
    sales_today = len([s for s in sales if s["date"].startswith(today_str)])
    recent_sales = sorted(sales, key=lambda s: s["id"], reverse=True)[:5]

    return render_template("index.html",
                           total_items=len(items),
                           low_count=len(low_items),
                           low_items=low_items,
                           sales_today=sales_today,
                           recent_sales=recent_sales,
                           today=today)


#Record a sale - any logged in user (FR07/FR08)
@app.route("/sale", methods=["GET", "POST"])
def sale():
    if not is_logged_in():
        return redirect(url_for("login"))

    items = load_stock()

    if request.method == "POST":
        #Read the chosen item and quantity
        try:
            item_id = int(request.form.get("item_id"))
            quantity = int(request.form.get("quantity", 0))
        except (TypeError, ValueError):
            return render_template("sale.html", items=items, success=None,
                                   error="Please choose an item and a valid quantity.")

        #Find the item that was chosen
        item = None
        for it in items:
            if it["id"] == item_id:
                item = it
                break

        if item is None:
            return render_template("sale.html", items=items, success=None,
                                   error="That item could not be found.")
        if quantity <= 0:
            return render_template("sale.html", items=items, success=None,
                                   error="Quantity must be at least 1.")
        if quantity > item["quantity"]:
            return render_template("sale.html", items=items, success=None,
                                   error="Only " + str(item["quantity"]) + " of that item left in stock.")

        #Reduce the stock on hand and save it
        item["quantity"] -= quantity
        save_stock(items)

        #Record the sale (total is worked out here)
        sales = load_sales()
        new_sale = {
            "id": (max([s["id"] for s in sales], default=0) + 1),
            "item_name": item["name"],
            "quantity": quantity,
            "price": item["price"],
            "total": round(quantity * item["price"], 2),
            "sold_by": session.get("name"),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        sales.append(new_sale)
        save_sales(sales)

        #Show the confirmation with an updated item list
        return render_template("sale.html", items=load_stock(), success=new_sale, error=None)

    return render_template("sale.html", items=items, success=None, error=None)


#Stock page - list, search and sort
@app.route("/stock")
def stock():
    if not is_logged_in():
        return redirect(url_for("login"))

    items = load_stock()

    #Sort by name or quantity depending on which button was pressed
    sort_by = request.args.get("sort", "name")
    if sort_by == "quantity":
        items = sorted(items, key=lambda i: i["quantity"])
    else:
        sort_by = "name"
        items = sorted(items, key=lambda i: i["name"].lower())

    low_count = len([i for i in items if i["quantity"] <= i["min_level"]])
    return render_template("stock.html",
                           items=items,
                           sort_by=sort_by,
                           total_items=len(items),
                           low_count=low_count)


#Edit a stock item - Admin only
@app.route("/stock/edit/<int:item_id>", methods=["GET", "POST"])
def stock_edit(item_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    if not is_admin():
        return redirect(url_for("stock"))

    items = load_stock()

    #Find the item we are editing
    item = None
    for it in items:
        if it["id"] == item_id:
            item = it
            break
    if item is None:
        return redirect(url_for("stock"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()

        #Check the number fields are actually numbers
        try:
            quantity = int(request.form.get("quantity", 0))
            price = float(request.form.get("price", 0))
            min_level = int(request.form.get("min_level", 0))
        except ValueError:
            return render_template("stock_edit.html", item=item,
                                   error="Quantity, price and minimum level must be numbers.")

        if name == "":
            return render_template("stock_edit.html", item=item,
                                   error="Please enter an item name.")

        #Update the item and save the whole list back to the database
        item["name"] = name
        item["quantity"] = quantity
        item["price"] = price
        item["min_level"] = min_level
        save_stock(items)
        return redirect(url_for("stock"))

    return render_template("stock_edit.html", item=item, error=None)


#Delete a stock item - Admin only
@app.route("/stock/delete/<int:item_id>", methods=["POST"])
def stock_delete(item_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    if not is_admin():
        return redirect(url_for("stock"))

    items = load_stock()
    items = [item for item in items if item["id"] != item_id]
    save_stock(items)
    return redirect(url_for("stock"))


#Add stock page - Admin only
@app.route("/stock/add", methods=["GET", "POST"])
def stock_add():
    if not is_logged_in():
        return redirect(url_for("login"))
    #Staff are not allowed to add stock - send them back to the stock list
    if not is_admin():
        return redirect(url_for("stock"))

    items = load_stock()
    categories = get_categories(items)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()

        #Checks the number fields are actually numbers
        try:
            quantity = int(request.form.get("quantity", 0))
            price = float(request.form.get("price", 0))
            min_level = int(request.form.get("min_level", 0))
        except ValueError:
            return render_template("stock_add.html", categories=categories,
                                   error="Quantity, price and minimum level must be numbers.")

        if name == "":
            return render_template("stock_add.html", categories=categories,
                                   error="Please enter an item name.")

        new_item = {
            "id": next_id(items),
            "name": name,
            "category": category or "Uncategorised",
            "quantity": quantity,
            "price": price,
            "min_level": min_level,
        }
        items.append(new_item)
        save_stock(items)
        return redirect(url_for("stock"))

    return render_template("stock_add.html", categories=categories, error=None)


if __name__ == "__main__":
    app.run(debug=True)
