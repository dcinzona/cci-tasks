# This script executs a REST request to a Salesforce org using the Salesforce CLI access token

# Defaults
token=""
url=""
org_name=""
api_uri="/services/data/v59.0/query/?q="
query="SELECT+name+from+Account+limit+1"
user_id=""

function instance_url() {
    if [[ "$#" -gt 0 ]] ; then
        sf org display -o $1 --json | jq -r '.result.instanceUrl'
    else
        sf org display --json | jq -r '.result.instanceUrl'
    fi
}

function access_token() {
    if [[ "$#" -gt 0 ]] ; then
        sf org display -o $1 --json | jq -r '.result.accessToken'
    else
        sf org display --json | jq -r '.result.accessToken'
    fi
}

if [[ "$#" -eq 0 ]] ; then
    echo "using default org"
    token=$(access_token)
    url=$(instance_url)
    # user_id=$(sf org display user --json | jq -r '.result.id')
    # user_id=$(sf org display user -o $org_name --json | jq -r '.result.id')
else
    while [ "$#" -gt 0 ]; do
        case "$1" in
            -h|--help)
            echo "Usage: sfrest.sh -o <org_name> -r <api_uri> -q <query>"
            echo "Example: sfrest.sh -o myorg -r /services/data/v59.0/query/?q= -q SELECT+name+from+Account+limit+1"
            exit 1
            ;;
            -o|--org)
            org_name="$2"
            token=$(access_token $org_name)
            url=$(instance_url $org_name)
            shift 2
            ;;
            -r|--uri)
            api_uri="$2"
            query="" # clear query as it may not be compatible with the new service uri
            shift 2
            ;;
            -q|--query)
            query="$2"
            shift 2
            ;;
            *)
            echo "Usage: sfrest.sh -o <org_name> -r <api_uri> -q <query>"
            echo "Example: sfrest.sh -o myorg -r /services/data/v59.0/query/?q= -q SELECT+name+from+Account+limit+1"
            echo "Example 2: sh ./scripts/sfrest.sh -r '/services/data/v60.0/chatter/users/me/following'"
            exit 1
            ;;
        esac
    done
fi

# if url or token are empty, then use default
if [[ -z "$url" ]] ; then
    url=$(instance_url)
fi
if [[ -z "$token" ]] ; then
    token=$(access_token)
fi


resource="$url$api_uri$query"
curl "$resource" \
    -H "Authorization: Bearer $token" \
    -H "X-PrettyPrint:1"