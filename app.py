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
            cart = json.loads(request.form.get("cart", "[]"))
        except ValueError:
            cart = []

        customer = request.form.get("customer", "").strip()
        address = request.form.get("address", "").strip()
        try:
            delivery = float(request.form.get("delivery") or 0)
        except ValueError:
            delivery = 0.0

        if not cart:
            return render_template("sale.html", items=items,
                                   error="Add at least one item to the sale.")

        by_id = {}
        for it in items:
            by_id[it["id"]] = it

        #Add up how much of each item is being sold
        wanted = {}
        for entry in cart:
            iid = entry.get("id")
            qty = int(entry.get("qty", 0))
            if iid not in by_id or qty <= 0:
                return render_template("sale.html", items=items,
                                       error="One of the items is invalid.")
            wanted[iid] = wanted.get(iid, 0) + qty

        #Check there is enough stock
        for iid in wanted:
            if wanted[iid] > by_id[iid]["quantity"]:
                return render_template("sale.html", items=items,
                                       error="Not enough " + by_id[iid]["name"] + " in stock.")

        #Build the invoice lines (each with its own description and discount)
        lines = []
        subtotal = 0
        discount_total = 0
        for entry in cart:
            it = by_id[entry["id"]]
            qty = int(entry["qty"])
            try:
                disc_value = float(entry.get("discount") or 0)
            except (TypeError, ValueError):
                disc_value = 0.0
            if disc_value < 0:
                disc_value = 0.0
            disc_type = entry.get("discountType", "dollar")

            #Work out the dollars off each unit
            if disc_type == "percent":
                if disc_value > 100:
                    disc_value = 100
                per_unit = it["price"] * disc_value / 100
            else:
                if disc_value > it["price"]:
                    disc_value = it["price"]
                per_unit = disc_value

            gross = round(qty * it["price"], 2)
            line_discount = round(qty * per_unit, 2)
            line_total = round(gross - line_discount, 2)
            lines.append({
                "name": it["name"],
                "description": str(entry.get("description", "")).strip(),
                "quantity": qty,
                "price": it["price"],
                "discount_type": disc_type,
                "discount_value": round(disc_value, 2),
                "line_discount": line_discount,
                "line_total": line_total,
            })
            subtotal += gross
            discount_total += line_discount

        #Reduce the stock
        for iid in wanted:
            by_id[iid]["quantity"] -= wanted[iid]
        save_stock(items)

        total = round(subtotal - discount_total + delivery, 2)

        sales = load_sales()
        new_sale = {
            "id": (max([s["id"] for s in sales], default=0) + 1),
            "customer": customer,
            "address": address,
            "lines": lines,
            "subtotal": round(subtotal, 2),
            "discount": round(discount_total, 2),
            "delivery": round(delivery, 2),
            "total": total,
            "sold_by": session.get("name"),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        sales.append(new_sale)
        save_sales(sales)

        return redirect(url_for("invoice", sale_id=new_sale["id"]))

    return render_template("sale.html", items=items, error=None)


#Invoice
@app.route("/invoice/<int:sale_id>")
def invoice(sale_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    sale = None
    for s in load_sales():
        if s["id"] == sale_id:
            sale = s
            break
    if sale is None:
        return redirect(url_for("index"))
    return render_template("invoice.html", sale=sale)


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


#Estimator
@app.route("/estimator")
def estimator():
    if not is_logged_in():
        return redirect(url_for("login"))
    items = sorted(load_stock(), key=lambda i: i["name"].lower())
    return render_template("estimator.html", items=items)


#Map
@app.route("/map")
def job_map():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("map.html")


if __name__ == "__main__":
    app.run(debug=True)
