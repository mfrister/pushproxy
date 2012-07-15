#!/usr/bin/env bash
if [ -e production ]; then
	python "$(which twistd)" -l data/push.log --pidfile data/twistd-push.pid -y pushserver.py
else
	python "$(which twistd)" -l- -n --pidfile data/twistd-push.pid -y pushserver.py
fi
