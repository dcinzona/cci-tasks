from cumulusci.salesforce_api.org_schema import get_org_schema
from cumulusci.core.config import TaskConfig
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from pathlib import Path
import os
from cumulusci.utils.xml.metadata_tree import parse
from cumulusci.tasks.metadata_etl.help_text import SetFieldHelpText


class UpdateHelpText(BaseSalesforceApiTask):

    task_options = {
        "dir": {
            "description": "The path to the source directory",
            "required": False,
        },
    }

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        self.dir = self.options.get("dir", self.project_config.default_package_path)
        self.fields = []
        self.fields_to_update = []
    
    def _run_task(self):
        self.logger.info(f"Project directory: {self.dir}")
        self._process_dir()
        if len(self.fields) == 0:
            self.logger.info("No fields with help text found")
            return
        self.logger.info(f"Fields with help text: {self.fields}")
        with get_org_schema(self.sf, self.org_config) as schema:
            for field in self.fields:                
                obj, field_name = field["api_name"].split(".")
                self.logger.info(f"Checking field {field_name} on object {obj}")
                field_schema = schema[obj]["fields"].get(field_name)
                if field_schema is not None:
                    if field["help_text"] != field_schema["inlineHelpText"]:
                        self.logger.info(f"Updating help text for {field['api_name']}")
                        self.fields_to_update.append(field)

        self.return_values = {"fields": self.fields_to_update}
        self.logger.info(f"Fields to update: {self.fields_to_update}")
        if len(self.fields_to_update) > 0:
            task = _make_task(SetFieldHelpText, self.project_config, self.org_config, fields=self.fields_to_update, overwrite=True)
            task()

    def _process_dir(self):
        for path, folders, files in os.walk(self.dir):
            for filename in files:
                if filename.endswith(".field-meta.xml"):
                    sobject = Path(path).parent.name
                    field_file_path = os.path.join(path, filename)
                    field = self._get_field_with_help_text(field_file_path)
                    if field is not None:
                        field_api_name = f"{sobject}.{field.fullName.text}"
                        self.fields.append({
                            "api_name": field_api_name,
                            "help_text": field.inlineHelpText.text
                            })

    def _get_field_with_help_text(self, field_file_path):
        field = parse(field_file_path)
        return field if field.find("inlineHelpText") is not None else None
 

def _make_task(task_class, project_config, org_config, **options):
    task_config = TaskConfig({"options": options})
    return task_class(project_config, task_config, org_config)
