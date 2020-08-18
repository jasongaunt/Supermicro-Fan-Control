#!/usr/bin/python

'''

Script to parse and process IPMI information from SuperMicro X8/9/10/11 boards and intelligently adjust fan PWM.
Written by JBG 20190715

*** PLEASE READ THE README FILE FOR USAGE INFORMATION ***

*** I TAKE NO RESPONSIBILITY FOR ANY DAMAGES THAT MAY OCCUR FROM USING THIS SCRIPT. NO WARRANTY WHATSOEVER ***

'''

# Import required modules
import os, sys, re, time, configparser, statistics
from subprocess import Popen, PIPE

# Set up our default variables with safe values
ZONE_A_SENSOR_NAME_SEARCH = r'^.*CPU.*$'
ZONE_A_SENSOR_TEST_MATCH = False
ZONE_A_MIN_TEMP = 50
ZONE_A_MIN_FAN_PWM = 80
ZONE_A_MAX_TEMP = 60
ZONE_A_MAX_FAN_PWM = 100
ZONE_B_SENSOR_NAME_SEARCH = r'^.*CPU.*$'
ZONE_B_SENSOR_TEST_MATCH = True
ZONE_B_MIN_TEMP = 50
ZONE_B_MIN_FAN_PWM = 80
ZONE_B_MAX_TEMP = 60
ZONE_B_MAX_FAN_PWM = 100
POLL_RATE = 5
IGNORE_TEMP_CHANGE_AMOUNT = 1
EXIT_ON_FAILURE = False
DEBUG = False

# Wrapper for (re)reading config.ini
def reload_config():
	global DEBUG
	if DEBUG: sys.stdout.write('Reloading config... '); sys.stdout.flush()
	config = configparser.ConfigParser()
	config.read(os.path.join(os.path.dirname(__file__), './config.ini'))

	global ZONE_A_SENSOR_NAME_SEARCH; ZONE_A_SENSOR_NAME_SEARCH = config.get('Fan Zone A', 'Sensor Name Search')
	global ZONE_A_SENSOR_TEST_MATCH;  ZONE_A_SENSOR_TEST_MATCH  = config.get('Fan Zone A', 'Sensor Test Match').lower() in ["yes", "true", "1"]
	global ZONE_A_MIN_TEMP;           ZONE_A_MIN_TEMP           = int(config.get('Fan Zone A', 'Minimum Temperature Degrees'))
	global ZONE_A_MIN_FAN_PWM;        ZONE_A_MIN_FAN_PWM        = int(config.get('Fan Zone A', 'Minimum Temperature Fan PWM'))
	global ZONE_A_MAX_TEMP;           ZONE_A_MAX_TEMP           = int(config.get('Fan Zone A', 'Maximum Temperature Degrees'))
	global ZONE_A_MAX_FAN_PWM;        ZONE_A_MAX_FAN_PWM        = int(config.get('Fan Zone A', 'Maximum Temperature Fan PWM'))

	global ZONE_B_SENSOR_NAME_SEARCH; ZONE_B_SENSOR_NAME_SEARCH = config.get('Fan Zone B', 'Sensor Name Search')
	global ZONE_B_SENSOR_TEST_MATCH;  ZONE_B_SENSOR_TEST_MATCH  = config.get('Fan Zone B', 'Sensor Test Match').lower() in ["yes", "true", "1"]
	global ZONE_B_MIN_TEMP;           ZONE_B_MIN_TEMP           = int(config.get('Fan Zone B', 'Minimum Temperature Degrees'))
	global ZONE_B_MIN_FAN_PWM;        ZONE_B_MIN_FAN_PWM        = int(config.get('Fan Zone B', 'Minimum Temperature Fan PWM'))
	global ZONE_B_MAX_TEMP;           ZONE_B_MAX_TEMP           = int(config.get('Fan Zone B', 'Maximum Temperature Degrees'))
	global ZONE_B_MAX_FAN_PWM;        ZONE_B_MAX_FAN_PWM        = int(config.get('Fan Zone B', 'Maximum Temperature Fan PWM'))

	global POLL_RATE;                 POLL_RATE                 = int(config.get('General Configuration', 'Poll Rate'))
	global IGNORE_TEMP_CHANGE_AMOUNT; IGNORE_TEMP_CHANGE_AMOUNT = int(config.get('General Configuration', 'Ignore Temp Change Amount'))
	global EXIT_ON_FAILURE;           EXIT_ON_FAILURE           = config.get('General Configuration', 'Exit On IPMI Failure').lower() in ["yes", "true", "1"]
	DEBUG = config.get('General Configuration', 'Debug Mode').lower() in ["yes", "true", "1"]

	if DEBUG: sys.stdout.write("done\n")

# Wrapper for making IPMI calls
def call_ipmi(params):
	IPMICMD = "./IPMICFG-Linux.x86"
	IPMICWD = os.path.join(os.path.dirname(__file__), "./ipmitool/")
	IPMICMD = [IPMICMD]	+ params
	if DEBUG: sys.stdout.write(' ' + ' '.join(IPMICMD) + '\n')
	process = Popen(IPMICMD, stdout=PIPE, cwd=IPMICWD)
	(output, err) = process.communicate()
	EXITCODE = process.wait()
	if DEBUG: sys.stdout.write("IPMI exit code: %d\n" % EXITCODE)
	return [EXITCODE, output.decode('utf-8'), err]

# Wrapper for making sure we're not already running
def check_if_already_running():
	if DEBUG: sys.stdout.write("Checking if already running other than my PID %d... " % os.getpid()); sys.stdout.flush()
	CMD = ["pgrep", "-f", __file__]
	if DEBUG: sys.stdout.write('Calling ' + ' '.join(CMD) + '\n'); sys.stdout.flush()
	process = Popen(CMD, stdout=PIPE)
	(output, err) = process.communicate()
	EXITCODE = process.wait()
	if DEBUG: sys.stdout.write("Check process exit code: %d\n" % EXITCODE); sys.stdout.flush()
	for line in output.decode('utf-8').split("\n"):
		if line == "": continue
		line = line.split()
		if DEBUG: sys.stdout.write("Found PID %d... " % int(line[0])); sys.stdout.flush()
		if int(line[0]) == 0: continue # Safety net
		if int(line[0]) == os.getpid():
			if DEBUG: sys.stdout.write("this is me, ignoring.\n"); sys.stdout.flush()
		else:
			if DEBUG: sys.stdout.write("stopping here as there is another instance running.\n"); sys.stdout.flush()
			exit(0)

# Wrapper for calculating fan PWM - this is quite complex
def calculate_pwm(PEAK_TEMP, MIN_TEMP, MAX_TEMP, MIN_FAN_PWM, MAX_FAN_PWM):
	PWMVAL = float(PEAK_TEMP)
	if   PWMVAL < MIN_TEMP: PWMVAL = MIN_TEMP # Sanitise input
	elif PWMVAL > MAX_TEMP: PWMVAL = MAX_TEMP # Sanitise input
	PWMVAL = (PWMVAL - MIN_TEMP) / (MAX_TEMP - MIN_TEMP) # Calculate ratio of where between min-max temps our value sits
	PWMVAL = MIN_FAN_PWM + ((MAX_FAN_PWM - MIN_FAN_PWM) * PWMVAL) # Calculate ratio between mix-max fan pwm
	if   PWMVAL < MIN_FAN_PWM: PWMVAL = MIN_FAN_PWM # Sanitise output
	elif PWMVAL > MAX_FAN_PWM: PWMVAL = MAX_FAN_PWM # Sanitise output
	return int(PWMVAL)

# Main program loop starts here
reload_config(); check_if_already_running();
ZONE_A_TEMP_SAMPLES = [ZONE_A_MAX_TEMP, ZONE_A_MAX_TEMP, ZONE_A_MAX_TEMP, ZONE_A_MAX_TEMP, ZONE_A_MAX_TEMP]
ZONE_A_LAST_PWM = 0
ZONE_B_TEMP_SAMPLES = [ZONE_B_MAX_TEMP, ZONE_B_MAX_TEMP, ZONE_B_MAX_TEMP, ZONE_B_MAX_TEMP, ZONE_B_MAX_TEMP]
ZONE_B_LAST_PWM = 0
USE_ALT_COMMANDS=True
while True:
	# Reset variables
	PEAK_ZONE_A_TEMP = 0
	FINAL_ZONE_A_TEMP = 0
	PEAK_ZONE_B_TEMP = 0
	FINAL_ZONE_B_TEMP = 0
	ZONE_A_FINAL_PWM = 0
	ZONE_B_FINAL_PWM = 0
	FAILED_FAN = False
	reload_config()

	# Print time
	sys.stdout.write('\nTimestamp of run: ' + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + ' UTC\n=========================================\n'); sys.stdout.flush()

	# Get sensor values from IPMI
	sensorinfo = call_ipmi(["-sdr"])
	if sensorinfo[0] != 0:
		sys.stdout.write("Error getting info from IPMI: " + sensorinfo[1] + "\n"); sys.stdout.flush()
		if EXIT_ON_FAILURE: sys.exit(sensorinfo[0])
		time.sleep(POLL_RATE)
		continue

	# Process our sensor values and grab the highest for each zone
	for line in sensorinfo[1].split("\n"):
		# Parse returned data if we can, otherwise ignore it
		if "|" not in line: continue
		line = line.rstrip().split("|")
		line[0] = line[0].strip()
		line[1] = line[1].strip()
		line[2] = line[2].strip()
		if DEBUG: sys.stdout.write(line[1] + ": " + line[2] + "\n"); sys.stdout.flush()

		# Check to see if we have a failed fan
		if ((line[0].lower() == "fail") and ("fan" in line[1].lower())): FAILED_FAN = True

		# Only continue past this point of the for-loop if we have a temperature value
		if not re.match(r'\d+C\/\d+F', line[2]): continue

		# Check to see if this sensor matches Zone A
		if (ZONE_A_SENSOR_NAME_SEARCH.lower() in line[1].lower()) == ZONE_A_SENSOR_TEST_MATCH:
			temp = line[2].split('C/')
			if DEBUG: sys.stdout.write("ZONE A SENSOR MATCH: " + line[1] + " " + temp[0] + "'C\n"); sys.stdout.flush()
			if int(temp[0]) > PEAK_ZONE_A_TEMP: PEAK_ZONE_A_TEMP = int(temp[0])

		# Check to see if this sensor matches Zone B
		if (ZONE_B_SENSOR_NAME_SEARCH.lower() in line[1].lower()) == ZONE_B_SENSOR_TEST_MATCH:
			temp = line[2].split('C/')
			if DEBUG: sys.stdout.write("ZONE B SENSOR MATCH: " + line[1] + " "+ temp[0] + "'C\n"); sys.stdout.flush()
			if int(temp[0]) > PEAK_ZONE_B_TEMP: PEAK_ZONE_B_TEMP = int(temp[0])

	# Average out temp values over the last 5 samples to smooth RPM changes and output our values
	ZONE_A_TEMP_SAMPLES.append(PEAK_ZONE_A_TEMP); ZONE_A_TEMP_SAMPLES.pop(0)
	FINAL_ZONE_A_TEMP = int(statistics.mean(ZONE_A_TEMP_SAMPLES))
	ZONE_B_TEMP_SAMPLES.append(PEAK_ZONE_B_TEMP); ZONE_B_TEMP_SAMPLES.pop(0)
	FINAL_ZONE_B_TEMP = int(statistics.mean(ZONE_B_TEMP_SAMPLES))
	sys.stdout.write("\nMaximum Zone A temp = " + str(PEAK_ZONE_A_TEMP) + "'C, averaged " + str(FINAL_ZONE_A_TEMP) + "'C\nMaximum Zone B temp = " + str(PEAK_ZONE_B_TEMP) + "'C, averaged " + str(FINAL_ZONE_B_TEMP) + "'C\n"); sys.stdout.flush()

	# Calculate our fan PWM values
	if FAILED_FAN:
		sys.stdout.write('Failed fan detected. Setting both zones to 100% PWM!\n'); sys.stdout.flush()
		ZONE_A_TEMP_SAMPLES = [100, 100, 100, 100, 100]
		ZONE_B_TEMP_SAMPLES = [100, 100, 100, 100, 100]
		ZONE_A_FINAL_PWM = 100
		ZONE_B_FINAL_PWM = 100
	else:
		ZONE_A_FINAL_PWM = calculate_pwm(FINAL_ZONE_A_TEMP, ZONE_A_MIN_TEMP, ZONE_A_MAX_TEMP, ZONE_A_MIN_FAN_PWM, ZONE_A_MAX_FAN_PWM)
		ZONE_B_FINAL_PWM = calculate_pwm(FINAL_ZONE_B_TEMP, ZONE_B_MIN_TEMP, ZONE_B_MAX_TEMP, ZONE_B_MIN_FAN_PWM, ZONE_B_MAX_FAN_PWM)

	# Set fan speeds
	if abs(ZONE_A_FINAL_PWM - ZONE_A_LAST_PWM) > IGNORE_TEMP_CHANGE_AMOUNT:
		sys.stdout.write('Setting our Zone A fan PWM to ' + str(ZONE_A_FINAL_PWM) + '%... '); sys.stdout.flush()
		if not USE_ALT_COMMANDS:
			updatepwm = call_ipmi("-raw 0x30 0x70 0x66 0x01 0x00".split() + [hex(int((ZONE_A_FINAL_PWM * 2.55) / 2))])
			if updatepwm[0] != 0:
				sys.stdout.write("error setting fan PWM, attempting alternative command... "); sys.stdout.flush()
				USE_ALT_COMMANDS = True
				if EXIT_ON_FAILURE: sys.exit(updatepwm[0])
			else: sys.stdout.write("success!\n"); sys.stdout.flush()
		if USE_ALT_COMMANDS:
			updatepwm = call_ipmi("-raw 0x30 0x91 0x5A 0x3 0x10".split() + [hex(int((ZONE_A_FINAL_PWM * 2.55) / 1))])
			if updatepwm[0] != 0:
				sys.stdout.write("error setting fan PWM by alternative command too!\n"); sys.stdout.flush()
				if EXIT_ON_FAILURE: sys.exit(updatepwm[0])
			else: sys.stdout.write("success!\n"); sys.stdout.flush()
		ZONE_A_LAST_PWM = ZONE_A_FINAL_PWM
	else:
		sys.stdout.write('Not setting our Zone A fan PWM, little to no change since last time (' + str(ZONE_A_FINAL_PWM) + '%).\n'); sys.stdout.flush()

	if abs(ZONE_B_FINAL_PWM - ZONE_B_LAST_PWM) > IGNORE_TEMP_CHANGE_AMOUNT:
		sys.stdout.write('Setting our Zone B fan PWM to ' + str(ZONE_B_FINAL_PWM) + '%... '); sys.stdout.flush()
		if not USE_ALT_COMMANDS:
			updatepwm = call_ipmi("-raw 0x30 0x70 0x66 0x01 0x01".split() + [hex(int((ZONE_B_FINAL_PWM * 2.55) / 2))])
			if updatepwm[0] != 0:
				sys.stdout.write("error setting fan PWM, attempting alternative command..."); sys.stdout.flush()
				USE_ALT_COMMANDS = True
				if EXIT_ON_FAILURE: sys.exit(updatepwm[0])
			else: sys.stdout.write("success!\n"); sys.stdout.flush()
		if USE_ALT_COMMANDS:
			updatepwm = call_ipmi("-raw 0x30 0x91 0x5A 0x3 0x11".split() + [hex(int((ZONE_B_FINAL_PWM * 2.55) / 1))])
			if updatepwm[0] != 0:
				sys.stdout.write("error setting fan PWM by alternative command too!\n"); sys.stdout.flush()
				if EXIT_ON_FAILURE: sys.exit(updatepwm[0])
			else: sys.stdout.write("success!\n"); sys.stdout.flush()
		ZONE_B_LAST_PWM = ZONE_B_FINAL_PWM
	else:
		sys.stdout.write('Not setting our Zone B fan PWM, little to no change since last time (' + str(ZONE_B_FINAL_PWM) + '%).\n'); sys.stdout.flush()

	sys.stdout.flush()

	# Sleep 5 seconds
	time.sleep(POLL_RATE)