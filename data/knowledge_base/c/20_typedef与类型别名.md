# 模块 20：typedef 与类型别名

## 一、typedef 基本用法

`typedef` 给已存在的类型起别名，不创建新类型。

```c
typedef unsigned int uint;
uint a, b;   // 等价 unsigned int a, b

// 简化结构体
struct Tag { int x; };
typedef struct { int x; } Point;   // 最常见写法：同时声明 + typedef

Point p1;    // 不再需要 struct 关键字
```

## 二、typedef 与指针

```c
typedef char *cstring;
cstring p1, p2;   // 都是 char *（和 #define 不同！）

// 如果写成宏：
#define CSTRING char *
CSTRING p3, p4;   // 展开为 char *p3, p4; → p4 是 char！（陷阱）
```

## 三、typedef 与函数指针

```c
// 原写法（丑）
int (*my_fp_t)(int, double);

// typedef 一下
typedef int (*Handler)(int, double);
Handler on_click;    // 声明一个函数指针变量，和 Handler f1, f2, f3
```

## 四、typedef 与数组

```c
typedef int vec3[3];   // vec3 是"3 个 int 的数组"类型
vec3 pos = {1, 2, 3};
```

## 五、typedef vs #define

| 特性 | typedef | #define |
|------|---------|---------|
| 处理阶段 | 编译 | 预处理（文本替换） |
| 作用域 | 有作用域（函数内可） | 全局，直到 #undef |
| 指针声明 | `typedef char *S; S a,b;` 两个都是指针 | `#define S char *; S a,b;` → 只有 a 是指针 |

## 六、最佳实践

- 复杂类型（函数指针、数组指针）永远用 typedef 简化
- 跨平台代码用 typedef 抽象类型（如 `typedef long long i64;`）
