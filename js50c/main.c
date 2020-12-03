/* -*- mode: c; c-basic-offset: 2; indent-tabs-mode: nil; -*-
 *
 * Using the C-API of this library.
 *
 */
#include "led-matrix-c.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <czmq.h>

static char * s_recv (void *socket) {
    enum { cap = 256 };
    char buffer [cap];
    int size = zmq_recv (socket, buffer, cap - 1, 0);
    if (size == -1)
        return NULL;
    buffer[size < cap ? size : cap - 1] = '\0';
    return strndup (buffer, sizeof(buffer) - 1);
}



int main(int argc, char **argv) {
    struct RGBLedMatrixOptions options;
    struct RGBLedMatrix *matrix;
    struct LedCanvas *offscreen_canvas;
    int width, height;
    int x, y, i;
    const int loops=1024;
    u_int8_t nextMatrix[64][64][3];

    fprintf(stderr,"Connecting ...\n");

    void *context = zmq_ctx_new ();
    void *subscriber = zmq_socket (context, ZMQ_SUB);
    zmq_bind (subscriber, "tcp://127.0.0.1:5555");

    zmq_setsockopt (subscriber, ZMQ_SUBSCRIBE, "A", 1);

    memset(&options, 0, sizeof(options));
    options.rows = 32;
    options.cols = 64;
    options.chain_length = 2;

    /* This supports all the led commandline options. Try --led-help */
    matrix = led_matrix_create_from_options(&options, &argc, &argv);
    if (matrix == NULL)
        return 1;

    offscreen_canvas = led_matrix_create_offscreen_canvas(matrix);

    led_canvas_get_size(offscreen_canvas, &width, &height);

    fprintf(stderr, "Size: %dx%d. Hardware gpio mapping: %s\n",
            width, height, options.hardware_mapping);

    while (!zctx_interrupted) {
       char *address = s_recv (subscriber);
       zmq_recv (subscriber, nextMatrix, 64*64*3*sizeof(u_int8_t), 0);
        free (address);


        for (y = 0; y < height; ++y) {
            for (x = 0; x < width; ++x) {
                led_canvas_set_pixel(offscreen_canvas, height-y-1, width-x-1, nextMatrix[x][y][0], nextMatrix[x][y][1], nextMatrix[x][y][2]);
            }
        }

        offscreen_canvas = led_matrix_swap_on_vsync(matrix, offscreen_canvas);
    }

    led_matrix_delete(matrix);
    zmq_close (subscriber);
    zmq_ctx_destroy (context);

    return 0;
}