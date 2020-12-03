import time

import numpy as np
import zmq


class LEDPost:
    def __init__(self, fps=120, width=64, height=64, address='tcp://127.0.0.1:5555', channel=b'A'):
        self.context = zmq.Context()

        #  Socket to talk to server
        print(f"Connecting to {address} ...")
        self.channel = channel
        self.socket = self.context.socket(zmq.PUB)
        self.socket.connect(address)
        self.send_matrix = np.zeros((width, height, 3), dtype=np.uint8)
        self.fps = fps
        self.last_frame = time.time()

    def send(self, matrix):
        self.socket.send_multipart([self.channel, matrix.tobytes(order='C')])
        time.sleep(max(0.0, (1.0 / self.fps) - (time.time() - self.last_frame)))
        self.last_frame = time.time()

    def send_non_blocking(self, matrix):
        self.socket.send_multipart([self.channel, matrix.tobytes(order='C')])
        return max(0.0, (1.0 / self.fps) - (time.time() - self.last_frame))

    def send_np_array(self, matrix):
        self.send(matrix.astype(np.uint8))

    def send_pil(self, image):
        self.send(np.array(image.convert('RGB'), dtype=np.uint8))

    def send_color(self, color):
        self.send_matrix[:,:] = np.array(color)[None,None,:]
        self.send(self.send_matrix)