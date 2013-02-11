#!/usr/bin/env bash
if [ -e production ]; then
	python "$(which twistd)" --logger=icl0ud.logger.fileLogger --pidfile data/twistd-push.pid -y pushserver.py
else
	python "$(which twistd)" --logger=icl0ud.logger.stdoutLogger -n --pidfile data/twistd-push.pid -y pushserver.py
fi
