export ORG_ALIAS
while [ "$1" != "" ]; do
  case $1 in
    -a | --alias ) shift
                   ORG_ALIAS=$1
                   ;;
  esac
  shift
done
while [ "$ORG_ALIAS" = "" ]; do
  read -p "Enter the alias of the scratch org: " ORG_ALIAS
done

echo "Resetting the scratch org with alias $ORG_ALIAS"
cci org scratch_delete --org $ORG_ALIAS
cci org info $ORG_ALIAS