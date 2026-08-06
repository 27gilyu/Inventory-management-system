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


#Load sales
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


#Save sales
def save_sales(sales):
    path = os.path.join("data", "sales.json")
    f = open(path, "w", encoding="utf-8")
    json.dump(sales, f, indent=2)
    f.close()


#Next id
def next_id(items):
    biggest = 0
    for item in items:
        if item["id"] > biggest:
            biggest = item["id"]
    return biggest + 1


#Categories
def get_categories(items):
    categories = []
    for item in items:
        if item["category"] not in categories:
            categories.append(item["category"])
    return categories


#Load users
def load_users():
    path = os.path.join("data", "users.json")
    f = open(path, "r", encoding="utf-8")
    users = json.load(f)
    f.close()
    return users


#Find user
def find_user(username):
    for user in load_users():
        if user["username"] == username:
            return user
    return None


#Logged in
def is_logged_in():
    return "username" in session


#Is admin
def is_admin():
    return session.get("role") == "admin"


#Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = find_user(username)
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html",
                                   error="Incorrect username or password.")

        session["username"] = user["username"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        return redirect(url_for("index"))

    return render_template("login.html", error=None)


#Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


#Dashboard
@app.route("/")
def index():
    if not is_logged_in():
        return redirect(url_for("login"))
    items = load_stock()
    low_items = [it for it in items if it["quantity"] <= it["min_level"]]
    today = datetime.now().strftime("%A %d %B %Y")

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


#Record sale
@app.route("/sale", methods=["GET", "POST"])
def sale():
    if not is_logged_in():
        return redirect(url_for("login"))

    items = load_stock()

    if request.method == "POST":
        try:
            item_id = int(request.form.get("item_id"))
            quantity = int(request.form.get("quantity", 0))
        except (TypeError, ValueError):
            return render_template("sale.html", items=items, success=None,
                                   error="Please choose an item and a valid quantity.")

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

        item["quantity"] -= quantity
        save_stock(items)

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

        return render_template("sale.html", items=load_stock(), success=new_sale, error=None)

    return render_template("sale.html", items=items, success=None, error=None)


#Stock
@app.route("/stock")
def stock():
    if not is_logged_in():
        return redirect(url_for("login"))

    items = load_stock()

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


#Edit stock
@app.route("/stock/edit/<int:item_id>", methods=["GET", "POST"])
def stock_edit(item_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    if not is_admin():
        return redirect(url_for("stock"))

    items = load_stock()

    item = None
    for it in items:
        if it["id"] == item_id:
            item = it
            break
    if item is None:
        return redirect(url_for("stock"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()

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

        item["name"] = name
        item["quantity"] = quantity
        item["price"] = price
        item["min_level"] = min_level
        save_stock(items)
        return redirect(url_for("stock"))

    return render_template("stock_edit.html", item=item, error=None)


#Delete stock
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


#Add stock
@app.route("/stock/add", methods=["GET", "POST"])
def stock_add():
    if not is_logged_in():
        return redirect(url_for("login"))
    if not is_admin():
        return redirect(url_for("stock"))

    items = load_stock()
    categories = get_categories(items)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()

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


#Map
@app.route("/map")
def job_map():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("map.html")


if __name__ == "__main__":
    app.run(debug=True)
