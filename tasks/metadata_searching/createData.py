from contextlib import contextmanager
from datetime import timedelta
import os
from pathlib import Path
import json
from typing import Callable
from utils.menu import menu

from sqlalchemy.engine import create_engine
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.session import Session
from sqlalchemy.orm.util import aliased
from sqlalchemy.sql.schema import MetaData
from cumulusci.core.config import TaskConfig
from cumulusci.tasks.bulkdata.generate_from_yaml import (
    GenerateDataFromYaml,
    process_list_of_pairs_dict_arg,
)
from cumulusci.tasks.bulkdata.load import LoadData
from cumulusci.tasks.bulkdata.utils import SqlAlchemyMixin
from cumulusci.tasks.salesforce.BaseSalesforceApiTask import BaseSalesforceApiTask
import cumulusci.core.exceptions as exc
from cumulusci.tasks.bulkdata.mapping_parser import parse_from_yaml
import time
import re
from cumulusci.core.exceptions import BulkDataException
from cumulusci.core.utils import (
    format_duration,
)

PROJECT_CONFIG_RE = re.compile(r"\$project_config.(\w+)")


class createRecordsFromRecipe(SqlAlchemyMixin, BaseSalesforceApiTask):
    task_options = {
        "recipe": {
            "description": "Path to a Snowfakery recipe file determining what fields to use.",
        },
        "owner": {
            "description": "The owner of the records being created.",
        },
        "recipe_options": {
            "description": "Legacy support for record owner.  Use --owner instead.",
        },
        "component": {
            "description": "The applicant component. This selects the recipe and has no effect if --recipe is specified. "
            " Valid values are: RA, ARNG, RESERVE",
        },
        "compcd": {
            "description": "Shorthand for --component. Valid values are: A = Active, R = Reserve, G = Guard",
        },
        "preview": {
            "description": "If true, will run the recipe without creating records.",
        },
        "count": {
            "required": False,
            "description": "Number of Applicant record sets to create.",
        },
        # todo: use this
        "working_directory": {
            "description": "The directory to use for temporary files.",
        },
    }
    components = ["RA", "ARNG", "RESERVE"]

    def _invalidCompMessage(self, cmp=None):
        return f"""Invalid component: {self.options['component'] if cmp is None else cmp}
    - Valid options are: {self.components}
    -> Example: cci task run createData --component RA"""

    def validate_options(self):
        if "recipe" not in self.options and "component" not in self.options:
            self.selectComponent()
        elif self.count is None or self.count < 1:
            self.count = 1
        if "component" in self.options and not self._is_component_valid(
            self.options["component"]
        ):
            raise exc.TaskOptionsError(self._invalidCompMessage())
        self.recipe = self.options.get("recipe")
        recipe = Path(self.recipe)
        if not recipe.exists():
            raise exc.TaskOptionsError(f"Cannot find recipe `{recipe}`")

    def selectComponent(self):
        selected, idx = menu(
            self.components + ["(exit)"],
            "For which component do you want to create data?",
        )
        if selected == "(exit)":
            self._logandexit("Exiting...")
        self.options["component"] = selected
        self.options["recipe"] = self._get_recipe_path(self.options["component"])
        if self.count is None or self.count < 1:
            self.askCount()
        self.confirm_run()

    def askCount(self):
        self.count, idx = menu(
            [],
            "How many accounts would you like to create?",
            "Enter a number (default is 1)",
            1,
        )
        if isinstance(self.count, int) and self.count < 1:
            self.askCount()
        elif isinstance(self.count, int) is False:
            try:
                self.count = int(self.count)
            except ValueError:
                raise exc.TaskOptionsError(
                    f'"Count" must be a number. You provided "{self.count}"'
                )

    def confirm_run(self, no_action: Callable[[str], str] = None):
        """Confirm the task is ready to run."""
        title = f"""Are you sure you want to create data for {self.options['component']}?\n -> Command: \"{self.getFinalCommandString()}\"\n"""
        confirm, idx = menu(["Yes", "No", "Preview Only", "(exit)"], title)
        if confirm == "(exit)":
            self._logandexit("Exiting...")
        if confirm == "No":
            self.count = None
            self.selectComponent() if no_action is None else no_action()
        elif confirm == "Preview Only":
            self.options["preview"] = True
            self.logger.info(
                "Previewing output only...This will not create any records."
            )
        else:
            self.logger.info(
                f"Creating data for {self.options['component']} in {self.org_config.name}"
            )

    def getFinalCommandString(self):
        cmd = f"cci task run createData --org {self.org_config.name}"
        if "component" in self.options:
            cmd += f" --component {self.options.get('component')}"
        elif "recipe" in self.options:
            cmd += f" --recipe {self.options.get('recipe')}"
        if "recipe_options" in self.options and "owner" not in self.options:
            self.options["owner"] = process_list_of_pairs_dict_arg(
                self.options["recipe_options"]
            ).get("recordOwnerUsername", None)
        if "owner" in self.options:
            owner = self.options.get("owner")
            if " " in owner:
                owner = f"'{owner}'"
            cmd += f" --owner {owner}"
        cmd += f" --run_until_records_loaded Account:{self.count}"
        return cmd

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        options = self.options
        if "recipe_options" in options:
            rc = process_list_of_pairs_dict_arg(options["recipe_options"])
            if "owner" not in options and "recordOwnerUsername" in rc:
                options["owner"] = rc.get("recordOwnerUsername", None)
        if "compcd" in options and "component" not in options:
            options["component"] = self._getComponentFromCode(options["compcd"])
        if "component" in options:
            cmp = options["component"]
            options["component"] = options["component"].upper()
            if options["component"] not in self.components:
                raise exc.TaskOptionsError(self._invalidCompMessage(cmp))
        if "recipe" in options and "component" in options:
            raise exc.TaskOptionsError(
                "Please specify either --recipe or --component/--compcd, not both"
            )
        if "component" in options and "recipe" not in options:
            options["recipe"] = self._get_recipe_path(options["component"])

    def _get_recipe_path(self, component):
        return f"datasets/TempRes/{component}/TempResData.recipe.yml"

    def _is_component_valid(self, component):
        return component in ["RA", "ARNG", "RESERVE"]

    def _getComponentFromCode(self, compcd):
        if compcd == "A":
            return "RA"
        elif compcd == "R":
            return "ARNG"
        elif compcd == "G":
            return "RESERVE"
        else:
            raise exc.TaskOptionsError(
                f"""Invalid component code: {compcd}
            Valid options are: A, R, G
            A = Active, R = Reserve, G = Guard

            Example for Active Army: cci task run createData --compcd A """
            )

    def setup(self):
        self.start_time = time.time()
        self.results = []
        self.owner = self.options.get("owner") if "owner" in self.options else None
        try:
            self.count = (
                int(self.options.get("count")) if "count" in self.options else None
            )
        except ValueError:
            raise exc.TaskOptionsError(
                f"""Invalid count: {self.count}

            Example for Active Army: cci task run createData --count 2 """
            )
        self.output_dir = os.path.join(
            os.getcwd(),
            "reports",
            "created_data",
            self.org_config.name,
            time.strftime("%Y%m%d%H%M%S"),
        )
        self.validate_options()

    def _run_task(self):
        self.setup()
        self.logger.info(f'...Compiled Command: "{self.getFinalCommandString()}"')
        self.logger.info(f"...Recipe: '{self.recipe}'")
        self.logger.info(
            f"...Record Owner: '{self.options['owner']}'"
        ) if "owner" in self.options else None
        self.logger.info(f"...Output Directory: '{self.output_dir}'")
        self.logger.info(f"...Number of Accounts to create: {self.count}")
        if "preview" in self.options:
            self.logger.info("...Log Only")
            self._snowfakeToCLI()
        else:
            tempMapping, tempDb = self._generate_and_load()
            self.logger.info("Generated data in %s", self.output_dir)
            elapsed = format_duration(timedelta(seconds=time.time() - self.start_time))
            totals = 0
            self.logger.info("\n== Results ==\n")
            for result in self.results:
                sobject_name = result["sobject"]
                successes = result["records_processed"] - result["total_row_errors"]
                totals += successes
                self.logger.info(f" ...{sobject_name} records created: { successes } ")
            self._unify(tempMapping, tempDb)
            self.logger.info("\n== Totals ==\n")
            self.logger.info(
                f"  ☃ Snowfakery created {totals} records in {elapsed} seconds"
            )

    def _unify(self, tempMapping, tempDb):
        """Merges the data fields from the object tables and the generated SFID fields from the SFID tables
        Logs results to the UI
        """
        # There's probably a way more efficient way to do this
        tsk = LoadData(
            self.project_config,
            TaskConfig({"options": {"mapping": tempMapping, "database_url": tempDb}}),
            self.org_config,
        )
        tsk.mapping = parse_from_yaml(tempMapping)
        self.logger.info("\n== Quick Links ==")
        with self._init_db(tsk):
            tsk._expand_mapping()
            csvfilepath = os.path.join(self.output_dir, "Records.csv")
            with open(csvfilepath, "w", newline="") as csvfile:
                csvfile.write("sobject,id,url\n")
                csvrows = []
                for name, mapping in tsk.mapping.items():
                    model = tsk.models[mapping.table]
                    id_column = model.__table__.primary_key.columns.keys()[0]
                    columns = [getattr(model, id_column)]
                    aliasedIdTable = aliased(
                        tsk.metadata.tables[f"{mapping.table}_sf_ids"]
                    )
                    columns.append(aliasedIdTable.columns.sf_id.label("id"))
                    for fname, f in mapping.fields.items():
                        if fname not in ("Id"):
                            columns.append(model.__table__.columns[f])
                    # self.logger.info([x.key for x in columns])
                    query = tsk.session.query(*columns)
                    query = query.outerjoin(
                        aliasedIdTable,
                        aliasedIdTable.columns.id == model.__table__.columns[id_column],
                    )
                    all_rows = [dict(x) for x in query.all()]
                    for row in all_rows:
                        # Todo: Identify core recipe objects and use those instead of Account / Opportunity
                        shouldLog = mapping.table in ["Account", "Opportunity"]
                        recId = row["id"]
                        self.logger.info(
                            f"\n  {mapping.table} ({row['id']}):"
                        ) if shouldLog else None
                        url = f"{self.org_config.config['instance_url']}/{recId}"
                        csvrows.append(f"{mapping.table},{recId},{url}")
                        for k, v in row.items():
                            # Todo: Allow field names to be customized by options
                            if k in ["id", "Name", "SSN__pc", "OwnerId"] and shouldLog:
                                if k == "id":
                                    self.logger.info(f"    - URL: {url}")
                                else:
                                    self.logger.info(f"    - {k}: {v}")
                csvfile.write("\n".join(csvrows))

    def _generate_and_load(self):
        """Sub-task to generate data and save it to the custom output directory.
        Calls GenerateDataFromYaml and LoadData."""
        tempMapping = os.path.join(self.output_dir, "generated_mapping.yml")
        tempDBUrl = "sqlite:///" + os.path.join(self.output_dir, "generated_data.db")
        os.makedirs(self.output_dir, exist_ok=True)
        with open(tempMapping, "w") as f:
            print("...Generating data...") if f is None else None
            taskOptions = {
                "generator_yaml": self.recipe,
                "generate_mapping_file": tempMapping,
                "database_url": tempDBUrl,
            }
            if self.owner:
                taskOptions["vars"] = "recordOwnerUsername:{}".format(self.owner)
            if self.count > 1:
                taskOptions["num_records"] = self.count
                taskOptions["num_records_tablename"] = "Account"
            task_config = TaskConfig({"options": taskOptions})
            subtask = GenerateDataFromYaml(
                self.project_config, task_config, self.org_config
            )
            subtask()
        step_results = self._loadData(tempMapping, tempDBUrl)
        self.results = [v for v in step_results["step_results"].values()]
        return tempMapping, tempDBUrl

    def _loadData(
        self,
        mapping_file,
        database_url,
        batch_size=1,
    ):
        """Custom load data task to load data into the database and return the statistics."""
        subtask_options = {
            "mapping": mapping_file,
            "reset_oids": False,
            "database_url": database_url,
            "num_records": None,
            "current_batch_number": 0,
            "working_directory": self.output_dir,
            "set_recently_viewed": False,
        }
        subtask_config = TaskConfig({"options": subtask_options})
        subtask = LoadData(
            project_config=self.project_config,
            task_config=subtask_config,
            org_config=self.org_config,
        )
        subtask()
        return subtask.return_values

    @contextmanager
    def _init_db(self, tsk):
        """Override the default _init_db to to keep and process the data before it gets cleaned up"""
        with tsk._database_url() as database_url:
            parent_engine = create_engine(database_url)
            with parent_engine.connect() as connection:
                # initialize the DB session
                tsk.session = Session(connection)

                if tsk.options.get("sql_path"):
                    tsk._sqlite_load()

                # initialize DB metadata
                tsk.metadata = MetaData()
                tsk.metadata.bind = connection
                tsk.inspector = inspect(parent_engine)

                # initialize the automap mapping
                tsk.base = automap_base(bind=connection, metadata=tsk.metadata)
                tsk.base.prepare(connection, reflect=True)

                # Loop through mappings and reflect each referenced table
                tsk.models = {}
                for name, mapping in tsk.mapping.items():
                    if mapping.table not in tsk.models:
                        try:
                            tsk.models[mapping.table] = tsk.base.classes[mapping.table]
                        except KeyError as e:
                            raise BulkDataException(f"Table not found in dataset: {e}")

                yield

    def _snowfakeToCLI(self):
        from snowfakery.api import generate_data
        from io import StringIO

        out = StringIO()
        user_options = (
            {} if self.owner is None else {"recordOwnerUsername": f"{self.owner}"}
        )
        plugin_options = {
            "org_config": self.org_config,
            "project_config": self.project_config,
            "plugin_options": {"org_name": self.org_config.name},
        }
        generate_data(
            self.recipe,
            output_files=[out],
            output_format="json",
            plugin_options=plugin_options,
            user_options=user_options,
            target_number=(self.count, "Account"),
        )
        val = json.loads(out.getvalue())
        values = {}
        for row in val:
            table = row["_table"]
            cleanVal = {k: v for k, v in row.items() if k not in ["_table"]}
            if table not in values:
                values[table] = []
            values[table].append(cleanVal)
            # self._logandexit(values)

        """

        for table, rows in values.items():
            data = []
            keys = [k for k,v in rows[0].items()]
            data.append(keys)
            for r in rows:
                data.append([v for k,v in r.items()])
                #data2=list(map(list, r.items()))
            CliTable(data,title=table).echo()
        """
        self.logger.info(json.dumps(values, indent=2))
        return values
        """
        task_options = {
            "command": f"snowfakery {self.recipe} --plugin-option org_name {self.org_config.name}",
        }
        task_config = TaskConfig({"options": task_options})
        task = Command(self.project_config, task_config, org_config=self.org_config, logger=self.logger)
        task()
        """

    def _logandexit(self, message, exitcode=1):
        """Log a message and exit with the given exit code."""
        self.logger.info(message)
        exit(exitcode)
