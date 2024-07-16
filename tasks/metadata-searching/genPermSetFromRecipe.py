import os
import tempfile
from pathlib import Path
from urllib.parse import unquote
from cumulusci.core.config import TaskConfig
from cumulusci.tasks.metadata_etl.permissions import AddPermissionSetPermissions
from cumulusci.tasks.salesforce.BaseSalesforceApiTask import BaseSalesforceApiTask
from cumulusci.utils.xml import metadata_tree
from snowfakery.api import open_file_like
import cumulusci.core.exceptions as exc

from snowfakery.data_generator_runtime import ParseResult
from snowfakery.parse_recipe_yaml import parse_recipe
import json
import re

PROJECT_CONFIG_RE = re.compile(r"\$project_config.(\w+)")
FIELD_PERMISSIONS = []


class generatePermSetFromRecipe(BaseSalesforceApiTask):
    task_options = {
        "recipe": {
            "required": True,
            "description": "Path to a Snowfakery recipe file determining what fields to use.",
        },
        "permset": {
            "required": True,
            "description": "The API Name of the Permission Set to use. Example: Temp_Res_Permissions",
            "default": "Temp_Res_Permissions",
        },
        "editable": {
            "description": "If true, the fields defined will be set to editable. Default is false.",
            "default": False,
        },
        "readable": {
            "description": "If true, the fields defined will be set to readable. Default is true.",
            "default": True,
        },
    }

    original_xml = {}
    transformed_xml = {}
    readable = True
    editable = False

    def _validate_options(self):
        super()._validate_options()
        recipe = self.options.get("recipe")
        recipe = Path(recipe)
        if not recipe.exists():
            raise exc.TaskOptionsError(f"Cannot find recipe `{recipe}`")

    def setup(self):
        self.recipe = Path(self.options.get("recipe"))
        self.permissionSetName = self.options.get("permset")
        editable = self.options.get("editable")
        if editable is not None:
            self.editable = json.loads(editable.lower())
        readable = self.options.get("readable")
        if readable is not None:
            self.readable = json.loads(readable.lower())

    def _run_task(self):
        # Save to /reports/permission_sets/orgname/
        self.output_dir = os.path.join(
            os.getcwd(), "reports", "permission_sets", self.org_config.name
        )
        self.setup()
        self.parseRecipe(self.recipe)
        os.makedirs(self.output_dir, exist_ok=True)
        self.getPermSetFromOrg()
        for file, transformed_xml in self.transformed_xml.items():
            # save the transformed xml
            with open(os.path.join(self.output_dir, file), "w") as f:
                f.write(transformed_xml)
            self.logger.info(f"Saved transformed {file} to {self.output_dir}")

    def getPermSetFromOrg(self):
        taskOptions = {
            "managed": False,
            "api_version": self.api_version,
            "api_names": self.permissionSetName,
            "field_permissions": FIELD_PERMISSIONS,
        }
        task_config = TaskConfig({"options": taskOptions})
        task = AddPermissionSetPermissions(
            self.project_config, task_config, self.org_config
        )
        task.deploy = False
        with tempfile.TemporaryDirectory() as tempdir:
            task._create_directories(tempdir)
            if task.retrieve:
                task._retrieve()
            folder = os.path.join(task.retrieve_dir, "permissionsets")
            files = os.listdir(folder)
            for file in files:
                if file.endswith(".permissionset"):
                    unquoted_api_name = unquote(file)
                    path = os.path.join(folder, file)
                    try:
                        tree = metadata_tree.parse(path)
                        self.original_xml[file] = tree
                        original_fileName = "original_" + file
                        # save the original xml
                        with open(
                            os.path.join(self.output_dir, original_fileName), mode="w"
                        ) as f:
                            f.write(tree.tostring(xml_declaration=True))
                    except SyntaxError as err:
                        err.filename = path
                        raise err
                    transformed = task._transform_entity(tree, unquoted_api_name)
                    self.transformed_xml[file] = transformed.tostring(
                        xml_declaration=True
                    )
        return self.transformed_xml

    def parseRecipe(self, file):
        with open_file_like(file, mode="r") as (path, f):
            data = parse_recipe(f)
            recipeData = RecipeObject(data)
            FIELD_PERMISSIONS.extend(
                [
                    {
                        "editable": self.editable,
                        "field": compName,
                        "readable": self.readable,
                    }
                    for compName in recipeData.compoundFields
                ]
            )


class RecipeObject(dict):

    compoundFields = []

    def __getattr__(self, item):
        try:
            return self[item]
        except Exception as ex:
            print(ex)
            return None

    def __init__(self, data: ParseResult):
        recipeObjects = sorted(data.tables.keys())
        for k in recipeObjects:
            t = data.tables[k]
            fields = sorted(t.fields.keys())
            for field in fields:
                self._setFieldData(k, field)
                (sobj, f) = self._getPCKeyValue(k, field)
                compName = "{}.{}".format(sobj, f)
                (
                    self.compoundFields.append(compName)
                    if compName not in self.compoundFields
                    else None
                )
        self.compoundFields = sorted(list(set(self.compoundFields)))

    def _checkKey(self, k):
        if k not in self.keys():
            self[k] = {}
            self[k]["fields"] = []

    # Person Accounts transformation (could lead to duplicates, so checking for that as well)
    def _getPCKeyValue(self, sobj, field):
        return (
            ("Contact", field.replace("__pc", "__c"))
            if field.endswith("__pc")
            else (sobj, field)
        )

    def _setFieldData(self, table, field):
        self._checkKey(table)
        if field.endswith("__pc"):
            sobj, contactField = self._getPCKeyValue(table, field)
            self._setFieldData(sobj, contactField)
        (
            self[table]["fields"].append(field)
            if field not in self[table]["fields"]
            else None
        )
