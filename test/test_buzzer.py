# test_buzzer.py
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)

print("삐- 소리 나면 정상")
GPIO.output(17, True)
time.sleep(1)
GPIO.output(17, False)
GPIO.cleanup()