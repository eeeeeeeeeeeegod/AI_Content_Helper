from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from flask_login import (
    current_user,
    login_user,
    logout_user,
    login_required
)

from extensions import (
    db,
    limiter
)

from models import User

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

auth_bp = Blueprint(
    "auth",
    __name__
)



# 使用者註冊
@auth_bp.route(
    "/register",
    methods=["GET", "POST"]
)
@limiter.limit("3 per minute", methods=["POST"])
def register():

    if current_user.is_authenticated:

        return redirect(
            url_for("projects.index")
        )


    error = None


    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()


        password = request.form.get(
            "password",
            ""
        )


        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        # =================================
        # 檢查 Email
        # =================================

        if (
            len(email) > 255
            or email.count("@") != 1
            or not email.split("@")[0]
            or "." not in email.split("@")[1]
        ):

            error = "請輸入有效的 Email"


        # =================================
        # 檢查密碼
        # =================================

        elif len(password) < 12:

            error = "密碼長度至少需要 12 個字元"


        elif password != confirm_password:

            error = "兩次輸入的密碼不一致"


        else:

            # =============================
            # 確認 Email 沒有被註冊
            # =============================

            existing_user = (
                User.query
                .filter_by(
                    email=email
                )
                .first()
            )


            if existing_user:

                error = "這個 Email 已經被註冊"


            else:

              # 將使用者輸入的密碼轉成雜湊值

                hashed_password = generate_password_hash(
                    password
                )
                
                # 建立使用者資料
                
                user = User(
                    email=email,
                    password_hash=hashed_password
                )
                
                db.session.add(user)
                
                db.session.commit()


                print(
                    "新使用者建立成功，ID：",
                    user.id
                )


                # =============================
                # 註冊後自動登入
                # =============================

                login_user(
                    user
                )


                return redirect(
                    url_for("projects.index")
                )


    return render_template(

        "register.html",

        error=error

    )

# ============================================
# 使用者登入
# ============================================

@auth_bp.route(
    "/login",
    methods=["GET", "POST"]
)
@limiter.limit("5 per minute", methods=["POST"])
@limiter.limit("20 per hour", methods=["POST"])
def login():

    if current_user.is_authenticated:

        return redirect(
            url_for("projects.index")
        )


    error = None


    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()


        password = request.form.get(
            "password",
            ""
        )



        # 從 Database 找使用者

        user = (
            User.query
            .filter_by(
                email=email
            )
            .first()
        )


        # 驗證帳號與密碼

        if (
            user is None
            or not check_password_hash(
                user.password_hash,
                password
            )
        ):

            error = "Email 或密碼錯誤"


        else:

 
            # 登入成功

            login_user(
                user
            )

            print(
                "使用者登入成功，ID：",
                user.id
            )

            return redirect(
                url_for("projects.index")
            )


    return render_template(

        "login.html",

        error=error

    )


# 使用者登出

@auth_bp.route(
    "/logout",
    methods=["POST"]
)
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("auth.login")
    )
