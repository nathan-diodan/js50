cmake_minimum_required(VERSION 3.13)
project(lamp_pusher C)

set(CMAKE_C_STANDARD 99)

include_directories(/home/pi/lamp_data/rpi-rgb-led-matrix/lib)
include_directories(/home/pi/lamp_data/rpi-rgb-led-matrix/include)

add_executable(lamp_pusher main.c)
target_link_libraries(lamp_pusher  /home/pi/lamp_data/rpi-rgb-led-matrix/lib/librgbmatrix.so.1 -lczmq -lzmq)