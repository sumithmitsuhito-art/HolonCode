import random
import os

class Maze:
    def __init__(self, w=15, h=10):
        self.w, self.h = w, h
        self.grid = [['#' for _ in range(w)] for _ in range(h)]
        self.px, self.py = 1, 1
        self.ex, self.ey = w-2, h-2
        self._gen()

    def _gen(self):
        stack, visited = [(1,1)], {(1,1)}
        dirs = [(2,0),(-2,0),(0,2),(0,-2)]
        while stack:
            cx, cy = stack[-1]
            random.shuffle(dirs)
            moved = False
            for dx, dy in dirs:
                nx, ny = cx+dx, cy+dy
                mx, my = cx+dx//2, cy+dy//2
                if 0 < nx < self.w-1 and 0 < ny < self.h-1 and (nx,ny) not in visited:
                    visited.add((nx,ny))
                    self.grid[my][mx] = self.grid[ny][nx] = ' '
                    stack.append((nx,ny))
                    moved = True
                    break
            if not moved:
                stack.pop()
        self.grid[1][1] = 'P'
        self.grid[self.ey][self.ex] = 'E'

    def show(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        for row in self.grid:
            print(' '.join(row))
        print("\nWASD移动 | Q退出 | 走到E获胜")

    def move(self, d):
        dx, dy = {'w':(0,-1),'s':(0,1),'a':(-1,0),'d':(1,0)}.get(d, (0,0))
        nx, ny = self.px+dx, self.py+dy
        cell = self.grid[ny][nx] if 0 <= nx < self.w and 0 <= ny < self.h else '#'
        if cell != '#':
            self.grid[self.py][self.px] = ' '
            self.px, self.py = nx, ny
            if (nx, ny) == (self.ex, self.ey):
                self.grid[ny][nx] = 'P'
                self.show()
                return 'win'
            self.grid[ny][nx] = 'P'
        return None

if __name__ == '__main__':
    m = Maze()
    while True:
        m.show()
        k = input('> ').strip().lower()
        if k == 'q': break
        if m.move(k) == 'win':
            print('过关.')
            break
