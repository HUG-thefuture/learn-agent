# 生成器与 yield：让数据“按需生产”

## 1. 本课目标
- 理解生成器是什么，为什么它能节省内存。
- 学会用 `yield` 编写生成器函数，并用 `for` 循环或 `next()` 获取值。
- 能识别生成器的“一次性”特点，并会用生成器表达式简化代码。

## 2. 概念讲解

### 2.1 从“列表”到“按需生产”
假设你要处理 100 万条数据。如果用列表，会一次性把所有数据加载到内存，可能撑爆内存。生成器就像“流水线”：每次只生产一个数据，用完就丢，需要时再生产下一个。

比方：列表是一整箱苹果，生成器是一棵苹果树，你摘一个吃一个，树上还能继续长。

### 2.2 生成器函数：用 yield 代替 return
普通函数用 `return` 返回结果，函数就结束了。生成器函数用 `yield` 返回一个值，然后“暂停”，下次调用时从暂停处继续。

```python
def my_generator():
    print("开始")
    yield 1
    print("继续")
    yield 2
    print("结束")
```

调用 `my_generator()` 不会执行函数体，而是返回一个生成器对象。用 `next()` 或 `for` 循环才会执行。

### 2.3 生成器表达式：像列表推导式，但用圆括号
列表推导式：`[x*2 for x in range(5)]` 立即生成列表。  
生成器表达式：`(x*2 for x in range(5))` 返回生成器，按需计算。

### 2.4 为什么生成器只能迭代一次？
因为生成器内部保存了“执行到哪了”的状态。迭代完就到底了，再迭代就没有了。需要重新创建生成器对象。

## 3. 由浅入深的完整示例

### 示例1：最简单的生成器——倒计时
```python
def countdown(n):
    """生成从 n 到 1 的倒计时"""
    while n > 0:
        yield n
        n -= 1

# 使用 for 循环遍历生成器
for num in countdown(3):
    print(num)

# 预期输出：
# 3
# 2
# 1
```

### 示例2：生成器处理大文件（模拟）
```python
# 模拟一个大文件的内容（实际中可能是 open('big.txt')）
fake_file_lines = [
    "第一行：你好\n",
    "第二行：生成器\n",
    "第三行：节省内存\n",
    "第四行：结束\n"
]

def read_lines(lines):
    """逐行读取，每次只返回一行"""
    for line in lines:
        yield line.strip()  # 去掉换行符

# 使用生成器逐行处理
for line in read_lines(fake_file_lines):
    print(f"处理: {line}")

# 预期输出：
# 处理: 第一行：你好
# 处理: 第二行：生成器
# 处理: 第三行：节省内存
# 处理: 第四行：结束
```

### 示例3：无限斐波那契数列 + next() 手动获取
```python
def fibonacci():
    """无限生成斐波那契数列"""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

# 创建生成器对象
fib = fibonacci()

# 手动获取前 8 个
for _ in range(8):
    print(next(fib))

# 预期输出：
# 0
# 1
# 1
# 2
# 3
# 5
# 8
# 13
```

## 4. 常用函数/调用速查表

| 函数/语法 | 签名 | 用途 | 最小示例 |
|-----------|------|------|----------|
| `yield` | `yield value` | 在函数中返回值并暂停，使函数成为生成器 | `def g(): yield 1` |
| `next()` | `next(iterator[, default])` | 获取生成器的下一个值 | `next(g())` → `1` |
| `iter()` | `iter(obj)` | 获取可迭代对象的迭代器 | `it = iter([1,2])` |
| 生成器表达式 | `(expr for item in iterable)` | 创建生成器，按需计算 | `(x*2 for x in range(3))` |
| `for` 循环 | `for x in generator:` | 自动迭代生成器直到结束 | `for x in g(): print(x)` |
| `list()` | `list(generator)` | 将生成器所有值转为列表（消耗生成器） | `list(g())` → `[1]` |
| `send()` | `generator.send(value)` | 向生成器发送值，恢复执行并赋值给 yield 表达式 | `g.send(10)`（进阶） |

## 5. 新手易错点

### 易错点1：调用生成器函数得到的是生成器对象，不是结果
❌ **错误写法**
```python
def get_numbers():
    yield 1
    yield 2

result = get_numbers()
print(result)  # 期望打印 1，实际打印 <generator object ...>
# 运行输出：<generator object get_numbers at 0x...>
```
✅ **正确写法**
```python
def get_numbers():
    yield 1
    yield 2

gen = get_numbers()      # 得到生成器对象
print(next(gen))         # 1
print(next(gen))         # 2
# 预期输出：
# 1
# 2
```
**为什么错**：生成器函数调用后不会立即执行函数体，而是返回一个生成器对象。必须用 `next()` 或 `for` 循环来驱动它执行。

### 易错点2：生成器只能迭代一次
❌ **错误写法**
```python
def simple_gen():
    yield 1
    yield 2

g = simple_gen()
print(list(g))  # [1, 2]
print(list(g))  # [] 第二次为空
# 预期输出：
# [1, 2]
# []
```
✅ **正确写法**
```python
def simple_gen():
    yield 1
    yield 2

g = simple_gen()
print(list(g))  # [1, 2]

# 需要再次使用，重新创建生成器
g2 = simple_gen()
print(list(g2))  # [1, 2]
# 预期输出：
# [1, 2]
# [1, 2]
```
**为什么错**：生成器内部保存了迭代位置，迭代完就到底了。再次迭代不会重置，需要重新调用生成器函数创建新的生成器对象。

### 易错点3：在生成器函数中使用 return 会提前结束生成器
❌ **错误写法**
```python
def gen_with_return():
    yield 1
    return 99
    yield 2  # 永远不会执行

g = gen_with_return()
print(next(g))  # 1
print(next(g))  # 报错 StopIteration: 99
# 运行报错：StopIteration: 99
```
✅ **正确写法**
```python
def gen_without_return():
    yield 1
    yield 2

g = gen_without_return()
print(next(g))  # 1
print(next(g))  # 2
# 预期输出：
# 1
# 2
```
**为什么错**：在生成器函数中，`return` 会终止生成器，并触发 `StopIteration` 异常，返回值会作为异常的参数。如果只想结束生成器，用 `return` 不带值即可，但通常直接让函数自然结束。

### 易错点4：混淆生成器表达式和列表推导式
❌ **错误写法**
```python
# 想创建生成器，却用了方括号（列表推导式）
gen = [x * 2 for x in range(3)]
print(type(gen))  # <class 'list'>
print(gen)        # [0, 2, 4]
# 预期输出：
# <class 'list'>
# [0, 2, 4]
```
✅ **正确写法**
```python
# 用圆括号创建生成器表达式
gen = (x * 2 for x in range(3))
print(type(gen))  # <class 'generator'>
print(next(gen))  # 0
print(next(gen))  # 2
# 预期输出：
# <class 'generator'>
# 0
# 2
```
**为什么错**：列表推导式用 `[]`，会立即生成完整列表；生成器表达式用 `()`，返回生成器对象，按需计算，节省内存。

### 易错点5：yield 后面的代码在下次 next() 时才执行
❌ **错误写法**
```python
def gen():
    print("A")
    yield 1
    print("B")
    yield 2

g = gen()
print("创建生成器")
# 此时不会打印 A 和 B
# 预期输出：
# 创建生成器
```
✅ **正确写法**
```python
def gen():
    print("A")
    yield 1
    print("B")
    yield 2

g = gen()
print("创建生成器")
print(next(g))  # 打印 A，然后返回 1
print(next(g))  # 打印 B，然后返回 2
# 预期输出：
# 创建生成器
# A
# 1
# B
# 2
```
**为什么错**：生成器函数调用时只创建生成器对象，不执行函数体。只有调用 `next()` 或迭代时，才会执行到第一个 `yield`，然后暂停。下次 `next()` 从暂停处继续。

## 6. 本课小练习

### 练习1：生成平方数
- **目标**：掌握用 `yield` 编写生成器函数，生成 1 到 n 的平方。
- **引导步骤**：
  1. 定义一个生成器函数 `squares(n)`。
  2. 使用 `for` 循环从 1 到 n。
  3. 在循环中用 `yield` 返回当前数字的平方。
  4. 调用函数并用 `for` 循环打印结果。
- **起步代码**
```python
def squares(n):
    # TODO: 使用 for 循环和 yield 生成 1 到 n 的平方
    pass

# 测试：打印 1 到 5 的平方
for sq in squares(5):
    print(sq)
```
- **预期输出**：
```
1
4
9
16
25
```
- 参考答案：
<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
def squares(n):
    for i in range(1, n + 1):
        yield i * i

for sq in squares(5):
    print(sq)
```

</details>

### 练习2：用生成器表达式筛选偶数
- **目标**：学会用生成器表达式从可迭代对象中筛选数据。
- **引导步骤**：
  1. 有一个列表 `numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]`。
  2. 用生成器表达式筛选出偶数。
  3. 用 `for` 循环遍历生成器并打印。
- **起步代码**
```python
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# TODO: 用生成器表达式筛选偶数，赋值给 even_gen
even_gen = None  # 请替换为生成器表达式

# 遍历并打印
for num in even_gen:
    print(num)
```
- **预期输出**：
```
2
4
6
8
10
```
- 参考答案：
<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

even_gen = (x for x in numbers if x % 2 == 0)

for num in even_gen:
    print(num)
```

</details>

### 练习3：生成器实现倒计时并手动 next()
- **目标**：理解生成器的暂停与恢复，学会用 `next()` 手动获取值。
- **引导步骤**：
  1. 编写生成器函数 `countdown(n)`，从 n 倒数到 1，每次 `yield` 一个数字。
  2. 创建生成器对象 `c = countdown(3)`。
  3. 使用 `next(c)` 三次，分别打印结果。
  4. 第四次调用 `next(c)` 会怎样？可以尝试捕获 `StopIteration`。
- **起步代码**
```python
def countdown(n):
    # TODO: 使用 while 循环和 yield 实现倒计时
    pass

c = countdown(3)
print(next(c))  # 预期 3
print(next(c))  # 预期 2
print(next(c))  # 预期 1
# 第四次会抛出 StopIteration，这里不处理
```
- **预期输出**：
```
3
2
1
```
- 参考答案：
<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
def countdown(n):
    while n > 0:
        yield n
        n -= 1

c = countdown(3)
print(next(c))  # 3
print(next(c))  # 2
print(next(c))  # 1
```

</details>

## 7. 本课小结
- 生成器函数用 `yield` 返回值并暂停，调用时返回生成器对象，不会立即执行。
- 生成器按需生成数据，节省内存，适合处理大数据或无限序列。
- 生成器只能迭代一次，迭代完就耗尽，需要重新创建生成器对象。
- 生成器表达式用圆括号，列表推导式用方括号，前者按需计算，后者立即生成列表。
- 使用 `next()` 可以手动获取生成器的下一个值，迭代结束会抛出 `StopIteration` 异常。

下一课建议：尝试用生成器处理一个真实的大文件，比如逐行读取并统计单词数量，体会“按需生产”的优势。