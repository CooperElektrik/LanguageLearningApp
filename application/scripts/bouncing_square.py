import pyglet

window = pyglet.window.Window(width=800, height=600, caption='Bouncing Square')
square = pyglet.shapes.Rectangle(x=50, y=50, width=50, height=50, color=(255, 0, 0))

dx = 100  # pixels per second
dy = 100  # pixels per second

@window.event
def on_draw():
    window.clear()
    square.draw()

def update(dt):
    global dx, dy
    square.x += dx * dt
    square.y += dy * dt

    if square.x + square.width > window.width or square.x < 0:
        dx *= -1
    if square.y + square.height > window.height or square.y < 0:
        dy *= -1

pyglet.clock.schedule_interval(update, 1/60.0)
pyglet.app.run()