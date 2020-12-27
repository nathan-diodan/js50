# js50

*js50* is a collection of tools to create an interactive light installation controlled by a Telegram bot.
 
## Setup
These setup instructions are written for the [Raspberry Pi OS Lite](https://www.raspberrypi.org/software/operating-systems/) and tested with a [Adafruit RGB matrix bonnet](https://learn.adafruit.com/adafruit-rgb-matrix-bonnet-for-raspberry-pi).

After the system is flashed, login as `pi` over ssh.
Ensure that the system is up to date.

```shell script
sudo apt update
sudo apt upgrade
```

The different parts of the toolkit require a variety of packages to be installed.
```shell script
sudo apt install git cmake libczmq-dev python3-venv python3-dev npm chromium-browser ffmpeg
sudo apt install libatlas-base-dev  libproj-dev proj-data proj-bin libfreetype6-dev
sudo apt install libgeos-dev libopenjp2-7-dev libtiff-dev libasound2-dev
sudo apt install portaudio19-dev libportaudio2 libportaudiocpp0 xvfb libwebp-dev
``` 

Next the needed sources are downloaded in the pi home folder.

```shell script
cd /home/pi
mkdir lamp_data
cd lamp_data
git clone https://github.com/nathan-diodan/js50.git
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
```

Compiling Henner Zeller's matrix library 

```shell script
cd rpi-rgb-led-matrix/lib
make
```

and then the C interface for the python code.

```shell script
cd /home/pi/lamp_data/js50/js50c
cmake -DCMAKE_BUILD_TYPE=Release ./
make
sudo cp js50/js50c/lamp_pusher /usr/local/sbin/
```

Preparing the python environment. The requirements are split in three parts.
```shell script
cd /home/pi/lamp_data/
python3 -m 'venv' venv_lamp
. venv_lamp/bin/activate
pip install -r js50/js50py/requirements.txt 
pip install -r js50/js50py/requirements_2.txt 
pip install -r js50/js50py/requirements_3.txt 
```

Set up the autostart with systemd.

```shell script
chmod +x js50/system/auto_lamp_*
sudo cp js50/system/auto_lamp_pusher.sh /usr/local/sbin/
sudo cp js50/system/auto_lamp_player.sh /usr/local/bin
sudo cp js50/system/auto_lamp_bot.sh /usr/local/bin
sudo cp js50/system/*.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable lamp_bot.service
sudo systemctl enable lamp_player.service
sudo systemctl enable lamp_pusher.service
```

Deactivate sound `dtparam=audio=off` in `/boot/config.txt`.
Prepare for the first lunch:
```shell script
python /home/pi/lamp_data/js50/js50py/setup.py
```
It will ask for the some information like your telegram bot token to create the `settings.json`.
