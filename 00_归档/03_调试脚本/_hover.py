import ctypes, sys, time
x, y = int(sys.argv[1]), int(sys.argv[2])
u = ctypes.windll.user32
u.SetCursorPos(x, y)
time.sleep(1.6)
print('HOVER', x, y)
