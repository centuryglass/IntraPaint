#TODO: It would probably be better to find a way to embed this interface directly in the brushlib library
#TODO: Singleton design inherited from qtMypaint means that only one surface can exist. Either fix the C++ QT
#      interface, or implement a system to dynamically load and unload content.
import os, sys
from threading import Lock
from brushlib import MPHandler, MPTile
from PyQt5.QtCore import QByteArray


class Brushlib():
    _addedToScene = False
    _scale = 1.0
    _x = 0.0
    _y = 0.0

    def setScale(scene, scale):
        if scale != Brushlib._scale:
            lastScale = Brushlib._scale
            Brushlib._scale = scale
            for item in scene.items():
                if isinstance(item, MPTile):
                    item.setScale(scale)
                    item.setX(item.x() * scale)
                    item.setY(item.y() * scale)

    def setX(scene, x):
        if x != Brushlib._x:
            offset = Brushlib._scale * (x - Brushlib._x)
            Brushlib._x = x
            for item in scene.items():
                if isinstance(item, MPTile):
                    item.setX(item.x() + offset)

    def setY(scene, y):
        if y != Brushlib._y:
            offset = y - Brushlib._y
            Brushlib._y = y
            for item in scene.items():
                if isinstance(item, MPTile):
                    item.setY(item.y() + offset)

    def addToScene(scene):
        if Brushlib._addedToScene:
            raise Exception("Brushlib can only be added to a scene once (for now)")
        Brushlib.loadBrush("./resources/brush.myb")
        Brushlib._addedToScene = True
        zValue = 0
        for item in scene.items():
            zValue = max(zValue, item.zValue())

        def onNewTile(surface, tile):
            tile.setZValue(zValue)
            #tile.setScale(Brushlib._scale)
            #tile.setX((Brushlib._x + tile.x()) * Brushlib._scale)
            #tile.setY((Brushlib._y + tile.y()) * Brushlib._scale)
            #print(f"tile {len(scene.items())}: x= {tile.x()}, y={tile.y()}, scale={tile.scale()}")
            scene.addItem(tile)
        MPHandler.handler().newTile.connect(onNewTile)

        def onUpdateTile(surface, tile):
            tile.update()
        MPHandler.handler().newTile.connect(onUpdateTile)

    def setSurfaceSize(size):
        MPHandler.handler().setSurfaceSize(size)

    def surfaceSize():
        return MPHandler.handler().surfaceSize()

    def loadBrush(brushpath):
        with open(brushpath, 'rb') as file:
            data = file.read()
            qbytes = QByteArray(data)
            MPHandler.handler().loadBrush(qbytes)

    def setBrushColor(color):
        MPHandler.handler().setBrushColor(color)

    def loadImage(image):
        MPHandler.handler().loadImage(image)

    def renderImage():
        return MPHandler.handler().renderImage(image)

    def clearSurface():
        MPHandler.handler().clearSurface()

    def startStroke():
        MPHandler.handler().startStroke()

    def endStroke():
        MPHandler.handler().endStroke()

    def strokeTo(x, y):
        MPHandler.handler().strokeTo(x, y)

    def strokeTo(x, y, pressure, xtilt, ytilt):
        MPHandler.handler().strokeTo(x, y, pressure, xtilt, ytilt)

    # Brush setting functions, descriptions copied from libmypaint brushsettings-gen.h
    # TODO: Fix enum issues in the sip bindings so we don't need to use hard-coded ints as enum values.
    # TODO: Use proper docstrings


    def _getBrushValue(setting):
        return MPHandler.handler().getBrushValue(setting)

    def _setBrushValue(setting, value):
        MPHandler.handler().setBrushValue(setting, value)


    # 0: Opacity: 0 means brush is transparent, 1 fully visible
    def opacity():
        return Brushlib._getBrushValue(0)

    def set_opacity(value):
        Brushlib._setBrushValue(0, value)

    # 1: Opacity multiply: 0.0 - 2.0, default 1.0
    #     This gets multiplied with opaque. You should only change the
    #    pressure input of this setting. Use 'opaque' instead to make opacity
    #    depend on speed. This setting is responsible to stop painting when
    #    there is zero pressure. This is just a convention, the behaviour is
    #    identical to 'opaque'.
    def opacity_multiply():
        return Brushlib._getBrushValue(1)

    def set_opacity_multiply(value):
        Brushlib._setBrushValue(1, value)


    # 2: Opacity linearize: 0.0 - 2.0, default 0.9
    #     Correct the nonlinearity introduced by blending multiple dabs on top
    #    of each other. This correction should get you a linear (\"natural\")
    #    pressure response when pressure is mapped to opaque_multiply, as it
    #    is usually done. 0.9 is good for standard strokes, set it smaller if
    #    your brush scatters a lot, or higher if you use dabs_per_second.
    #    0.0: the opaque value above is for the individual dabs
    #    1.0: the opaque value above is for the final brush stroke, assuming
    #         each pixel gets (dabs_per_radius*2) brushdabs on average during
    #         a stroke
    def opacity_linearize():
        return Brushlib._getBrushValue(2)

    def set_opacity_linearize(value):
        Brushlib._setBrushValue(2, value)

    # 3: Radius: -2.0 - 6.0, default 2.0
    #    Basic brush radius (logarithmic)
    #     0.7 means 2 pixels
    #     3.0 means 20 pixels
    def radius():
        return Brushlib._getBrushValue(3)

    def set_radius(value):
        Brushlib._setBrushValue(3, value)

    # 4: Hardness:  0.0 - 1.0, default 0.8
    #     Hard brush-circle borders (setting to zero will draw nothing). To
    #     reach the maximum hardness, you need to disable Pixel feather.
    def hardness():
        return Brushlib._getBrushValue(4)

    def set_hardness(value):
        Brushlib._setBrushValue(4, value)

    # 5: Pixel feather: 0.0 - 5.0, default 1.0
    #     This setting decreases the hardness when necessary to prevent a
    #    pixel staircase effect (aliasing) by making the dab more blurred.
    #    0.0: disable (for very strong erasers and pixel brushes)
    #    1.0: blur one pixel (good value)
    #    5.0: notable blur, thin strokes will disappear
    def pixel_feather():
        return Brushlib._getBrushValue(5)

    def set_pixel_feather(value):
        Brushlib._setBrushValue(5, value)

    # 6: Dabs per basic radius: 0.0 - 6.0, default 0.0
    #     How many dabs to draw while the pointer moves a distance of one
    #    brush radius (more precise: the base value of the radius)
    def dabs_per_basic_radius():
        return Brushlib._getBrushValue(6)

    def set_dabs_per_basic_radius(value):
        Brushlib._setBrushValue(6, value)

    # 7: Dabs per actual radius: 0.0 - 6.0, default 2.0
    #    Same as above, but the radius actually drawn is used, which can
    #    change dynamically. 
    def dabs_per_actual_radius():
        return Brushlib._getBrushValue(7)

    def set_dabs_per_actual_radius(value):
        Brushlib._setBrushValue(7, value)

    # 8: Dabs per second: 0.0 - 80.0, default 0.0
    #    Dabs to draw each second, no matter how far the pointer moves
    def dabs_per_second():
        return Brushlib._getBrushValue(8)

    def set_dabs_per_second(value):
        Brushlib._setBrushValue(8, value)

    # 9: Radius by random: 0.0 - 1.5, default 0.0
    #     Alter the radius randomly each dab. You can also do this with the
    #    by_random input on the radius setting. If you do it here, there are
    #    two differences:
    #    1) the opaque value will be corrected such that a big-radius dabs is
    #       more transparent
    #    2) it will not change the actual radius seen by dabs_per_actual_radius
    def radius_by_random():
        return Brushlib._getBrushValue(9)

    def set_radius_by_random(value):
        Brushlib._setBrushValue(9, value)

    # 10: Fine speed filter: 0.0 - 0.2, default 0.04
    #      How slow the input fine speed is following the real speed. 0.0
    #      change immediately as your speed changes (not recommended)
    def fine_speed_filter():
        return Brushlib._getBrushValue(10)

    def set_fine_speed_filter(value):
        Brushlib._setBrushValue(10, value)

    # 11: Gross speed filter:  0.0 - 3.0, default 0.8
    #     Same as 'fine speed filter', but note that the range is different
    def gross_speed_filter():
        return Brushlib._getBrushValue(11)

    def set_gross_speed_filter(value):
        Brushlib._setBrushValue(11, value)

    # 12: Fine speed gamma: -8.0 - 8.0, default 4.0
    #      This changes the reaction of the 'fine speed' input to extreme
    #     physical speed. You will see the difference
    #     best if 'fine speed' is mapped to the radius.
    #     -8.0: very fast speed does not increase 'fine speed' much more
    #      8.0: very fast speed increases 'fine speed' a lot
    #     For very slow speed the opposite happens.
    def fine_speed_gamma():
        return Brushlib._getBrushValue(12)

    def set_fine_speed_gamma(value):
        Brushlib._setBrushValue(12, value)

    # 13: Gross speed gamma: -8.0 - 8.0, default 4.0
    #     Same as 'fine speed gamma' for gross speed.
    def gross_speed_gamma():
        return Brushlib._getBrushValue(13)

    def set_gross_speed_gamma(value):
        Brushlib._setBrushValue(13, value)

    # 14: Offset by speed: -3.0 - 3.0, default 0.0
    #      Change position depending on pointer speed
    #     = 0 disable
    #     > 0 draw where the pointer moves to
    #     < 0 draw where the pointer comes from
    def offset_by_speed():
        return Brushlib._getBrushValue(14)

    def set_offset_by_speed(value):
        Brushlib._setBrushValue(14, value)

    # 15: Offset by speed filter: 0.0 - 10.0, default 0.0
    #      Slowdown pointer tracking speed. 0 disables it, higher values remove
    #      more jitter in cursor movements.
    #     Useful for drawing smooth, comic-like outlines.
    def offset_by_speed_filter():
        return Brushlib._getBrushValue(15)

    def set_offset_by_speed_filter(value):
        Brushlib._setBrushValue(15, value)

    # 16: Slow tracking per dab: 0.0 - 10.0, default 0.0
    #      Similar as above but at brushdab level (ignoring how much time has
    #     past, if brushdabs do not depend on time)
    def slow_tracking_per_dab():
        return Brushlib._getBrushValue(16)

    def set_slow_tracking_per_dab(value):
        Brushlib._setBrushValue(16, value)

    # 17: Tracking noise: 0.0 - 12.0, default 0.0
    #      Add randomness to the mouse pointer; this usually generates many
    #     small lines in random directions; maybe try this together with
    #     'slow tracking'
    def tracking_noise():
        return Brushlib._getBrushValue(17)

    def set_tracking_noise(value):
        Brushlib._setBrushValue(17, value)

    # 18: Color hue: 0.0 - 1.0, default 0.0
    def color_hue():
        return Brushlib._getBrushValue(18)

    def set_color_hue(value):
        Brushlib._setBrushValue(18, value)

    # 19: Color saturation: -0.5 - 1.5, default 0.0
    def color_saturation():
        return Brushlib._getBrushValue(19)

    def set_color_saturation(value):
        Brushlib._setBrushValue(19, value)

    # 20: Color value: -0.5 - 1.5, default 0.0
    #     (brightness, intensity)
    def color_value():
        return Brushlib._getBrushValue(20)

    def set_color_value(value):
        Brushlib._setBrushValue(20, value)

    # 21. Save color: 0.0 - 1.0, default 0.0
    #      When selecting a brush, the color can be restored to the color that
    #     the brush was saved with.
    #     0.0: do not modify the active color when selecting this brush
    #     0.5: change active color towards brush color
    #     1.0: set the active color to the brush color when selected
    def save_color():
        return Brushlib._getBrushValue(21)

    def set_save_color(value):
        Brushlib._setBrushValue(21, value)

    # 22. Change color hue: -2.0 - 2.0, default 0.0
    #       Change color hue.
    #     -0.1: small clockwise color hue shift
    #      0.0: disable
    #      0.5: counterclockwise hue shift by 180 degrees
    def change_color_hue():
        return Brushlib._getBrushValue(22)

    def set_change_color_hue(value):
        Brushlib._setBrushValue(22, value)

    # 23. Change color lightness (HSL): -2.0 - 2.0, default 0.0
    #       Change the color lightness (luminance) using the HSL color model.
    #      -1.0: blacker
    #       0.0: disable
    #       1.0: whiter
    def change_color_lightness_hsl():
        return Brushlib._getBrushValue(23)

    def set_change_color_lightness_hsl(value):
        Brushlib._setBrushValue(23, value)


    # 24. Change color satur. (HSL): -2.0 - 2.0, default 0.0
    #      Change the color saturation using the HSL color model.
    #     -1.0: more grayish
    #      0.0: disable
    #      1.0: more saturated
    def change_color_satur_hsl():
        return Brushlib._getBrushValue(24)

    def set_change_color_satur_hsl(value):
        Brushlib._setBrushValue(24, value)

    # 25. Change color value (HSV): -2.0 - 2.0, default 0.0
    #      Change the color value (brightness, intensity) using the HSV color
    #     model.HSV changes are applied before HSL.
    #     1.0: darker
    #     0.0: disable
    #     1.0: brighter
    def change_color_value_hsv():
        return Brushlib._getBrushValue(25)

    def set_change_color_value_hsv(value):
        Brushlib._setBrushValue(25, value)

    # 26. Change color satur. (HSV): -2.0 - 2.0, default 0.0
    #     Change the color saturation using the HSV color model. HSV changes
    #    are applied before HSL.
    #    -1.0: more grayish
    #     0.0: disable
    #     1.0: more saturated
    def change_color_satur_hsv():
        return Brushlib._getBrushValue(26)

    def set_change_color_satur_hsv(value):
        Brushlib._setBrushValue(26, value)

    # 27. Smudge: 0.0 - 1.0, default 0.0
    #      Paint with the smudge color instead of the brush color. The smudge
    #     color is slowly changed to the color you
    #     are painting on.
    #     0.0: do not use the smudge color
    #     0.5: mix the smudge color with the brush color
    #     1.0: use only the smudge color
    def smudge():
        return Brushlib._getBrushValue(27)

    def set_smudge(value):
        Brushlib._setBrushValue(27, value)

    # 28. Smudge length: 0.0 - 1.0, default 0.5
    #     This controls how fast the smudge color becomes the color you are
    #    painting on.
    #    0.0: immediately update the smudge color (requires more CPU cycles
         #    because of the frequent color checks)
    #    0.5: change the smudge color steadily towards the canvas color
    #    1.0: never change the smudge color
    def smudge_length():
        return Brushlib._getBrushValue(28)

    def set_smudge_length(value):
        Brushlib._setBrushValue(28, value)

    # 29. Smudge radius: -1.6 - 1.6, default 0.0
    #      This modifies the radius of the circle where color is picked up for
    #     smudging.
    #     0.0: use the brush radius
    #    -0.7: half the brush radius (fast, but not always intuitive)
    #    +0.7: twice the brush radius
    #    +1.6: five times the brush radius (slow performance)
    def smudge_radius():
        return Brushlib._getBrushValue(29)

    def set_smudge_radius(value):
        Brushlib._setBrushValue(29, value)

    # 30. Eraser: 0.0 - 1.0, default 0.0
    #      how much this tool behaves like an eraser
    #     0.0: normal painting
    #     1.0: standard eraser
    #     0.5: pixels go towards 50% transparency
    def eraser():
        return Brushlib._getBrushValue(30)

    def set_eraser(value):
        Brushlib._setBrushValue(30, value)

    # 31. Stroke threshold: 0.0 - 0.5, default 0.0
    #      How much pressure is needed to start a stroke. This affects the
    #     stroke input only. Mypaint does not need a
    #     minimal pressure to start drawing.
    def stroke_threshold():
        return Brushlib._getBrushValue(31)

    def set_stroke_threshold(value):
        Brushlib._setBrushValue(31, value)

    # 32. Stroke duration: -1.0 - 7.0, default 4.0
    #      How far you have to move until the stroke input reaches 1.0. This
    #     value is logarithmic (negative values will
    #     not inverse the process).
    def stroke_duration():
        return Brushlib._getBrushValue(32)

    def set_stroke_duration(value):
        Brushlib._setBrushValue(32, value)

    # 33. Stroke hold time: 0.0 - 10.0, default 0.0
    #      This defines how long the stroke input stays at 1.0. After that it
    #     will reset to 0.0 and start growing again,
    #     even if the stroke is not yet finished.
    #     2.0 means twice as long as it takes to go from 0.0 to 1.0
    #     9.9 and bigger stands for infinite
    def stroke_hold_time():
        return Brushlib._getBrushValue(33)

    def set_stroke_hold_time(value):
        Brushlib._setBrushValue(33, value)

    # 34. Custom input: -5.0 - 5.0, default 0.0
    #     Set the custom input to this value. If it is slowed down, move it
    #    towards this value (see below). The idea
    #    is that you make this input depend on a mixture of
    #    pressure/speed/whatever, and then make other settings depend on this
    #    'custom input' instead of repeating this combination everywhere you
    #    need it. If you make it change 'by random' you can generate a slow
    #    (smooth) random input.
    def custom_input():
        return Brushlib._getBrushValue(34)

    def set_custom_input(value):
        Brushlib._setBrushValue(34, value)

    # 35. Custom input filter: 0.0 - 10.0, default 0.0
    #      How slow the custom input actually follows the desired value (the
    #     one above). This happens at brushdab level (ignoring how much time
    #     has past, if brushdabs do not depend on time).
    #     0.0: no slowdown (changes apply instantly)
    def custom_input_filter():
        return Brushlib._getBrushValue(35)

    def set_custom_input_filter(value):
        Brushlib._setBrushValue(35, value)

    # 36. Elliptical dab: ratio: 1.0 - 10.0, default 1.0
    #      Aspect ratio of the dabs; must be >= 1.0, where 1.0 means a
    #     perfectly round dab.
    def elliptical_dab_ratio():
        return Brushlib._getBrushValue(36)

    def set_elliptical_dab_ratio(value):
        Brushlib._setBrushValue(36, value)

    # 37. Elliptical dab: angle: 0.0 - 180.0, default 90.0
    #      Angle by which elliptical dabs are tilted
    #     0.0: horizontal dabs
    #     45.0: 45 degrees, turned clockwise
    #     180.0: horizontal again
    def elliptical_dab_angle():
        return Brushlib._getBrushValue(37)

    def set_elliptical_dab_angle(value):
        Brushlib._setBrushValue(37, value)

    # 38. Direction filter: 0.0 - 10.0, default 2.0
    #     A low value will make the direction input adapt more quickly, a high
    #    value will make it smoother
    def direction_filter():
        return Brushlib._getBrushValue(38)

    def set_direction_filter(value):
        Brushlib._setBrushValue(38, value)

    # 39. Lock alpha: 0.0 - 1.0, default 0.0
    #      Do not modify the alpha channel of the layer (paint only where there
    #     is paint already)
    #     0.0: normal painting
    #     0.5: half of the paint gets applied normally
    #     1.0: alpha channel fully locked
    def lock_alpha():
        return Brushlib._getBrushValue(39)

    def set_lock_alpha(value):
        Brushlib._setBrushValue(39, value)

    # 40. Colorize: 0.0 - 1.0, default 0.0
    #      Colorize the target layer, setting its hue and saturation from the
    #     active brush colour while retaining its value and alpha.
    def colorize():
        return Brushlib._getBrushValue(40)

    def set_colorize(value):
        Brushlib._setBrushValue(40, value)

    # 41. Snap to pixel: 0.0 - 1.0, default 0.0
    #     Snap brush dab's center and it's radius to pixels. Set this to 1.0
    #     for a thin pixel brush.
    def snap_to_pixel():
        return Brushlib._getBrushValue(41)

    def set_snap_to_pixel(value):
        Brushlib._setBrushValue(41, value)

    # 42. Pressure gain: -1.8 - 1.8, default 0.0
    #      This changes how hard you have to press. It multiplies tablet
    #     pressure by a constant factor.
    def pressure_gain():
        return Brushlib._getBrushValue(42)

    def set_pressure_gain(value):
        Brushlib._setBrushValue(42, value)
