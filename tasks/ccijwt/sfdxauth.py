import json
import os
from cumulusci.tasks.sfdx import SFDXBaseTask
from cumulusci.core.exceptions import TaskOptionsError
from utilities.envparser import (
    get_value_from_option,
    load_env_vars,
)
from cumulusci.core.exceptions import CommandException

AUTH_COMMAND = "sfdx force:auth:jwt:grant --clientid {client_id} --jwtkeyfile {key_path} --instanceurl {loginurl} --username {username} --setalias {alias}"


class ConnectSFDX_JWT(SFDXBaseTask):

    task_docs = """
       **Example Command-line Usage:**

        ``cci task run createSFDXJWT --username test@username --clientid MW3425wfSEFXxdf32w... --alias testccijwt --loginurl https://mydomain.my.salesforce.com --jwtkey .jwt/server.key``

       **Using Environment Variables:**

       The below command will check the os environment for the following variables: ``username``, ``client_id``, ``key_path``, ``login_url``

        ``cci task run createSFDXJWT --username {username} --clientid {client_id} --alias testccijwt --loginurl {login_url} --jwtkey {key_path}``


    """

    task_options = {
        "username": {
            "description": "Connect to your connected app with SFDX JWT with the provided username.",
            "required": True,
        },
        "clientid": {
            "description": "Client ID for the connected app.",
            "required": True,
        },
        "jwtkey": {
            "description": "Path to the JWT key file.",
            "required": True,
        },
        "loginurl": {
            "description": "Login URL for the connected app (https://mydomain.my.salesforce.com).",
            "required": True,
        },
        "alias": {
            "description": "SFDX org alias to be used for the connection.",
            "required": False,
        },
    }

    def _init_options(self, kwargs):
        super(ConnectSFDX_JWT, self)._init_options(kwargs)
        load_env_vars()
        self.env = self._get_env()
        self.username = self._get_option_value_or_token("username")
        self.client_id = self._get_option_value_or_token("clientid")
        self.login_url = self._get_option_value_or_token("loginurl")
        self.key_path = self._get_option_value_or_token("jwtkey")
        self.alias = self.options["alias"] if "alias" in self.options else "ccijwt"

    def _get_option_value_or_token(self, key):
        if key in self.options:
            value = get_value_from_option(self.options[key])
            if not value:
                print(json.dumps(self.env, indent=2))
                raise TaskOptionsError(
                    f'Environment variable "{self.options[key]}" was not found for option "--{key}"',
                    "--{} {}".format(key, self.options[key]),
                )
            return value
        else:
            return None

    def _get_command(self):
        command = AUTH_COMMAND.format(
            client_id=self.client_id,
            key_path=self.key_path,
            loginurl=self.login_url,
            username=self.username,
            alias=self.alias,
        )
        return command

    def _run_task(self):
        self.logger.info(self.username)
        self.options["command"] = self._get_command()
        output = []
        self._run_command(
            command=self._get_command(),
            env=self.env,
            output_handler=output.append,
            return_code_handler=self._handle_returncode,
        )
        resp = output[0].decode("utf-8")
        if resp.find("Successfully authorized") != -1:
            spl = resp.split(" ")
            self.logger.info(
                "Successfully authorized {} into org {}".format(self.username, spl[-1])
            )

            os.putenv("SFDX_HUB_USERNAME", self.username)
            os.putenv("SFDX_CLIENT_ID", self.client_id)
            os.putenv("SFDX_HUB_KEY", self._getCertString(self.key_path))
            os.putenv(f"CUMULUSCI_ORG_{self.alias}", self.username)

    def _handle_returncode(self, returncode, stderr):
        if returncode:
            message = "Return code: {}".format(returncode)
            if stderr:
                message += "\nstderr: {}".format(stderr.read().decode("utf-8"))
            self.logger.error(message)
            raise CommandException(message)

    def _getCertString(self, cert_path):
        with open(cert_path, "r", encoding="utf-8") as f:
            cert = ""
            for line in f.readlines():
                cert += line.strip() if line.find("-----") == -1 else ""
            return cert
