#!/bin/sh

BLACK=$(tput setaf 0)
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
LIME_YELLOW=$(tput setaf 190)
POWDER_BLUE=$(tput setaf 153)
BLUE=$(tput setaf 4)
MAGENTA=$(tput setaf 5)
CYAN=$(tput setaf 6)
WHITE=$(tput setaf 7)
BRIGHT=$(tput bold)
NORMAL=$(tput sgr0)
BLINK=$(tput blink)
REVERSE=$(tput smso)
UNDERLINE=$(tput smul)

CONNECT=0
SET_DEFAULT=0
_KEYPATH=.jwt/server.key
_ALIAS=ccijwt

# Local .env
[ -f .env ] && source .env

############################################################
# Help                                                     #
############################################################
Help()
{
   # Display Help
   echo ""
   echo "Authenticate a user via JWT."
   echo
   echo "Syntax: auth.sh -u [username] -a [alias] -k [cert path] -c [clientId] [-h|d|C]"
   echo ""
   echo "Options:"
   echo ""
   echo "  d     Set the org as the default SF CLI org"
   echo "  a     The org alias name for SF CLI"
   echo "  h     Print this Help"
   echo "  u     Username to authenticate"
   echo "  c     The client id of the connected app"
   echo "  C     Create the SFDX Org Connection (easy way to add the connection to your local SFDX environment)"
   echo "  k     The certificate private key to use for authentication (Default: .jwt/server.key)"
   echo
}

ConnectSFDX()
{
    COMMAND="sfdx force:auth:jwt:grant --clientid $_CLIENTID --username $_USERNAME --setalias $_ALIAS \
    --jwtkeyfile $_KEYPATH"

    if [[ $SET_DEFAULT -eq 1 ]];
    then
        COMMAND="$COMMAND --setdefaultdevhubusername "
    fi
    eval $COMMAND
}

PASSED_ARGS=$@
if [[ ${#PASSED_ARGS} -ne 0 ]]
then
  while getopts ":c:k:u:a:Cdh" ARG; do
    echo "\nRunning JWT CCI Test"
    case "$ARG" in 
        h) Help && exit 0 ;;
        d) SET_DEFAULT=1 && echo "  Setting default org";;
        a) _ALIAS=${OPTARG} && echo "  Set ALIAS = $_ALIAS";;
        u) _USERNAME=${OPTARG} && echo "  Set USERNAME = $_USERNAME \n";;
        c) _CLIENTID=${OPTARG} && echo "  Set CLIENTID = $_CLIENTID \n";;
        k) _KEYPATH=${OPTARG} && echo "  Set KEY = $_KEYPATH \n";;
        C) CONNECT=1;;
        :​) echo "argument missing for $ARG" ;;
        \?) echo "Something is wrong" ;;
    esac
  done
else
  Help
  exit 1
fi

shift "$((OPTIND-1))"

# 

RunRun()
{
    export CUMULUSCI_ORG_ccijwt="{\"username\": \"$_USERNAME\", \"instance_url\": \"$_LOGIN_URL\"}"
    export SFDX_CLIENT_ID=$_CLIENTID
    export SFDX_HUB_KEY=`cat $_KEYPATH`
    export SFDX_HUB_USERNAME=$_USERNAME

    # echo "$CUMULUSCI_ORG_ccijwt"
    # echo "$SFDX_HUB_USERNAME"
    if [[ $CONNECT -eq 1 ]];
    then
        ConnectSFDX
    fi
    # sfdx config:set defaultdevhubusername=$_ALIAS
    cciCommand="cci task run execute_anon --apex \"System.debug(Userinfo.getUserId());\" --org $_ALIAS"
    echo "Executing CCI Command:\n ${YELLOW} $cciCommand ${NORMAL}\n"
    eval $cciCommand
}

RunRun