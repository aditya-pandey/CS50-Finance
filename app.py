import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from time import strftime
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    return render_template("quote.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if lookup(request.form.get("symbol")):
            share = lookup(request.form.get("symbol"))
            if not share or not request.form.get("shares"):
                return apology("please enter valid symbol", 400)

            count = request.form.get("shares")
            if count.isdigit():
                price = share["price"]
                total = float(price)*float(count)

                result = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])
                if result[0]["cash"] > total:
                    cur_time = strftime("%m/%d/%Y %H:%M")

                    db.execute("INSERT INTO portfolio VALUES(:symbol,:name,:shares,:price,:total,:user_id,:cur_time)", symbol=share["symbol"], name=share["name"],
                               shares=count, price=price, total=total, user_id=session["user_id"], cur_time=cur_time)

                    balance = result[0]["cash"] - float(total)
                    db.execute("UPDATE users SET  cash=:balance WHERE id = :user_id", balance=balance, user_id=session["user_id"])

                    return render_template("bought.html", symbol=share["symbol"], name=share["name"], shares=count, price=float(price),
                    total=float(total),balance=balance)

                else:
                    return apology("INSUFFICIENT CASH", 400)
            else:
                return apology("valid shares please",400)
        else:
            return apology("Com'on! There is no such company", 400)
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    username = request.args.get("username")
    ans = db.execute("SELECT * FROM users WHERE username = :username", username=username)
    if len(ans) > 0 :
        return jsonify(False)
    else:
        return jsonify(True)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    result = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])
    data = db.execute("SELECT * FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])
    return render_template("history.html", data=data, balance=usd(result[0]["cash"]))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if lookup(request.form.get("symbol")):
            quote = lookup(request.form.get("symbol"))
            name = quote["name"]
            price = usd(quote["price"])
            symbol = quote["symbol"]
            return render_template("quote-display.html", name=name, price=price, symbol=symbol)
        else:
            return apology("Com'on! There is no such company")
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Missing username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Enter password", 400)

        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("Passwords should match")
        password = generate_password_hash(request.form.get("password"))

        result = db.execute("INSERT INTO users (username,hash) VALUES(:username,:hash)",
                            username=request.form.get("username"), hash=password)

        if not result:
            return apology("Username already exists", 400)

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        session["user_id"] = rows[0]["id"]

        return render_template("quote.html")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Share Not Selected")
        if not request.form.get("shares"):
            return apology("Invalid Shares",400)

        comp = request.form.get("symbol")
        count = request.form.get("shares")

        if count.isdigit():
            data = db.execute("SELECT * FROM portfolio WHERE symbol LIKE :symbol AND user_id = :user_id",
                              user_id=session["user_id"], symbol=comp)
            owned = 0
            for d in data:
                owned = owned + d["shares"]

            if owned >= int(count):
                price = lookup(comp)["price"]
                total = float(count)*float(price)

                result = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])
                balance = result[0]["cash"] + total

                cur_time = strftime("%m/%d/%Y %H:%M")

                db.execute("UPDATE users SET  cash=:balance WHERE id = :user_id", balance=balance, user_id=session["user_id"])

                db.execute("INSERT INTO portfolio VALUES(:symbol,:name,:shares,:price,:total,:user_id,:cur_time)", symbol=lookup(comp)["symbol"], name=lookup(comp)["name"],
                           shares=0-int(count), price=price, total=total, user_id=session["user_id"], cur_time=cur_time)

                return render_template("sold.html", symbol=comp, name=lookup(comp)["name"], shares=count, price=float(price),
                total=float(total),balance=float(balance))
            else:
                return apology("You Do Not have that many shares!!", 400)
        else:
            return apology("Invalid Shares",400)
    else:
        options = db.execute("SELECT * FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])
        shares = []
        for i in range(len(options)):
            shares.append(options[i]["symbol"])
        sell = list(set(shares))
        return render_template("sell.html", options=sell)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)