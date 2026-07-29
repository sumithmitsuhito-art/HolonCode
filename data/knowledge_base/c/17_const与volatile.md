# 模块 17：const 与 volatile 类型限定符

## 一、const —— 只读

### 1. const 修饰指针
```c
const char *p1;      // 指向的数据不能改（可以 p1++，不能 *p1 = 'a'）
char *const p2 = &x; // 指针本身不能改（不能 p2 = q，但可以 *p2 = 5）
const char *const p3 = &x;  // 都不能改
```
> 读法：从变量名往左读
> - `const char *p` → p 指向 "const char"
> - `char *const p` → p 是 "const" 指针，指向 char

### 2. const 修饰函数参数（最佳实践）

```c
// 告诉调用者"我保证不会改你传进来的字符串"
size_t my_strlen(const char *s);

// 结构体传指针 + const：避免复制，又保证不写
void print_student(const struct Student *s);
```

### 3. const 是编译器层面的保护
可以通过指针强制转掉 const 来修改（但结果是未定义的，千万别写）：
```c
const int x = 10;
int *p = (int*)&x;
*p = 20;    // 未定义行为（真的常量可能被放到只读内存段，这里会崩溃）
```

## 二、volatile —— 易变的

告诉编译器：这个变量**可能随时改变**，不要做优化（比如缓存到寄存器、删去读写）。

常见场景：
1. 被**中断**或**另一线程**修改的全局变量
2. **内存映射硬件寄存器**（例如串口状态寄存器）

```c
volatile int stop_flag = 0;   // 中断服务函数会改它

void busy_wait(void) {
    while (!stop_flag) { }   // 如果不加 volatile，编译器可能优化成 while (1)
}
```

## 三、const volatile 同时出现

```c
const volatile int *clock_reg;
// const：代码不能写它（只读寄存器）
// volatile：编译器不能假设它不变，每次都重新读
```
