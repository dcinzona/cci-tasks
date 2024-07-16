#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
sh $SCRIPT_DIR/sfrest.sh -r /services/data/v60.0/chatter/users/me/following $@