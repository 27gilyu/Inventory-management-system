## app.py
## DeckTrack - Business Management Website for Eco Deckmasters
##

from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)


## Login page - the entry point of the website
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ## For now any login takes you through to the home page
        return redirect(url_for("index"))
    return render_template("login.html")


## Home page
@app.route("/")
def index():
    return render_template("index.html")


## Runs the local web server
if __name__ == "__main__":
    app.run(debug=True)
