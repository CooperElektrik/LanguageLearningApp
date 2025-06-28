import pyglet

window = pyglet.window.Window(800, 600, caption='Hello Pyglet!')

@window.event
def on_draw():
    window.clear()
    label.draw()

label = pyglet.text.Label('Hello, Pyglet!',
                          font_name='Times New Roman',
                          font_size=36,
                          x=window.width//2, y=window.height//2,
                          anchor_x='center', anchor_y='center')

pyglet.app.run()