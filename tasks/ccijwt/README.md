# CCI JWT Authentication POC
Proof of concept for specifying a username and logging in via CumulusCI without a password (Using JWT)
## Setup

This assumes you have a strong understanding of JWT and Connected Apps in Salesforce, created a [connected app](https://developer.salesforce.com/docs/atlas.en-us.232.0.sfdx_dev.meta/sfdx_dev/sfdx_dev_auth_connected_app.htm), and [set up the certificate](https://developer.salesforce.com/docs/atlas.en-us.232.0.sfdx_dev.meta/sfdx_dev/sfdx_dev_auth_key_and_cert.htm) within the app.

After having completed the above, do the following:
1. Copy `sample.env` to `.env`
2. Update the parameters within `.env` (client ID, login URL, private key path, etc.)
3. Run ```./auth.sh -u <username>```

#### Help Command: `./auth.sh -h`

```
$ ./auth.sh -h

Authenticate a user via JWT.

Syntax: auth.sh -u [username] -a [alias] -k [cert path] -c [clientId] [-h|d|C]

Options:

  d     Set the org as the default SF CLI org
  a     The org alias name for SF CLI
  h     Print this Help
  u     Username to authenticate
  c     The client id of the connected app
  C     Create the SFDX Org Connection (easy way to add the connection to your local SFDX environment)
  k     The certificate private key to use for authentication (Default: .jwt/server.key)
  ```


## Dev Setup

Use [pyenv](https://github.com/pyenv/pyenv) and pyenv-virtualenv:

1. `brew install pyenv`
1. `brew install pyenv-virtualenv`
1. `pyenv install 3.9.12`
1. `pyenv virtualenv 3.9.12 ccijwt`
1. `pyenv local ccijwt`
1. `pyenv rehash`
1. `pip install -r requirements.txt --upgrade`

## Using CumulusCI Tasks

TBD: Working on setting up cumulusCI tasks to create certificates and connect orgs and authenticate.

### Creating a Self-Signed Certificate
You can create a self-signed certificate used for JWT auth by running the command: `cci task run make_cert`

  Options

    --hostname HOSTNAME
      Required
      The domain for self-signed certificate generation
      Default: cci.dev.dcinzona.internal

    --dir DIR
      Optional
      If provided, the directory where the command should be run from.

    --interactive INTERACTIVE
      Optional
      If True, the command will use stderr, stdout, and stdin of the main process.Defaults to False.

### Running CCI as another user:

Use the `run_as` task. This will load the environment variables specified in `.env`
The `username` flag will default to the username specified in the .env file. Setting the flag overrides that user.

Example:
```cci task run run_as --alias ccijwt --username <another user>```