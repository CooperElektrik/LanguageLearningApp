import pyglet
import random

window = pyglet.window.Window(width=600, height=600, caption='Interactive Circle')
circle = pyglet.shapes.Circle(x=300, y=300, radius=50, color=(255, 255, 0))

@window.event
def on_draw():
    window.clear()
    circle.draw()

@window.event
def on_mouse_press(x, y, button, modifiers):
    if button == pyglet.window.mouse.LEFT:
        # Check if click is within the circle
        distance = ((x - circle.x)**2 + (y - circle.y)**2)**0.5
        if distance <= circle.radius:
            circle.color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

pyglet.app.run()