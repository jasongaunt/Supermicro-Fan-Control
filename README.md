Disclaimer
----------
PLEASE READ THIS DOCUMENT **ENTIRELY** - FAILURE TO DO SO MAY RESULT IN DAMAGE TO YOUR SYSTEM

I TAKE NO RESPONSIBILITY FOR ANY DAMAGES THAT MAY OCCUR FROM USING THIS SCRIPT. NO WARRANTY WHATSOEVER!


Introduction
------------
This tool is aimed at VMware ESXi, FreeBSD and Linux users who wish to better control their fans based on temperatures.

It monitors configured CPU / Motherboard / Memory temps and will set fan speeds accordingly with a little smoothing to
prevent rapidly changing fan speeds aka yo-yo'ing (which annoys those nearby and can reduce fan bearing lifespan).

I wrote this tool for use with VMware ESXi on a Supermicro X8SIL-F but it should work on other x86/x64 \*nix systems and
hopefully all Supermicro X8 / X9 / X10 / X11 boards with IPMI. I have personally tested it on the following;

* Supermicro X9DRi-LN4+
* Supermicro X8SIL-F (IPMI equipped variant)

* VMWare ESXi 6.7
* VMware ESXi 5.5
* Ubuntu 20.04
* Ubuntu 18.04
* Ubuntu 16.04

For this script to work, you **MUST** have an IPMI module **AND** set your fan speeds to FULL SPEED in the BIOS otherwise
this tool fights for control with the fans and they will spin up and down repeatedly (yo-yo'ing).

Setting it to full speed not only helps reduce *yo-yo'ing* of fan speeds but also provides a safety-net if a fan drops below
a certain RPM or worse, dies completely. In this eventuality the fans will default to full speed.


Installation
------------
#### VMware
On VMware these scripts should work straight out of the box, they do however require a persistent datastore to live on.

Place the files in something along the lines of `/vmfs/volumes/datastore1/tools/FanControl/` and then add the following
to the `/etc/rc.local.d/local.sh` (or `/etc/rc.local` if that file doesn't exist) **above** the `exit 0` statement;

~~~
/vmfs/volumes/datastore1/tools/FanControl/daemon.sh
~~~

#### Ubuntu
On Ubuntu systems you may need to install 32-bit execution support, `sudo su` to root and run the following;

~~~
dpkg --add-architecture i386
apt-get update
apt-get install libc6:i386 libncurses5:i386 libstdc++6:i386
apt-get install multiarch-support
~~~

Next, find a suitable place for the scripts to live such as `/opt/FanControl/` (you may need to create that dir).

Finally, run `crontab -e` and add the following line;

~~~
@reboot /opt/FanControl/daemon.sh
~~~


Hardware fan assignments
------------------------
Nearly all Supermicro X8 / X9 / X10 / X11 series motherboards have numerous fan ports, these are split into two zones;

* Zone A = **Numerical** fan ports labelled FAN1, FAN2 etc - there are usually at least four of these
* Zone B = **Alphabetical** fan ports labelled FANA / FANB - there are usually only two of these

The Supermicro IPMI system does NOT permit individual fan control, you can only control them **by zone**.


Recommended Fan Connection Strategy
-----------------------
#### Rackmount server cases

Supermicro boards are typically installed in rackmount cases where a cluster of fans cool the CPU, RAM and motherboard as one area, so
Supermicro assume Zone A is used for cooling the main system and Zone B for cooling auxiliary areas such as PCIe cards, drive bays etc.

* Zone A = Anything that cools the CPU, memory and motherboard
* Zone B = Anything that cools PCIe cards and / or drive bays

#### Desktop cases

If, like myself, you're using a Supermicro board in a desktop case, chances are you've already using dedicated CPU coolers with their
own fans. In this formation, I highly recommend you do the _opposite_ and **CONNECT THE CPU FANS** to Zone B ports and the remaining
case fans to Zone A.

* Zone A = Anything other than CPU fans
* Zone B = Fans that directly cool the CPU

It makes temperature management more efficient. There are usually only 1-2 CPU fans and if we can then cool the CPUs independently of
the rest of the case, we can control heat better by keeping those fans at a faster speed but reduce case fan speeds and noise overall.


Configuration
-------------
#### Sensor test options

The Sensor Name Search option allows you to select a sensor if it contains this value (case-insensitive). "CPU" (without the quotes)
would naturally select any temperature sensor with the word CPU, cpu, Cpu etc.

The Sensor Test Match option allows you to choose whether the selected sensor **SHOULD** or **SHOULD NOT** be accepted for that zone;

* By setting this to True, sensors will be selected if they match the search term
* By setting this to False, sensors that DO NOT match the search term will be selected instead

This is useful if you want to match CPU sensors in one zone and non-CPU temperature sensors in the other zone, just set the search
to the same in both zones and then set one zone to `match = True` and the other zone to `match = False`.

#### Fan PWM options

These are minimum and maximum fan speeds per zone, expressed as a PWM percentage, for example `60` is 60% PWM duty cycle and
should theoretically be 60% of the fan's maximum speed (this differs between different brands / models of fan).

Please note, if **any** fan speed falls below **650 RPM**, the IPMI will assume it's stalled, log a _fan fail_ alert and set **ALL** fans to
100% speed. When the script next sets the fan speeds, the fans will slow and may be considered as stalled again.

If this happens, your fans will repeatedly go **fast -> slow -> fast -> slow**, _over and over again_. This is known as yo-yo'ing.

To counteract this, raise your minimum fan PWM until your fan reads **675 RPM or greater** at its lowest setting.

If you still get yo-yo'ing, check to make sure you don't have a failed fan or if your fan can even spin that fast (some 200+ mm fans can't)

#### Temperature options

All temperatures are degrees Celsius, values are for which fans will be at their minimum and maximum speeds respectively.

Recommended _min -> max_ temperature ranges:

* 55 -> 65 for CPU temps
* 65 -> 75 for RAM and Chipset / BCH temps
* 45 -> 55 for Board / Case ambient temps
* 35 -> 45 for Hard Disk drive temps

These are intentionally conservative and components may tolerate higher, however one component may heat up another and cause heat soak.

Behaviour Example
-------
With the following values...

| Field       | Min | Max |
|-------------|-----|-----|
| Temperature | 60  | 70  |
| Fan PWM     | 50  | 100 |

We can expect the following behaviour (apologies for the crudely drawn ASCII graph);

~~~
PWM%

100 |           ,------
90  |          /
80  |         /
70  |        /
60  |       /
50  |------`
    `------------------
      50   60   70   80 'C
~~~

The values included in `config.ini` by default are sane values to start with. Good luck!

~ JG
