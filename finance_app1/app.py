from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_mail import Mail
from flask_migrate import Migrate
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FloatField, SelectField, DateField, FileField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from datetime import datetime
import os


# 表单类
class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    remember_me = BooleanField('记住我')
    submit = SubmitField('登录')


class RegistrationForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('邮箱', validators=[DataRequired(), Email()])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('注册')


class TransactionForm(FlaskForm):
    amount = FloatField('金额', validators=[DataRequired()])
    description = StringField('描述')
    type = SelectField('类型', choices=[('income', '收入'), ('expense', '支出')])
    category = SelectField('分类')
    date = DateField('日期', validators=[DataRequired()], format='%Y-%m-%d')
    goal = SelectField('目标', coerce=int, choices=[])
    submit = SubmitField('保存')


class BudgetForm(FlaskForm):
    name = StringField('名称', validators=[DataRequired()])
    amount = FloatField('金额', validators=[DataRequired()])
    category = SelectField('分类')
    period = SelectField('周期', choices=[('月度', '月度'), ('季度', '季度'), ('年度', '年度')])
    start_date = DateField('开始日期', validators=[DataRequired()], format='%Y-%m-%d')
    end_date = DateField('结束日期', validators=[DataRequired()], format='%Y-%m-%d')
    submit = SubmitField('保存')


class GoalForm(FlaskForm):
    name = StringField('名称', validators=[DataRequired()])
    target_amount = FloatField('目标金额', validators=[DataRequired()])
    current_amount = FloatField('当前金额', default=0)
    target_date = DateField('目标日期', validators=[DataRequired()], format='%Y-%m-%d')
    submit = SubmitField('保存')


class ProfileForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('邮箱', validators=[DataRequired(), Email()])
    avatar = FileField('头像')
    submit = SubmitField('更新资料')


# 数据库模型
db = SQLAlchemy()


class User(db.Model, UserMixin):
    """用户模型"""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    avatar = db.Column(db.String(128))  # 头像路径

    # 关系定义
    transactions = db.relationship('Transaction', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    budgets = db.relationship('Budget', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    goals = db.relationship('Goal', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    favorites = db.relationship('Knowledge', secondary='user_knowledge', backref=db.backref('users', lazy='dynamic'))

    def set_password(self, password):
        """设置密码哈希"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


# 用户收藏知识的关联表
user_knowledge = db.Table('user_knowledge',
                          db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
                          db.Column('knowledge_id', db.Integer, db.ForeignKey('knowledge.id'), primary_key=True)
                          )


class Transaction(db.Model):
    """交易记录模型"""
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    type = db.Column(db.String(10), nullable=False)  # 收入/支出
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, index=True, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f'<Transaction {self.amount} {self.type}>'


class Budget(db.Model):
    """预算模型"""
    __tablename__ = 'budgets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))
    period = db.Column(db.String(20), nullable=False)  # 月度/季度/年度
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def spent_amount(self):
        """计算已花费金额"""
        from sqlalchemy import func
        return db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == self.user_id,
            Transaction.type == 'expense',
            Transaction.category == self.category,
            Transaction.date >= self.start_date,
            Transaction.date <= self.end_date
        ).scalar() or 0

    def remaining_amount(self):
        """计算剩余金额"""
        return self.amount - self.spent_amount()

    def __repr__(self):
        return f'<Budget {self.name} {self.amount}>'


class Goal(db.Model):
    """财务目标模型"""
    __tablename__ = 'goals'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0)
    target_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def progress(self):
        """计算目标进度百分比"""
        return (self.current_amount / self.target_amount) * 100 if self.target_amount > 0 else 0

    def days_remaining(self):
        """计算剩余天数"""
        return (self.target_date - datetime.utcnow()).days

    def __repr__(self):
        return f'<Goal {self.name} {self.progress()}%>'


class Knowledge(db.Model):
    """理财知识模型"""
    __tablename__ = 'knowledge'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    image = db.Column(db.String(128))  # 知识图片路径

    def __repr__(self):
        return f'<Knowledge {self.title}>'


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化扩展
    db.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = 'login'
    mail = Mail(app)
    migrate = Migrate(app, db)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    # 错误处理
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500

    # 上下文处理器 - 使变量在所有模板中可用
    @app.context_processor
    def inject_vars():
        return dict(
            categories=app.config['CATEGORIES'],
            budget_periods=app.config['BUDGET_PERIODS'],
            app_name=app.config['APP_NAME']
        )

    # 辅助函数
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

    # 认证路由
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user is None or not user.check_password(form.password.data):
                flash('无效的用户名或密码', 'danger')
                return redirect(url_for('login'))
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        return render_template('auth/login.html', form=form)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = RegistrationForm()
        if form.validate_on_submit():
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
        return render_template('auth/register.html', form=form)

    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('index'))

    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        form = ProfileForm(obj=current_user)
        if form.validate_on_submit():
            current_user.username = form.username.data
            current_user.email = form.email.data

            # 处理头像上传
            if form.avatar.data:
                file = form.avatar.data
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    current_user.avatar = filename

            db.session.commit()
            flash('个人资料已更新', 'success')
            return redirect(url_for('profile'))
        return render_template('auth/profile.html', form=form)

    # 主路由
    @app.route('/')
    @login_required
    def index():
        # 最近交易
        recent_transactions = Transaction.query.filter_by(user_id=current_user.id) \
            .order_by(Transaction.date.desc()).limit(5).all()

        # 预算摘要
        active_budgets = Budget.query.filter(
            Budget.user_id == current_user.id,
            Budget.start_date <= datetime.utcnow(),
            Budget.end_date >= datetime.utcnow()
        ).all()

        # 目标进度
        active_goals = Goal.query.filter(
            Goal.user_id == current_user.id,
            Goal.target_date >= datetime.utcnow()
        ).all()

        # 推荐理财知识
        recommended_knowledge = Knowledge.query.order_by(func.random()).limit(3).all()

        return render_template('index.html',
                               recent_transactions=recent_transactions,
                               active_budgets=active_budgets,
                               active_goals=active_goals,
                               recommended_knowledge=recommended_knowledge)

    # 交易路由
    @app.route('/transactions')
    @login_required
    def transactions():
        page = request.args.get('page', 1, type=int)
        type_filter = request.args.get('type')
        category_filter = request.args.get('category')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = Transaction.query.filter_by(user_id=current_user.id)

        # 应用过滤器
        if type_filter:
            query = query.filter_by(type=type_filter)
        if category_filter:
            query = query.filter_by(category=category_filter)
        if start_date:
            query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d'))

        transactions = query.order_by(Transaction.date.desc()) \
            .paginate(page=page, per_page=app.config['ITEMS_PER_PAGE'])

        return render_template('transactions/list.html', transactions=transactions)

    @app.route('/transactions/add', methods=['GET', 'POST'])
    @login_required
    def add_transaction():
        form = TransactionForm()
        form.goal.choices = [(g.id, g.name) for g in Goal.query.filter_by(user_id=current_user.id).all()]

        if form.validate_on_submit():
            transaction = Transaction(
                amount=form.amount.data,
                description=form.description.data,
                type=form.type.data,
                category=form.category.data,
                date=datetime.strptime(form.date.data, '%Y-%m-%d'),
                user_id=current_user.id
            )
            db.session.add(transaction)

            # 更新目标进度
            if form.goal.data:
                goal = Goal.query.get(form.goal.data)
                if goal and goal.user_id == current_user.id:
                    if form.type.data == 'income':
                        goal.current_amount += form.amount.data
                    else:
                        goal.current_amount -= form.amount.data
                    db.session.add(goal)

            db.session.commit()
            flash('交易已添加', 'success')
            return redirect(url_for('transactions'))
        return render_template('transactions/add_edit.html', form=form, title='添加交易')

    @app.route('/transactions/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_transaction(id):
        transaction = Transaction.query.get_or_404(id)
        if transaction.user_id != current_user.id:
            abort(403)

        form = TransactionForm(obj=transaction)
        form.goal.choices = [(g.id, g.name) for g in Goal.query.filter_by(user_id=current_user.id).all()]

        if form.validate_on_submit():
            transaction.amount = form.amount.data
            transaction.description = form.description.data
            transaction.type = form.type.data
            transaction.category = form.category.data
            transaction.date = datetime.strptime(form.date.data, '%Y-%m-%d')

            # 这里可以添加目标更新逻辑

            db.session.commit()
            flash('交易已更新', 'success')
            return redirect(url_for('transactions'))
        return render_template('transactions/add_edit.html', form=form, title='编辑交易')

    @app.route('/transactions/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_transaction(id):
        transaction = Transaction.query.get_or_404(id)
        if transaction.user_id != current_user.id:
            abort(403)

        db.session.delete(transaction)
        db.session.commit()
        flash('交易已删除', 'success')
        return redirect(url_for('transactions'))

    # 预算路由
    @app.route('/budgets')
    @login_required
    def budgets():
        budgets = Budget.query.filter_by(user_id=current_user.id) \
            .order_by(Budget.start_date.desc()).all()
        return render_template('budgets/list.html', budgets=budgets)

    @app.route('/budgets/add', methods=['GET', 'POST'])
    @login_required
    def add_budget():
        form = BudgetForm()
        if form.validate_on_submit():
            budget = Budget(
                name=form.name.data,
                amount=form.amount.data,
                category=form.category.data,
                period=form.period.data,
                start_date=datetime.strptime(form.start_date.data, '%Y-%m-%d'),
                end_date=datetime.strptime(form.end_date.data, '%Y-%m-%d'),
                user_id=current_user.id
            )
            db.session.add(budget)
            db.session.commit()
            flash('预算已添加', 'success')
            return redirect(url_for('budgets'))
        return render_template('budgets/add_edit.html', form=form, title='添加预算')

    # 目标路由
    @app.route('/goals')
    @login_required
    def goals():
        goals = Goal.query.filter_by(user_id=current_user.id) \
            .order_by(Goal.target_date.asc()).all()
        return render_template('goals/list.html', goals=goals)

    @app.route('/goals/add', methods=['GET', 'POST'])
    @login_required
    def add_goal():
        form = GoalForm()
        if form.validate_on_submit():
            goal = Goal(
                name=form.name.data,
                target_amount=form.target_amount.data,
                current_amount=form.current_amount.data,
                target_date=datetime.strptime(form.target_date.data, '%Y-%m-%d'),
                user_id=current_user.id
            )
            db.session.add(goal)
            db.session.commit()
            flash('目标已添加', 'success')
            return redirect(url_for('goals'))
        return render_template('goals/add_edit.html', form=form, title='添加目标')

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()  # 创建数据库表
    app.run(debug=True)