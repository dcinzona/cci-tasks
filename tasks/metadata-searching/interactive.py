# from io import StringIO
from cumulusci.tasks.salesforce.BaseSalesforceApiTask import BaseSalesforceApiTask
from snowfakery.api import generate_data


class interactive(BaseSalesforceApiTask):
    task_options = {
        "recipe": {
            "required": True,
            "description": "Path to a Snowfakery recipe file determining what fields to use.",
        }
    }

    def _run_task(self):
        # yaml = """
        # - object: Status
        #  fields:
        #    quote: Shiny and new
        # """
        self.recipe = self.options.get("recipe")
        # out = StringIO()
        user_options = (
            {}
        )  # if self.owner is None else {"recordOwnerUsername": f"{self.owner}"}
        plugin_options = {
            "org_config": self.org_config,
            "project_config": self.project_config,
            "plugin_options": {"org_name": self.org_config.name},
        }
        generate_data(
            self.recipe, plugin_options=plugin_options, user_options=user_options
        )
