# from logging import getLogger
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from utils.getDependencies import getDependencies
import re

PROJECT_CONFIG_RE = re.compile(r"\$project_config.(\w+)")


class getDeps(BaseSalesforceApiTask):
    task_options = {
        "org_name": {
            "description": "The alias of the org to use",
        },
        "fields": {
            "description": "List of fields to check for dependencies"
            "Format: 'SOBJECTAPINAME.FIELDAPINAME, SOBJ2.FIELD2'"
            "example: Account.Name,CustomObj__c.Name",
            "default": "",
        },
    }

    def _run_task(self):
        super()._validate_options()
        # logger = getLogger(__name__)
        # exit()
        self.options["org_name"] = self.org_config.name
        print("Getting dependencies for org: {}".format(self.options["org_name"]))
        runner = getDependencies(self.options)
        runner.run()

    def _init_options(self, kwargs):
        super(getDeps, self)._init_options(kwargs)
        """Initializes self.options"""
        if self.task_config.options is None:
            self.options = {}
        else:
            self.options = self.task_config.options.copy()

        if kwargs:
            self.options.update(kwargs)
        # Handle dynamic lookup of project_config values via $project_config.attr
        for option, value in self.options.items():
            if isinstance(value, str):
                value = PROJECT_CONFIG_RE.sub(
                    lambda match: str(
                        getattr(self.project_config, match.group(1), None)
                    ),
                    value,
                )
                self.options[option] = value
