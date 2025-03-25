import sys
import sdl2.ext

# Define resources path
RESOURCES = sdl2.ext.Resources(__file__, "resources")

# Initialize SDL2
sdl2.ext.init()

# Create window
window = sdl2.ext.Window("Hello World!", size=(640, 480))
window.show()

# Create sprite factory and load image
factory = sdl2.ext.SpriteFactory(sdl2.ext.SOFTWARE)
sprite = factory.from_image(RESOURCES.get_path("hello.bmp"))

# Create sprite renderer and render the sprite
spriterenderer = factory.create_sprite_render_system(window)
spriterenderer.render(sprite)

# Process events to keep window open
processor = sdl2.ext.TestEventProcessor()
processor.run(window)

# Clean up
sdl2.ext.quit()