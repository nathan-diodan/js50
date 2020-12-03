import colorsys
import math
import time
from multiprocessing import Process, Queue
from pathlib import Path
from queue import Empty as qu_Empty
from threading import Thread

import moderngl
import numpy as np
import sounddevice as sd
import zmq
from matplotlib import cm
from pyhap import const
from pyhap.accessory import Accessory
from pyhap.accessory_driver import AccessoryDriver

from js50py.animation_helper.animation_functions import load_video, load_animation, load_text, load_qr, get_time_quad
from js50py.animation_helper.render_earth import render_earth, render_single_frame
from js50py.post_master import LEDPost


class LPlayer:
    def __init__(self):

        self.LEDmatrix = LEDPost(fps=30)

        context = zmq.Context()
        self.control_socket = context.socket(zmq.REP)
        self.control_socket.bind("tcp://127.0.0.1:2222")

        self.mode = 'telegram'

        self.current_animation = load_animation(Path('/home/pi/dev/lamp/cache/telegram/animated_sticker/AgADMQADwZxgDA.npz'))
        self.current_player = Player(self.LEDmatrix, self.current_animation)
        self.current_player.start()

    def recv_work(self, copy=True, track=False):
        meta_data = self.control_socket.recv_json()
        print(meta_data)
        if meta_data['type'] == 'cache':
            if meta_data['file_type'] == 'video':
                self.current_animation = load_video(Path(meta_data['cache']))
            elif meta_data['file_type'] == 'sticker':
                self.current_animation = load_animation(Path(meta_data['cache']))
        elif meta_data['type'] == 'music':
            self.current_animation = {'music': True, 'fps':60, 'name': meta_data['name']}
        elif meta_data['type'] == 'opengl':
            self.current_animation = {'opengl': True, 'fps':120}
        elif meta_data['type'] == 'apple':
            self.current_animation = {'apple': True, 'command': meta_data['command']}
        elif meta_data['type'] == 'animation_data':
            msg = self.control_socket.recv(copy=copy, track=track)
            buf = memoryview(msg)
            animation_data_raw = np.frombuffer(buf, dtype=meta_data['dtype'])
            animation_data_raw = animation_data_raw.reshape(meta_data['shape'])
            self.current_animation = {'animation': True, 'fps': 5, 'frames': animation_data_raw}
        elif meta_data['type'] == 'text':
            self.current_animation = load_text(meta_data['text'])
        elif meta_data['type'] == 'qr':
            self.current_animation = load_qr(meta_data['data'])
        elif meta_data['type'] == 'clock':
            self.current_animation = {'clock': True}
        elif meta_data['type'] == 'settings':
            self.mode = meta_data['mode']
        self.control_socket.send_string('received')
        return True

    def run(self):
        while True:
            self.recv_work()
            if self.current_player:
                self.current_player.stop()
                self.current_player.join()
            if self.current_animation.get('music'):
                self.current_player = MusicPlayer(self.LEDmatrix, self.current_animation)
            elif self.current_animation.get('opengl'):
                self.current_player = OpenGLPlayer(self.LEDmatrix, self.current_animation)
            elif self.current_animation.get('apple'):
                self.current_player = AppleHomeKitPlayer(self.LEDmatrix, self.current_animation)
            elif self.current_animation.get('clock'):
                self.current_player = ClockPlayer(self.LEDmatrix, self.current_animation)
            else:
                self.current_player = Player(self.LEDmatrix, self.current_animation)
            self.current_player.start()


class Player(Thread):
    def __init__(self, led_matrix, current_animation):
        self.current_animation = current_animation
        self.led_matrix = led_matrix
        self.stopped = False
        self.width = 64
        super().__init__()

    def run(self):
        self.led_matrix.fps = self.current_animation['fps']
        if self.current_animation.get('animation'):
            while not self.stopped:
                for frame in self.current_animation['frames']:
                    if not self.stopped:
                        self.led_matrix.send(frame)
                    else:
                        break
        elif self.current_animation.get('mover'):
            if self.current_animation['frame'].shape[1] == self.width:
                self.led_matrix.fps = 5
                while not self.stopped:
                    self.led_matrix.send(self.current_animation['frame'])
            else:
                while not self.stopped:
                    for n in range(self.current_animation['frame'].shape[1]-self.width):
                        if not self.stopped:
                            self.led_matrix.send(self.current_animation['frame'][:, n:n+self.width])
                        else:
                            break

    def stop(self):
        self.stopped = True


class ClockPlayer(Thread):
    def __init__(self, led_matrix, current_animation):
        super().__init__()
        self.stopped = False
        self.led_matrix = led_matrix
        self.rotation_per_minute = 5
        self.led_matrix.fps = 30
        self.current_animation = current_animation
        self.earth_queue = Queue(1)
        self.resolution_rotation = 360
        self.rot_frames = self.led_matrix.fps * 60 / self.rotation_per_minute
        self.earth_process = Process(target=render_earth, args=(self.earth_queue,), kwargs={'num': self.resolution_rotation})
        self.earth_process.start()
        self.earth = render_single_frame(0, 52)[None, ...]

    def run(self):
        n = 0
        while not self.stopped:
            n = (n+1) % self.rot_frames
            frame = int(n/self.rot_frames * len(self.earth))
            try:
                self.earth = self.earth_queue.get(False)
            except qu_Empty:
                pass
            self.led_matrix.send(get_time_quad(self.earth, earth_frame=frame))
        pass

    def stop(self):
        self.stopped = True
        self.earth_process.kill()


class AppleHomeKitPlayer(Thread):
    def __init__(self, led_matrix, current_animation):
        super().__init__()
        self.driver = AccessoryDriver(port=51826)
        if current_animation['command'] == 'setup':
            self.lamp = self.Light(self.driver, 'JS50 (LED Matrix)', led_matrix=led_matrix, setup=True)
        else:
            self.lamp = self.Light(self.driver, 'JS50 (LED Matrix)', led_matrix=led_matrix, setup=False)

    def run(self):
        self.driver.add_accessory(accessory=self.lamp)
        self.driver.start()

    def stop(self):
        self.driver.stop()

    class Light(Accessory):
        """Implementation of a mock light accessory."""

        category = const.CATEGORY_LIGHTBULB  # This is for the icon in the iOS Home app.

        def __init__(self, *args, led_matrix=None, setup=False, **kwargs):
            """Here, we just store a reference to the on and brightness characteristics and
            add a method that will be executed every time their value changes.
            """
            # If overriding this method, be sure to call the super's implementation first.
            super().__init__(*args, **kwargs)

            # Set our neopixel API services up using Lightbulb base
            serv_light = self.add_preload_service(
                'Lightbulb', chars=['On', 'Hue', 'Saturation', 'Brightness'])

            # Configure our callbacks
            self.char_hue = serv_light.configure_char(
                'Hue', setter_callback=self.set_hue)
            self.char_saturation = serv_light.configure_char(
                'Saturation', setter_callback=self.set_saturation)
            self.char_on = serv_light.configure_char(
                'On', setter_callback=self.set_state)
            self.char_on = serv_light.configure_char(
                'Brightness', setter_callback=self.set_brightness)

            # Set our instance variables
            self.accessory_state = 0  # State of the neo light On/Off
            self.hue = 0  # Hue Value 0 - 360 Homekit API
            self.saturation = 100  # Saturation Values 0 - 100 Homekit API
            self.brightness = 100  # Brightness value 0 - 100 Homekit API
            self.LEDmatrix = led_matrix
            if setup:
                qr = load_qr(self.xhm_uri())
                self.LEDmatrix.send(qr['frame'])
            else:
                self.update_matrix((0, 0, 0))

        def update_matrix(self, color):
            self.LEDmatrix.send_color(color)

        def set_state(self, value):
            self.accessory_state = value
            if value == 1:  # On
                self.set_hue(self.hue)
            else:
                self.update_matrix((0, 0, 0))  # Off

        def set_hue(self, value):
            # Lets only write the new RGB values if the power is on
            # otherwise update the hue value only
            if self.accessory_state == 1:
                print(self.hue, self.saturation, self.brightness)
                self.hue = value
                rgb_tuple = self.hsv_to_rgb(
                    self.hue, self.saturation, self.brightness)
                print(rgb_tuple)
                if len(rgb_tuple) == 3:
                    self.update_matrix(rgb_tuple)
            else:
                self.hue = value

        def set_brightness(self, value):
            self.brightness = value
            self.set_hue(self.hue)

        def set_saturation(self, value):
            self.saturation = value
            self.set_hue(self.hue)

        # The `stop` method can be `async` as well
        def stop(self):
            """We override this method to clean up any resources or perform final actions, as
            this is called by the AccessoryDriver when the Accessory is being stopped.
            """
            print('Stopping accessory.')

        def hsv_to_rgb(self, h, s, v):
            return [int(rgb * 255) for rgb in colorsys.hsv_to_rgb(h / 360.0, s / 100.0, v / 100.0)]

class OpenGLPlayer(Thread):
    def __init__(self, led_matrix, current_animation, device='cap'):
        super().__init__()
        self.device = device
        self.samplerate = sd.query_devices(self.device, 'input')['default_samplerate']
        self.rec_time = 1.0 / current_animation['fps']
        self.fps = current_animation['fps']
        self.current_animation = current_animation
        self.led_matrix = led_matrix
        self.stopped = False
        self.draw = self.first_3d

    def run(self):
        self.draw()

    @staticmethod
    def particle(x=0, y=0, color = None):
        a = np.random.uniform(0.0, 2 * np.pi)
        radius = np.random.uniform(0.005, 0.08)
        if color is None:
            r,g,b = [np.random.uniform(0, 1) for c in range(3)]
        else:
            r,g,b = color
        return np.array([x, y, r, g, b,
                         x + (np.cos(a) * radius), y + (np.sin(a) * radius)]).astype('f4')

    @staticmethod
    def mass_particle(size, x=0,y=0,color=None):
        out = np.zeros((size,7), dtype='f4')
        a = np.random.uniform(0.0, 2 * np.pi, size=size)
        radius = np.random.uniform(0.005, 0.08, size=size)
        if color is None:
            r, g, b = np.random.uniform(0.1, 0.7, size=3)
        else:
            r, g, b = color
        out[:,0] = x
        out[:,1] = y
        out[:,2] = r
        out[:,3] = g
        out[:,4] = b
        out[:,5] = x + (np.cos(a) * radius)
        out[:,6] = y + (np.sin(a) * radius)

        out[:,2:5] *= np.random.uniform(0.7, 1.8, size=size)[:,None]
        out[:,2:5][out[:,2:5]>1] = 1

        # out = np.stack([[x]*size, [y]*size, [r]*size, [g]*size, [b]*size, x + (np.cos(a) * radius), y + (np.sin(a) * radius)])
        return out

    def first_3d(self):
        ctx = moderngl.create_context(standalone=True, backend='egl')
        fbo = ctx.simple_framebuffer((64, 64), components=3, dtype='f4')
        fbo.use()

        prog = ctx.program(
            vertex_shader='''
                        #version 330

                        in vec2 in_vert;
                        in vec3 in_color;
                        out vec3 color;
                        
                        void main() {
                            gl_Position = vec4(in_vert, 0.0, 1.0);
                            color = in_color;
                        }
                    ''',
            fragment_shader="""
                    #version 330
                    out vec4 fragColor;
                    in vec3 color;
                    void main() {
                        fragColor = vec4(color, 0.5);
                    }
                    """,
        )

        transform = ctx.program(
            vertex_shader='''
                    #version 330

                    uniform vec2 Acc;

                    in vec2 in_pos;
                    in vec3 in_color;
                    in vec2 in_prev;

                    out vec2 out_pos;
                    out vec3 out_color;
                    out vec2 out_prev;

                    void main() {
                        vec2 velocity = in_pos - in_prev;
                        out_pos = in_pos + velocity + Acc;
                        out_prev = in_pos;
                        out_color = in_color;
                    }
                ''',
            varyings=['out_pos', 'out_color', 'out_prev']
        )

        acc = transform['Acc']
        #acc.value = (0.0, 0.0)
        acc.value = (0.0, -0.0008)

        vbo1 = ctx.buffer(b''.join(self.particle() for i in range(1024)))

        vao1 = ctx.simple_vertex_array(transform, vbo1, 'in_pos', 'in_color', 'in_prev' )

        render_vao = ctx.vertex_array(prog, [
             (vbo1, '2f 3f 2x4', 'in_vert', 'in_color'),
         ])

        idx = 0
        buffer = np.zeros(6)
        colors = [np.random.uniform(0.2, 1, size=3) for n in range(6)]
        while not self.stopped:
            # self.led_matrix.last_frame = time.time()
            # rec_time = max(self.rec_time, 1/self.fps)
            # print(self.rec_time, self.samplerate, math.ceil(self.rec_time * self.samplerate))

            # recording = sd.rec(int(rec_time * self.samplerate), device = self.device, channels = 1)
            # magnitude = np.abs(np.fft.rfft(np.nan_to_num(recording[:, 0]), n=16))
            # magnitude *= 10
            # buffer += magnitude[1:-2]
            # maxi = np.sum(np.abs(np.nan_to_num(recording)))
            ctx.clear(0.0, 0.0, 0.0)
            ctx.point_size = 1
            if np.random.random() > 0.95:
            #print(buffer)
            # if np.any(buffer>0.1):
                # print(maxi)
                # print(magnitude)
                # print(buffer)
                # for n, value in enumerate(buffer):
                #     if value>1:
                #         buffer[n] = 0.0
                        x = np.random.uniform(-1,1)
                        y = np.random.uniform(-1,1)
                        color = np.random.uniform(0.2, 1, size=3)
                        # color = colors[n]
                        size = np.random.randint(50, 300)
                        if size + idx >= 1024:
                            part_1 = 1024-idx
                            vbo1.write(self.mass_particle(part_1, x, y, color), offset=idx * 28)
                            vbo1.write(self.mass_particle(size-part_1, x, y, color), offset=0)
                        else:
                            vbo1.write(self.mass_particle(size,x,y, color), offset=idx * 28)
                        idx = (idx + size) % 1024

            render_vao.render(moderngl.POINTS, 1024)
            vao1.transform(vbo1, moderngl.POINTS, 1024)
            image = np.frombuffer(fbo.read(components=3, dtype='f4'), dtype='f4') * 255.0
            image = image.astype(np.uint8)
            image = np.flip(image.reshape((64, 64, 3)), axis=0)
            self.rec_time = self.led_matrix.send(image)



    def color_breath(self):
        ctx = moderngl.create_context(standalone=True, backend='egl')
        fbo = ctx.simple_framebuffer((64, 64), components=3, dtype='f4')
        fbo.use()
        prog = ctx.program(vertex_shader="""
        #version 330
        in vec2 in_vert;
        in vec3 in_color;
        out vec3 color;
        void main() {
            gl_Position = vec4(in_vert, 0.0, 1.0);
            color = in_color;
        }
        """,
        fragment_shader="""
        #version 330
        out vec4 fragColor;
        in vec3 color;
        void main() {
            fragColor = vec4(color, 1.0);
        }
        """,
                           )

        blue = 0
        while not self.stopped:
            blue = (blue + 1) % 200
            green = (blue + 66) % 200
            red = (blue + 133) % 200
            vertices = np.array([
                -1.0, -1.0, abs((100-blue)/100), 0.0, 0.0,
                1.0, -1.0, 0.0, abs((100-green)/100), 0.0,
                -1.0, 1.0, abs((100 - red) / 100), abs((100 - red) / 100), abs((100 - red) / 100),
                1.0, 1.0, 0.0, 0.0, abs((100 - red) / 100),
                1.0, -1.0, 0.0, abs((100 - green) / 100), 0.0,
                -1.0, 1.0, abs((100 - red) / 100), abs((100 - red) / 100), abs((100 - red) / 100),
            ],
                dtype='f4',
            )

            vao = ctx.simple_vertex_array(prog, ctx.buffer(vertices), 'in_vert', 'in_color')
            vao.render(mode=moderngl.TRIANGLES)

            image = np.frombuffer(fbo.read(components=3, dtype='f4'), dtype='f4') * 255.0
            image = image.astype(np.uint8)
            # print(image)
            # print(image.shape)
            # image.reshape((64,64,3))
            image = np.flip(image.reshape((64, 64, 3)), axis=0)
            self.led_matrix.send(image)

    def stop(self):
        self.stopped = True

class MusicPlayer(Thread):
    def __init__(self, led_matrix, current_animation, device='cap', color_map='inferno', gain=50, width=64, height=64):
        self.current_animation = current_animation
        self.led_matrix = led_matrix
        self.device = device
        self.samplerate = sd.query_devices(self.device, 'input')['default_samplerate']
        self.block_duration = 1000 / math.ceil(current_animation['fps'])  # ms
        print(self.block_duration)
        print(self.samplerate)
        print(int(self.samplerate * self.block_duration / 1000))
        self.stopped = False
        self.gain = gain
        self.width, self.height = width, height
        self.color_canvas = np.zeros((width,height,3), dtype=np.uint8)
        self.pos = 0
        self.color_map = cm.get_cmap(color_map)
        super().__init__()

    def colorize_matrix(self, m, limit=1):
        c = self.color_map((m+limit)/(limit*2))[:,:,:3]*255
        return c

    def colorize_line(self, l, limit=1):
        l[l>1] = 1
        c = self.color_map(l/limit)[:,:3]*255
        return c

    def spectral(self, indata, frames, time, status):
        low = 100
        high = 2000
        width = int(self.width / 2.0)
        delta_f = (high - low) / (width - 1)

        fftsize = math.ceil(self.samplerate / delta_f)
        low_bin = math.floor(low / delta_f)
        if any(indata):
            magnitude = np.abs(np.fft.rfft(indata[:, 0], n=fftsize))
            magnitude *= self.gain / fftsize
            line = np.zeros(self.width)
            magnitude = magnitude[low_bin:low_bin + width]
            line[:int(self.width/2.0)] = np.flip(magnitude)
            line[int(self.width / 2.0):] = magnitude
            self.line = line
            self.color_canvas = np.roll(self.color_canvas, 1, axis=0)
            self.color_canvas[0] = self.colorize_line(line)
            self.led_matrix.send_non_blocking(self.color_canvas)
        else:
            print('no input')

    def run(self):
        self.line = 0
        self.led_matrix.fps = self.current_animation['fps']
        try:
            callback = getattr(self, self.current_animation['name'])
        except AttributeError:
            return
        with sd.InputStream(device=self.device, channels=1, callback=callback,
                            blocksize=int(self.samplerate * self.block_duration / 1000),
                            samplerate=self.samplerate):
            while True:
                try:
                    self.color_canvas = np.roll(self.color_canvas, 1, axis=0)
                    self.color_canvas[0] = self.colorize_line(self.line)
                    self.led_matrix.send(self.color_canvas)
                except Exception as e:
                    print(e)
                    time.sleep(0.1)
                if self.stopped:
                    break

    def stop(self):
        self.stopped = True

lp = LPlayer()
lp.run()