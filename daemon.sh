#!/bin/sh

# To enable this script on boot, add it to /etc/rc.local.d/local.sh

cd `dirname $0`
nohup ./fan-control.py >> /var/log/fan-control.log 2>&1 &
