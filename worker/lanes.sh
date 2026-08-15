#!/bin/zsh
# Start/stop/inspect the three lanes. They are independent: stopping one never
# blocks the others, which is the entire point of the split.
set -e
HERE="${0:A:h}"
LANES=(collector classifier publisher)
case "${1:-status}" in
  install)
    for l in $LANES; do
      cp "$HERE/launchd/com.reddit-index.$l.plist" ~/Library/LaunchAgents/
      launchctl bootout gui/$UID/com.reddit-index.$l 2>/dev/null || true
      launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.reddit-index.$l.plist
      echo "installed $l"
    done ;;
  uninstall)
    for l in $LANES; do launchctl bootout gui/$UID/com.reddit-index.$l 2>/dev/null || true; done ;;
  start) for l in $LANES; do launchctl kickstart gui/$UID/com.reddit-index.$l; done ;;
  stop)  for l in $LANES; do launchctl kill SIGTERM gui/$UID/com.reddit-index.$l 2>/dev/null || true; done ;;
  status) python3 "$HERE/status.py" ;;
  watch)  python3 "$HERE/status.py" --watch ;;
  logs)   tail -f /tmp/ri-collector.log /tmp/ri-classifier.log /tmp/ri-publisher.log ;;
  *) echo "usage: lanes.sh {install|uninstall|start|stop|status|watch|logs}"; exit 1 ;;
esac
