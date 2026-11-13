# SQLite与SQLAlchemy数据库

## 1. 本课目标

学完本课，你将能够：

- **用SQLAlchemy定义数据模型**：用Python类描述数据库表结构，不再手写SQL建表语句
- **完成增删改查（CRUD）操作**：通过ORM方式对SQLite数据库进行数据管理
- **在FastAPI中集成数据库**：结合Depends实现依赖注入，构建完整的后端数据层

---

## 2. 概念讲解

### 2.1 为什么需要ORM？

想象你开了一家图书馆（数据库），以前你需要用"图书管理员语言"（SQL）来管理书籍：

```sql
INSERT INTO books(title, author) VALUES('三体', '刘慈欣');
```

现在有了ORM（对象关系映射），你可以直接用"日常语言"（Python）来操作：

```python
book = Book(title='三体', author='刘慈欣')
session.add(book)
```

**ORM就像翻译官**：它把Python对象自动翻译成SQL语句，让你专注于业务逻辑，不用记SQL语法。

### 2.2 SQLAlchemy的核心组件

SQLAlchemy由三部分组成：

| 组件 | 作用 | 类比 |
|------|------|------|
| **Engine** | 管理数据库连接 | 图书馆的入口大门 |
| **Session** | 执行操作的工作台 | 图书管理员的工作台 |
| **Model** | 定义表结构的类 | 图书的分类规则 |

### 2.3 工作流程

```
定义Model类 → 创建Engine → 创建Session → 用Python操作数据
```

整个过程就像：
1. 先设计好"图书登记表"的格式（Model）
2. 打开图书馆大门（Engine）
3. 坐在工作台前（Session）
4. 开始登记/查询图书（CRUD操作）

---

## 3. 完整示例

### 示例1：基础CRUD操作

```python
"""
SQLAlchemy基础操作演示
运行前需要安装：pip install sqlalchemy
"""
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. 创建数据库引擎（连接SQLite文件数据库）
engine = create_engine('sqlite:///demo.db', echo=True)

# 2. 创建基类（所有模型类的父类）
Base = declarative_base()

# 3. 定义User模型（对应users表）
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    age = Column(Integer)

# 4. 创建表（如果不存在）
Base.metadata.create_all(engine)

# 5. 创建会话
Session = sessionmaker(bind=engine)
session = Session()

# 6. 增：添加新用户
user1 = User(name='Alice', age=25)
user2 = User(name='Bob', age=30)
session.add_all([user1, user2])
session.commit()

# 7. 查：查询所有用户
users = session.query(User).all()
for u in users:
    print(f"ID: {u.id}, 姓名: {u.name}, 年龄: {u.age}")

# 8. 改：更新Alice的年龄
alice = session.query(User).filter_by(name='Alice').first()
alice.age = 26
session.commit()

# 9. 删：删除Bob
bob = session.query(User).filter_by(name='Bob').first()
session.delete(bob)
session.commit()

# 10. 验证结果
print("\n更新后的用户列表：")
for u in session.query(User).all():
    print(f"ID: {u.id}, 姓名: {u.name}, 年龄: {u.age}")

session.close()

# 预期输出：
# 新增用户：ID: 1, 姓名: Alice, 年龄: 25
# 新增用户：ID: 2, 姓名: Bob, 年龄: 30
# 更新后的用户列表：
# ID: 1, 姓名: Alice, 年龄: 26
```

### 示例2：查询进阶

```python
"""
SQLAlchemy查询操作进阶
"""
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///shop.db')
Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    price = Column(Integer)  # 价格以分为单位，避免浮点误差

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

# 添加测试数据
products = [
    Product(name='手机', price=299900),
    Product(name='电脑', price=599900),
    Product(name='耳机', price=29900),
    Product(name='键盘', price=19900),
]
session.add_all(products)
session.commit()

# 1. 条件查询：价格大于50000分的商品
expensive = session.query(Product).filter(Product.price > 50000).all()
print("价格>500元的产品：")
for p in expensive:
    print(f"  {p.name}: {p.price/100:.2f}元")

# 2. 排序查询：按价格降序
sorted_products = session.query(Product).order_by(Product.price.desc()).all()
print("\n按价格从高到低：")
for p in sorted_products:
    print(f"  {p.name}: {p.price/100:.2f}元")

# 3. 限制数量：只取前2个
top2 = session.query(Product).order_by(Product.price.desc()).limit(2).all()
print("\n最贵的2个产品：")
for p in top2:
    print(f"  {p.name}: {p.price/100:.2f}元")

# 4. 计数统计
count = session.query(Product).count()
print(f"\n产品总数：{count}")

session.close()

# 预期输出：
# 价格>500元的产品：
#   手机: 2999.00元
#   电脑: 5999.00元
# 按价格从高到低：
#   电脑: 5999.00元
#   手机: 2999.00元
#   耳机: 299.00元
#   键盘: 199.00元
# 最贵的2个产品：
#   电脑: 5999.00元
#   手机: 2999.00元
# 产品总数：4
```

### 示例3：FastAPI集成

```python
"""
FastAPI + SQLAlchemy 完整示例
运行前需要安装：pip install fastapi uvicorn sqlalchemy
启动方式：uvicorn main:app --reload
"""
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel

# 数据库配置
DATABASE_URL = "sqlite:///./fastapi_demo.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# 定义模型
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, index=True)

# 创建表
Base.metadata.create_all(bind=engine)

# Pydantic模型（用于请求/响应验证）
class UserCreate(BaseModel):
    name: str
    email: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    
    class Config:
        from_attributes = True

# 依赖注入函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 创建FastAPI应用
app = FastAPI()

# 创建用户
@app.post("/users/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(name=user.name, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# 查询所有用户
@app.get("/users/", response_model=list[UserResponse])
def read_users(db: Session = Depends(get_db)):
    return db.query(User).all()

# 查询单个用户
@app.get("/users/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user

# 删除用户
@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"message": "用户已删除"}

# 预期输出：启动后访问 http://127.0.0.1:8000/docs 查看API文档
```

---

## 4. 常用函数/调用速查表

| 函数/方法 | 签名 | 用途 | 最小示例 |
|-----------|------|------|----------|
| `create_engine` | `create_engine(url)` | 创建数据库引擎 | `engine = create_engine('sqlite:///test.db')` |
| `declarative_base` | `declarative_base()` | 创建模型基类 | `Base = declarative_base()` |
| `sessionmaker` | `sessionmaker(bind=engine)` | 创建会话工厂 | `Session = sessionmaker(bind=engine)` |
| `session.add` | `add(obj)` | 添加对象到会话 | `session.add(user)` |
| `session.add_all` | `add_all([obj1, obj2])` | 批量添加 | `session.add_all([u1, u2])` |
| `session.commit` | `commit()` | 提交事务 | `session.commit()` |
| `session.query` | `query(Model)` | 创建查询 | `session.query(User)` |
| `.filter()` | `filter(条件)` | 过滤结果 | `.filter(User.age > 18)` |
| `.filter_by()` | `filter_by(字段=值)` | 按字段过滤 | `.filter_by(name='Alice')` |
| `.all()` | `all()` | 获取所有结果 | `users = query.all()` |
| `.first()` | `first()` | 获取第一条 | `user = query.first()` |
| `.order_by()` | `order_by(字段)` | 排序 | `.order_by(User.age.desc())` |
| `.limit()` | `limit(n)` | 限制数量 | `.limit(10)` |
| `.count()` | `count()` | 统计数量 | `total = query.count()` |
| `session.delete` | `delete(obj)` | 删除对象 | `session.delete(user)` |
| `session.close` | `close()` | 关闭会话 | `session.close()` |

---

## 5. 新手易错点

### 易错点1：忘记调用commit()

❌ **错误写法**
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///test.db')
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# 错误：添加后没有commit()
user = User(name='Alice')
session.add(user)

# 验证数据是否保存
users = session.query(User).all()
print(f"用户数量: {len(users)}")
# 运行结果：用户数量: 0（数据没有真正保存到数据库）
```

✅ **正确写法**
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///test.db')
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# 正确：添加后必须commit()
user = User(name='Alice')
session.add(user)
session.commit()  # 关键步骤！

users = session.query(User).all()
print(f"用户数量: {len(users)}")
# 预期输出：用户数量: 1
```

**为什么错**：`session.add()`只是把对象加入会话，相当于"暂存区"，只有`commit()`才会真正写入数据库。

---

### 易错点2：查询结果为空时直接访问属性

❌ **错误写法**
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///test.db')
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# 查询不存在的用户
user = session.query(User).filter_by(name='不存在的人').first()
print(user.name)  # 运行报错：AttributeError: 'NoneType' object has no attribute 'name'
```

✅ **正确写法**
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///test.db')
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# 先判断是否为空
user = session.query(User).filter_by(name='不存在的人').first()
if user:
    print(user.name)
else:
    print("用户不存在")
# 预期输出：用户不存在
```

**为什么错**：`first()`在无结果时返回`None`，直接访问`None`的属性会报错。

---

### 易错点3：主键字段类型不匹配

❌ **错误写法**
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///test.db')
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)  # 主键是Integer
    name = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# 错误：给主键传字符串
user = User(id='abc', name='Alice')
session.add(user)
session.commit()  # 运行报错：sqlalchemy.exc.StatementError
```

✅ **正确写法**
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///test.db')
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)  # 主键是Integer
    name = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# 正确：不指定id，让数据库自动生成
user = User(name='Alice')
session.add(user)
session.commit()

print(f"用户ID: {user.id}")
# 预期输出：用户ID: 1
```

**为什么错**：SQLite的INTEGER主键会自动递增，手动传字符串类型不匹配。

---

### 易错点4：会话未关闭导致连接泄漏

❌ **错误写法**
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///test.db')
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# 错误：创建会话后忘记关闭
session = Session()
user = User(name='Alice')
session.add(user)
session.commit()
# 没有session.close()，连接一直占用
```

✅ **正确写法**
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///test.db')
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# 正确：使用with语句自动关闭
with Session() as session:
    user = User(name='Alice')
    session.add(user)
    session.commit()
    print(f"用户ID: {user.id}")
# 预期输出：用户ID: 1
```

**为什么错**：不关闭会话会占用数据库连接资源，在FastAPI中尤其要注意使用`Depends`自动管理。

---

### 易错点5：模型字段与数据库列不匹配

❌ **错误写法**
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///test.db')
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    # 错误：忘记定义email字段

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# 尝试添加email数据
user = User(name='Alice', email='alice@example.com')  # 运行报错：TypeError
```

✅ **正确写法**
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///test.db')
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)  # 正确：定义所有需要的字段

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

user = User(name='Alice', email='alice@example.com')
session.add(user)
session.commit()
print(f"用户: {user.name}, 邮箱: {user.email}")
# 预期输出：用户: Alice, 邮箱: alice@example.com
```

**为什么错**：模型类必须包含所有要使用的字段，否则传参时会报TypeError。

---

## 6. 本课小练习

### 练习1：创建图书模型

- **目标**：掌握定义模型类和创建表的基本流程
- **引导步骤**：
  1. 定义`Book`类，包含`id`（主键）、`title`（书名）、`author`（作者）、`price`（价格）字段
  2. 创建SQLite数据库引擎
  3. 创建表并添加一本测试图书
  4. 查询并打印所有图书

- **起步代码**：
```python
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

# TODO: 创建引擎
engine = create_engine('sqlite:///books.db')
Base = declarative_base()

# TODO: 定义Book模型类
class Book(Base):
    __tablename__ = 'books'
    # TODO: 定义字段
    pass

# TODO: 创建表
# TODO: 创建会话
# TODO: 添加一本图书并提交
# TODO: 查询所有图书并打印
```

- **预期输出**：
```
图书列表：
ID: 1, 书名: 三体, 作者: 刘慈欣, 价格: 59.0
```

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///books.db')
Base = declarative_base()

class Book(Base):
    __tablename__ = 'books'
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    author = Column(String(50))
    price = Column(Float)

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

book = Book(title='三体', author='刘慈欣', price=59.0)
session.add(book)
session.commit()

print("图书列表：")
for b in session.query(Book).all():
    print(f"ID: {b.id}, 书名: {b.title}, 作者: {b.author}, 价格: {b.price}")

session.close()
```

</details>

---

### 练习2：条件查询与排序

- **目标**：掌握filter和order_by的使用
- **引导步骤**：
  1. 创建`Student`模型（id, name, score）
  2. 添加3个学生数据
  3. 查询成绩大于80分的学生
  4. 按成绩从高到低排序显示

- **起步代码**：
```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///students.db')
Base = declarative_base()

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    score = Column(Integer)

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

# 添加测试数据
students = [
    Student(name='小明', score=85),
    Student(name='小红', score=92),
    Student(name='小刚', score=78),
]
session.add_all(students)
session.commit()

# TODO: 查询成绩大于80分的学生
# TODO: 按成绩降序排列所有学生
# TODO: 打印结果

session.close()
```

- **预期输出**：
```
成绩>80分的学生：
  小红: 92分
  小明: 85分

按成绩从高到低：
  小红: 92分
  小明: 85分
  小刚: 78分
```

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///students.db')
Base = declarative_base()

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    score = Column(Integer)

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

students = [
    Student(name='小明', score=85),
    Student(name='小红', score=92),
    Student(name='小刚', score=78),
]
session.add_all(students)
session.commit()

# 查询成绩大于80分的学生
high_scores = session.query(Student).filter(Student.score > 80).all()
print("成绩>80分的学生：")
for s in high_scores:
    print(f"  {s.name}: {s.score}分")

# 按成绩降序排列
sorted_students = session.query(Student).order_by(Student.score.desc()).all()
print("\n按成绩从高到低：")
for s in sorted_students:
    print(f"  {s.name}: {s.score}分")

session.close()
```

</details>

---

### 练习3：FastAPI集成数据库

- **目标**：掌握在FastAPI中使用Depends管理数据库会话
- **引导步骤**：
  1. 定义`Item`模型（id, name, quantity）
  2. 创建`get_db`依赖函数
  3. 实现创建和查询物品的API接口
  4. 使用Pydantic模型进行数据验证

- **起步代码**：
```python
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel

# 数据库配置
DATABASE_URL = "sqlite:///./items.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# TODO: 定义Item模型
class Item(Base):
    __tablename__ = "items"
    # TODO: 定义字段

Base.metadata.create_all(bind=engine)

# Pydantic模型
class ItemCreate(BaseModel):
    name: str
    quantity: int

class ItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    
    class Config:
        from_attributes = True

# TODO: 创建get_db依赖函数

app = FastAPI()

# TODO: 实现创建物品的接口
# TODO: 实现查询所有物品的接口
```

- **预期输出**：启动后访问`http://127.0.0.1:8000/docs`，可以测试API接口

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel

DATABASE_URL = "sqlite:///./items.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    quantity = Column(Integer, default=0)

Base.metadata.create_all(bind=engine)

class ItemCreate(BaseModel):
    name: str
    quantity: int

class ItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    
    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

@app.post("/items/", response_model=ItemResponse)
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    db_item = Item(name=item.name, quantity=item.quantity)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.get("/items/", response_model=list[ItemResponse])
def read_items(db: Session = Depends(get_db)):
    return db.query(Item).all()
```

</details>

---

## 7. 本课小结

恭喜你完成了SQLAlchemy数据库的学习！现在你已经掌握了：

- ✅ **ORM核心概念**：用Python类描述数据库表，告别手写SQL
- ✅ **CRUD操作**：增删改查的完整流程
- ✅ **查询进阶**：条件过滤、排序、限制数量
- ✅ **FastAPI集成**：使用Depends自动管理数据库会话

**下一课预告**：我们将学习**用户认证与JWT**，为你的API加上安全防护，让只有登录用户才能访问特定接口。这将是你构建完整后端服务的重要一步！