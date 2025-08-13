#!/bin/bash
env >> /etc/environment

# execute CMD
echo "$@"
exec "$@"
