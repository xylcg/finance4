# finance3/finance_app1/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FloatField, SelectField, DateField, FileField
from wtforms.validators import DataRequired, Email, EqualTo, Length

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