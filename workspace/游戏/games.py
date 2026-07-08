import random
import os
import time

# === 贪吃蛇 ===
def snake_game():
    w, h = 20, 15
    snake = [(w//2, h//2)]
    d = (1, 0)
    food = (random.randint(1,w-2), random.randint(1,h-2))
    while food in snake:
        food = (random.randint(1,w-2), random.randint(1,h-2))
    score = 0
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        head = (snake[0][0]+d[0], snake[0][1]+d[1])
        if head in snake or not (0 <= head[0] < w and 0 <= head[1] < h):
            print(f"Game Over! 得分: {score}")
            time.sleep(2)
            return
        snake.insert(0, head)
        if head == food:
            score += 10
            food = (random.randint(1,w-2), random.randint(1,h-2))
            while food in snake:
                food = (random.randint(1,w-2), random.randint(1,h-2))
        else:
            snake.pop()
        for y in range(h):
            row = ''
            for x in range(w):
                if (x,y) == snake[0]: row += 'O'
                elif (x,y) in snake: row += 'o'
                elif (x,y) == food: row += '*'
                else: row += '.'
            print(row)
        print(f"得分: {score} | WASD移动 | Q退出")
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            k = sys.stdin.read(1).lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if k == 'q': return
        if k == 'w' and d != (0,1): d = (0,-1)
        if k == 's' and d != (0,-1): d = (0,1)
        if k == 'a' and d != (1,0): d = (-1,0)
        if k == 'd' and d != (-1,0): d = (1,0)

# === 俄罗斯方块 ===
def tetris_game():
    w, h = 10, 20
    shapes = [
        [(0,0),(1,0),(0,1),(1,1)],  # O
        [(0,0),(0,1),(0,2),(0,3)],  # I
        [(0,0),(1,0),(2,0),(2,1)],  # L
        [(0,0),(1,0),(2,0),(0,1)],  # J
        [(0,0),(1,0),(1,1),(2,1)],  # S
        [(1,0),(2,0),(0,1),(1,1)],  # Z
        [(0,0),(1,0),(2,0),(1,1)],  # T
    ]
    board = [[0]*w for _ in range(h)]
    shape = random.choice(shapes)
    sx, sy = w//2-1, 0
    score = 0
    import sys, tty, termios, threading
    tick = [0]
    def timer():
        while True:
            time.sleep(0.5)
            tick[0] += 1
    threading.Thread(target=timer, daemon=True).start()
    last_tick = 0
    while True:
        if tick[0] > last_tick:
            last_tick = tick[0]
            if all(sy+dy+1 < h and board[sy+dy+1][sx+dx]==0 for dx,dy in shape):
                sy += 1
            else:
                for dx,dy in shape:
                    if sy+dy < h: board[sy+dy][sx+dx] = 1
                cleared = 0
                for y in range(h-1,-1,-1):
                    if all(board[y]):
                        del board[y]
                        board.insert(0, [0]*w)
                        cleared += 1
                score += cleared * cleared * 100
                shape = random.choice(shapes)
                sx, sy = w//2-1, 0
                if any(board[sy+dy][sx+dx] for dx,dy in shape):
                    print(f"Game Over! 得分: {score}")
                    time.sleep(2)
                    return
        os.system('cls' if os.name == 'nt' else 'clear')
        disp = [row[:] for row in board]
        for dx,dy in shape:
            if 0 <= sy+dy < h and 0 <= sx+dx < w:
                disp[sy+dy][sx+dx] = 2
        for row in disp:
            print(''.join('#' if c==1 else '[' if c==2 else '.' for c in row))
        print(f"得分: {score} | A/D移动 S加速 W旋转 Q退出")
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            k = sys.stdin.read(1).lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if k == 'q': return
        if k == 'a' and all(sx+dx-1>=0 and board[sy+dy][sx+dx-1]==0 for dx,dy in shape):
            sx -= 1
        if k == 'd' and all(sx+dx+1<w and board[sy+dy][sx+dx+1]==0 for dx,dy in shape):
            sx += 1
        if k == 's': last_tick = tick[0]

# === 打砖块 ===
def breakout_game():
    w, h = 30, 15
    px = w//2
    bx, by = w//2, h-3
    bdx, bdy = random.choice([(1,-1),(-1,-1)]), -1
    bricks = [[1]*10 for _ in range(4)]
    score = 0
    import sys, tty, termios
    while True:
        bx += bdx; by += bdy
        if bx <= 0 or bx >= w-1: bdx = -bdx
        if by <= 0: bdy = -bdy
        if by == h-2 and abs(bx-px) <= 2: bdy = -bdy
        if by >= h:
            print(f"Game Over! 得分: {score}")
            time.sleep(2)
            return
        if by < 4 and bricks[by][bx//3] == 1:
            bricks[by][bx//3] = 0
            bdy = -bdy
            score += 10
            if all(all(b==0 for b in row) for row in bricks):
                print(f"通关! 得分: {score}")
                time.sleep(2)
                return
        os.system('cls' if os.name == 'nt' else 'clear')
        for y in range(4):
            row = ''
            for x in range(10):
                row += '#'*3 if bricks[y][x] else ' '*3
            print(row)
        for y in range(4, h):
            row = ''
            for x in range(w):
                if (x,y) == (bx,by): row += 'O'
                elif y == h-2 and abs(x-px) <= 2: row += '='
                else: row += ' '
            print(row)
        print(f"得分: {score} | A/D移动挡板 | Q退出")
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            k = sys.stdin.read(1).lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if k == 'q': return
        if k == 'a': px = max(2, px-2)
        if k == 'd': px = min(w-3, px+2)

# === 主菜单 ===
def main():
    games = {'1':('贪吃蛇', snake_game), '2':('俄罗斯方块', tetris_game), '3':('打砖块', breakout_game)}
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=== 游戏大厅 ===\n")
        for k,(name,_) in games.items():
            print(f"  {k}. {name}")
        print("\n  Q. 退出")
        c = input('\n> ').strip().lower()
        if c == 'q': break
        if c in games:
            games[c][1]()

if __name__ == '__main__':
    main()
