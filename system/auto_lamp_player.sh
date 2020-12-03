. /home/pi/lamp_data/venv_lamp/bin/activate
export DISPLAY=:99.0
Xvfb :99 -screen 0 64x64x24 &
cd /home/pi/lamp_data/js50/js50py
python lamp_player.py