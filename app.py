## app.py
## DeckTrack - Business Management Website for Eco Deckmasters
##

import json
import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

app = Flask(__name__)

## Secret key - used by Flask to keep the login session secure
app.secret_key = "eco-deckmasters-decktrack-2026"


## Loads the stock list from the JSON database in the data folder
def load_stock():
    path = os.path.join("data", "stock.json")
    f = open(path, "r", encoding="utf-8")
    items = json.load(f)
    f.close()
    return items


## Saves the stock list back to the JSON database
def save_stock(items):
    path = os.path.join("data", "stock.json")
    f = open(path, "w", encoding="utf-8")
    json.dump(items, f, indent=2)
    f.close()


## Works out the next id number for a new stock item
def next_id(items):
    biggest = 0
    for item in items:
        if item["id"] > biggest:
            biggest = item["id"]
    return biggest + 1


## Returns a list of the categories already used in the stock list
def get_categories(items):
    categories = []
    for item in items:
        if item["category"] not in categories:
            categories.append(item["category"])
    return categories


## Groups the stock items by their category, keeping the price-list order
def group_by_category(items):
    groups = []
    for item in items:
        found = None
        for g in groups:
            if g["category"] == item["category"]:
                found = g
                break
        if found is None:
            found = {"category": item["category"], "products": []}
            groups.append(found)
        found["products"].append(item)
    return groups


## Loads the user accounts from the JSON database
def load_users():
    path = os.path.join("data", "users.json")
    f = open(path, "r", encoding="utf-8")
    users = json.load(f)
    f.close()
    return users


## Finds a single user by their username (returns None if not found)
def find_user(username):
    for user in load_users():
        if user["username"] == username:
            return user
    return None


## True if someone is currently logged in
def is_logged_in():
    return "username" in session


## True if the logged in user is an Admin
def is_admin():
    return session.get("role") == "admin"


## Login page - the entry point of the website (FR01)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        ## Look the user up and check their password against the stored hash
        user = find_user(username)
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html",
                                   error="Incorrect username or password.")

        ## Remember who is logged in for the rest of the session
        session["username"] = user["username"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        return redirect(url_for("index"))

    return render_template("login.html", error=None)


## Log out - clears the session and returns to the login page
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


## Home page / dashboard
@app.route("/")
def index():
    if not is_logged_in():
        return redirect(url_for("login"))
    items = load_stock()
    low_items = [it for it in items if it["quantity"] <= it["min_level"]]
    today = datetime.now().strftime("%A %d %B %Y")
    return render_template("index.html",
                           total_items=len(items),
                           low_count=len(low_items),
                           low_items=low_items,
                           sales_today=0,
                           today=today)


## Stock page - any logged in user can view
@app.route("/stock")
def stock():
    if not is_logged_in():
        return redirect(url_for("login"))
    items = load_stock()
    low_items = [it for it in items if it["quantity"] <= it["min_level"]]
    groups = group_by_category(items)
    return render_template("stock.html",
                           groups=groups,
                           total_items=len(items),
                           low_count=len(low_items))


## Add stock page - Admin only (FR02, role-based access)
@app.route("/stock/add", methods=["GET", "POST"])
def stock_add():
    if not is_logged_in():
        return redirect(url_for("login"))
    ## Staff are not allowed to add stock - send them back to the stock list
    if not is_admin():
        return redirect(url_for("stock"))

    items = load_stock()
    categories = get_categories(items)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()

        ## Check the number fields are actually numbers
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


## Runs the local web server
if __name__ == "__main__":
    app.run(debug=True)
