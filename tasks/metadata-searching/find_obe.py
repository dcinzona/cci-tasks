from logging import getLogger
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from utils.findOBE import findOBE
import re

PROJECT_CONFIG_RE = re.compile(r"\$project_config.(\w+)")


class find_obe(BaseSalesforceApiTask):
    task_options = {
        "save": {"description": "Wether to save the data to a file", "default": False},
        "sobjects": {
            "description": "List of sobjects to query",
        },
    }

    def _run_task(self):
        super()._validate_options()
        logger = getLogger(__name__)
        # exit()
        runner = findOBE(
            save=f"{self.options['save']}",
            logger=logger,
            org_config=self.org_config,
            sf=self.sf,
            sobjects=self.options["sobjects"] if "sobjects" in self.options else None,
        )
        runner.run()

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
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
