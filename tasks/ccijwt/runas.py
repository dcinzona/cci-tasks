import json
from utilities.envparser import (
    load_env_vars,
    getKey,
    get_value_from_option,
)
from cumulusci.tasks.command import Command
from dotenv import load_dotenv
from cumulusci.core.exceptions import TaskOptionsError

import os


class RunCommand(Command):

    task_options = {
        "command": {
            "description": "Command to run",
            "required": True,
        },
        "username": {
            "description": "Username to use for executing the command",
            "required": True,
        },
        "alias": {
            "description": "Used to set the environment variable CUMULUSCI_ORG_{alias}",
            "required": True,
        },
    }

    def _init_options(self, kwargs):
        load_dotenv()
        super(RunCommand, self)._init_options(kwargs)
        self.alias = self.options["alias"]
        self.username = self._get_option("username")
        self.options["command"] = self._replace_command_tokens()

    def _get_option(self, key):
        if key in self.options:
            return get_value_from_option(self.options[key])
        else:
            raise TaskOptionsError(
                "Value not found for option {}.  Please set it in the task options or in the environment".format(
                    key
                )
            )

    def _replace_command_tokens(self):
        command = self.options["command"]
        # if command.find(" --org ") == -1:
        #     command = f"{command} --org {self.alias}"
        return command.format(alias=self.alias, username=self.username)

    def _run_task(self):
        load_env_vars()
        self.instance_url = os.getenv("_LOGIN_URL")
        os.environ.setdefault("SFDX_CLIENT_ID", os.getenv("_CLIENTID"))
        os.environ.setdefault("SFDX_HUB_KEY", getKey(False))
        os.environ.setdefault(
            f"CUMULUSCI_ORG_{self.alias}",
            json.dumps({"username": self.username, "instance_url": self.instance_url}),
        )
        env = self._get_env()
        self.logger.info("Environment variables:")
        self.logger.info(json.dumps(env, indent=2))
        # self._connect_sfdx()
        self._run_command(
            env,
            command=self.options["command"],
            output_handler=None,
            return_code_handler=self.handle_error,
        )

    def handle_error(self, returncode, stderr):
        if returncode == 1:
            self.logger.error(f"Command failed with return code {returncode}")
            self.logger.error(f"Command failed with stderr {stderr}")
            self._run_command(self._get_env(), "cci error info")

    def _connect_sfdx(self):
        env = self._get_env()
        # first remove cci org connection with alias
        try:
            self._run_command(env, "cci org remove {}".format(self.alias))
        except Exception:
            pass
        # now create a new connection with the new alias
        command = "sfdx force:auth:jwt:grant --clientid {client_id} --jwtkeyfile {jwt_key} --username {username} --instanceurl {login_url} --setalias {alias}".format(
            client_id=env.get("_CLIENTID"),
            jwt_key=env.get("_KEYPATH"),
            username=self.username,
            login_url=env.get("_LOGIN_URL"),
            alias=self.alias,
        )
        self.logger.info(command)
        self._run_command(env, command)
