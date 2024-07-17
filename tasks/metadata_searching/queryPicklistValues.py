from logging import getLogger
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from utils.getPicklistValues import picklister, options
import re

PROJECT_CONFIG_RE = re.compile(r"\$project_config.(\w+)")


class queryPicklistValues(BaseSalesforceApiTask):
    task_options = {
        "save": {"description": "Wether to save the data to a file", "default": True},
        "filename": {
            "description": "Path to a file to contain reported data. "
            "All files are saved in a 'reports' folder in the root of this "
            "directory"
        },
        "use_cache": {
            "description": "Query the database, "
            "do not query Salesforce for recent metadata updates",
            "default": True,
        },
        "force_update_cache": {
            "description": "Forces a pull from the latest metadata from the org. "
            "Setting this to True will take a little longer. "
            "Ommitting or setting to False will directly query the local database ",
            "default": False,
        },
        "output": {"description": "Output to CSV of JSON", "default": "csv"},
        "sobjects": {
            "description": "List of sObjects to query. "
            "Leaving this blank or not setting the flag will query all sObjects"
        },
        "labels": {
            "description": "List of strings or words to look for within the field label. "
            "This will search for %word1%word2%"
        },
        "fields": {
            "description": "Comma-delimited list of field API Names to query. "
            "This will search where FieldAPIName in (list)"
        },
        "fields_like": {
            "description": "Comma-delimited list of words to look for within the field's API name. "
            "This will search for field API names like %word1%word2%"
        },
        "field_type": {
            "description": "Filters on custom, standard or all fields."
            "Use 'custom' for custom fields, 'standard' for only standard fields"
            "Blank or any other value will query all picklist fields",
            "default": "custom",
        },
    }

    def _run_task(self):
        super()._validate_options()
        logger = getLogger(__name__)
        print(self.options)
        options.logger = logger
        # exit()
        if self.options["force_update_cache"]:
            self.options["use_cache"] = False
        picklister(
            save=f"{self.options['save']}",
            queryCache=(
                eval(self.options["use_cache"])
                if type(self.options["use_cache"]) is str
                else self.options["use_cache"]
            ),
            updateCache=(
                eval(self.options["force_update_cache"])
                if type(self.options["force_update_cache"]) is str
                else self.options["force_update_cache"]
            ),
            logger=logger,
            org_config=self.org_config,
            sf=self.sf,
            filename=self.options["filename"],
            ext=self.options["output"],
            sobj=self.options["sobjects"].split(","),
            labels=self.options["labels"].split(","),
            fieldApiNames=self.options["fields"].split(","),
            fieldApiNamesLike=self.options["fields_like"].split(","),
            field_type=self.options["field_type"],
        )

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
